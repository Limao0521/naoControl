#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server.py – WebSocket → NAOqi dispatcher + Head‐Touch Web‐Launcher (single-config)

• ws://0.0.0.0:6671
• JSON actions:
    walk, walkTo, move, gait, getGait, caps, getCaps, getConfig,
    footProtection, posture, led, say, language, autonomous, kick,
    volume, getBattery, getAutonomousLife
• Watchdog detiene la marcha si no recibe walk en WATCHDOG s

Cambios clave (versión “single-config”):
- Se elimina setTerrain y todos los presets.
- Queda un ÚNICO conjunto de parámetros de marcha (gait) que puedes cambiar por WS.
- Quedan CAPs (vx,vy,wz) editables por WS para limitar velocidades.
"""

from __future__ import print_function
import sys, os, time, math, threading, json, socket, errno, subprocess, signal
from datetime import datetime
from naoqi import ALProxy

# ───── Rutas WS local ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/home/nao/SimpleWebSocketServer-0.1.2")
from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer

# Importar sistema de logging
try:
    from logger import create_logger
    logger = create_logger("CONTROL")
except ImportError:
    # Fallback si no está disponible
    class FallbackLogger:
        def debug(self, msg): print("DEBUG [CONTROL] {}".format(msg))
        def info(self, msg): print("INFO [CONTROL] {}".format(msg))
        def warning(self, msg): print("WARNING [CONTROL] {}".format(msg))
        def error(self, msg): print("ERROR [CONTROL] {}".format(msg))
        def critical(self, msg): print("CRITICAL [CONTROL] {}".format(msg))
    logger = FallbackLogger()

# — Configuración general —
IP_NAO     = "127.0.0.1"
PORT_NAO   = 9559
WS_PORT    = 6671
WATCHDOG   = 0.6
WEB_DIR    = "/home/nao/Websx/ControllerWebServer"
HTTP_PORT  = "8000"

def log(tag, msg):
    """Función de logging mejorada que usa el sistema centralizado"""
    ts = datetime.now().strftime("%H:%M:%S")
    formatted_msg = "{} [{}] {}".format(ts, tag, msg)
    print(formatted_msg)
    
    # Enviar al sistema de logging centralizado
    if tag == "NAO" or tag == "FallEvt":
        logger.info("[{}] {}".format(tag, msg))
    elif "error" in msg.lower() or "fail" in msg.lower():
        logger.error("[{}] {}".format(tag, msg))
    elif "warn" in msg.lower():
        logger.warning("[{}] {}".format(tag, msg))
    else:
        logger.info("[{}] {}".format(tag, msg))

# ───── Proxies NAOqi ───────────────────────────────────────────────────────────
logger.info("Inicializando proxies NAOqi...")
try:
    motion     = ALProxy("ALMotion",         IP_NAO, PORT_NAO)
    posture    = ALProxy("ALRobotPosture",   IP_NAO, PORT_NAO)
    life       = ALProxy("ALAutonomousLife", IP_NAO, PORT_NAO)
    leds       = ALProxy("ALLeds",           IP_NAO, PORT_NAO)
    tts        = ALProxy("ALTextToSpeech",   IP_NAO, PORT_NAO)
    battery    = ALProxy("ALBattery",        IP_NAO, PORT_NAO)
    memory     = ALProxy("ALMemory",         IP_NAO, PORT_NAO)
    audio      = ALProxy("ALAudioDevice",    IP_NAO, PORT_NAO)
    behavior   = ALProxy("ALBehaviorManager", IP_NAO, PORT_NAO)
    logger.info("Todos los proxies NAOqi inicializados correctamente")
except Exception as e:
    logger.critical("Error inicializando proxies NAOqi: {}".format(e))
    sys.exit(1)

# ─── Setup inicial seguro ──────────────────────────────────────────────────────
# Fall manager ON → auto-recover
motion.setFallManagerEnabled(True)
log("NAO", "Fall manager ENABLED → auto-recover ON")

# Mantener Autonomous Life desactivado y rigidez activa para control directo
life.setState("disabled")
motion.setStiffnesses("Body", 1.0)
log("NAO", "AutonomousLife disabled; Body stiffness ON")

# Activar balanceo de brazos durante el caminar (mejora estabilidad)
try:
    motion.setMoveArmsEnabled(True, True)
    log("NAO", "MoveArmsEnabled(True, True)")
except Exception as e:
    log("NAO", "Warn setMoveArmsEnabled: %s" % e)

# Mantener protección de contacto de pie activada por defecto
try:
    motion.setMotionConfig([["ENABLE_FOOT_CONTACT_PROTECTION", True]])
    log("NAO", "FootContactProtection = True")
except Exception as e:
    log("NAO", "Warn FootContactProtection: %s" % e)

# ─── Callback de caída ─────────────────────────────────────────────────────────
def onFall(_key, _value, _msg):
    log("FallEvt", "detected! Recuperando postura...")
    try:
        posture.goToPosture("Stand", 0.7)
    except Exception as e:
        log("FallEvt", "Recover error: %s" % e)

try:
    memory.subscribeToEvent("RobotHasFallen", __name__, "onFall")
    log("NAO", "Suscrito a evento RobotHasFallen")
except Exception as e:
    log("NAO", "Warn subscribe RobotHasFallen: %s" % e)

# ─── Único Gait + CAPs ─────────────────────────────────────────────────────────
# Por defecto: vacío -> NAOqi usa sus valores internos. Puedes sobrescribir por WS con action="gait".
CURRENT_GAIT = []  # e.g.: [["StepHeight",0.03],["MaxStepX",0.028],["MaxStepY",0.10],["MaxStepTheta",0.22],["Frequency",0.50]]
# CAPs de velocidad (1.0 = sin límite). Editables vía acción "caps".
CAP_LIMITS  = {"vx": 1.0, "vy": 1.0, "wz": 1.0}

def _config_to_move_list(config_dict_or_list):
    """
    Acepta dict o lista y devuelve lista [[key, val], ...] solo con claves válidas.
    Incluye compat para versiones antiguas/nuevas:
      - "Frequency" (0..1) usado en doc 1.12/2.1.x
      - "MaxStepFrequency" (algunas notas 2.5) — intentamos pasarla si viene.
    """
    allowed = set(["MaxStepX","MaxStepY","MaxStepTheta","MaxStepFrequency",
                   "StepHeight","TorsoWx","TorsoWy","Frequency"])
    pairs = []
    if isinstance(config_dict_or_list, dict):
        items = config_dict_or_list.items()
    else:
        # asume lista de pares
        items = config_dict_or_list
    for k, v in items:
        if k in allowed:
            pairs.append([k, float(v)])
    return pairs

def _apply_moveToward(vx, vy, wz, move_cfg_pairs):
    """
    Llama moveToward con config. Algunas versiones solo aceptan "Frequency",
    otras aceptan "MaxStepFrequency"; pasamos lo que tengamos y si falla reintentamos
    sin config para no perder control.
    """
    try:
        motion.moveToward(vx, vy, wz, move_cfg_pairs)
    except Exception as e:
        log("Walk", "moveToward with config failed: %s → retry no-config" % e)
        motion.moveToward(vx, vy, wz)

# ─── Watchdog ──────────────────────────────────────────────────────────────────
_last_walk = time.time()
def watchdog():
    global _last_walk
    log("Watchdog", "Iniciado (%.1fs)" % WATCHDOG)
    while True:
        time.sleep(0.05)
        if time.time() - _last_walk > WATCHDOG:
            try:
                motion.stopMove()
                _last_walk = time.time()
                log("Watchdog", "stopMove() tras timeout")
            except Exception as e:
                log("Watchdog", "stopMove error: %s" % e)

wd = threading.Thread(target=watchdog)
wd.setDaemon(True)
wd.start()

# ─── Limpieza de suscripciones y procesos ─────────────────────────────────────
web_proc = None

def cleanup_all_subscriptions():
    try:
        log("Cleanup", "Limpieza suscripciones NAOqi...")
        events_to_cleanup = ["RobotHasFallen","TouchChanged","FaceDetected",
                             "WordRecognized","SpeechDetected"]
        for event in events_to_cleanup:
            try:
                memory.unsubscribeToEvent(event, __name__)
            except Exception:
                pass
    except Exception as e:
        log("Cleanup", "Error limpieza subs: %s" % e)

def cleanup(signum, frame):
    global web_proc
    log("Server", "Señal {}, limpiando…".format(signum))
    
    # Mensaje TTS de cierre
    try:
        tts.say("nao control apagado")
        logger.info("Mensaje TTS de cierre enviado")
    except Exception as e:
        logger.warning("No se pudo enviar mensaje TTS de cierre: {}".format(e))
    
    try:
        cleanup_all_subscriptions()
    except Exception as e:
        log("Cleanup", "Error limpieza completa: {}".format(e))
    if web_proc:
        try:
            web_proc.terminate()
            web_proc.wait()
            log("Cleanup", "HTTP server detenido (pid {}).".format(web_proc.pid))
        except Exception as e:
            log("Cleanup", "Error deteniendo HTTP server: {}".format(e))
    try:
        log("Cleanup", "Liberando NAOqi...")
        motion.stopMove()
        motion.waitUntilMoveIsFinished()
        log("Cleanup", "NAOqi OK")
    except Exception as e:
        log("Cleanup", "Error liberando NAOqi: {}".format(e))
    log("Cleanup", "Bye")
    sys.exit(0)

signal.signal(signal.SIGINT,  cleanup)
signal.signal(signal.SIGTERM, cleanup)

# ─── WebSocket handler ─────────────────────────────────────────────────────────
class RobotWS(WebSocket):
    def handleConnected(self):
        log("WS", "Conectado %s" % (self.address,))
        # Al conectar, reporta config actual
        try:
            self.sendMessage(json.dumps({"gait": CURRENT_GAIT, "caps": CAP_LIMITS}))
        except Exception:
            pass

    def handleClose(self):
        log("WS", "Desconectado %s" % (self.address,))

    def handleMessage(self):
        global _last_walk, CURRENT_GAIT, CAP_LIMITS
        raw = self.data.strip()
        log("WS", "Recibido RAW: %s" % raw)
        try:
            msg = json.loads(raw)
        except Exception as e:
            log("WS", "JSON inválido: %s (%s)" % (raw, e))
            return

        action = msg.get("action")
        try:
            # ── Caminar reactivo con gait actual + caps ────────────────────────
            if action == "walk":
                vx, vy, wz = map(float, (msg.get("vx",0), msg.get("vy",0), msg.get("wz",0)))
                # Normaliza magnitud del vector (x,y) si excede 1.0
                norm = math.hypot(vx, vy)
                if norm > 1.0:
                    vx, vy = vx/norm, vy/norm
                # Aplica CAPs
                vx = max(-CAP_LIMITS["vx"], min(CAP_LIMITS["vx"], vx))
                vy = max(-CAP_LIMITS["vy"], min(CAP_LIMITS["vy"], vy))
                wz = max(-CAP_LIMITS["wz"], min(CAP_LIMITS["wz"], wz))

                move_cfg = _config_to_move_list(CURRENT_GAIT)
                _apply_moveToward(vx, vy, wz, move_cfg)
                _last_walk = time.time()
                log("SIM", "moveToward(vx=%.2f, vy=%.2f, wz=%.2f) cfg=%s caps=%s" %
                    (vx, vy, wz, move_cfg, CAP_LIMITS))

            # ── Caminar a un objetivo (bloqueante) con mismo gait ─────────────
            elif action == "walkTo":
                x = float(msg.get("x", 0.0))
                y = float(msg.get("y", 0.0))
                theta = float(msg.get("theta", 0.0))
                move_cfg = _config_to_move_list(CURRENT_GAIT)
                try:
                    motion.moveTo(x, y, theta, move_cfg)
                except Exception as e:
                    log("WalkTo", "moveTo with cfg failed: %s → retry sin cfg" % e)
                    motion.moveTo(x, y, theta)
                log("SIM", "moveTo(x=%.2f,y=%.2f,th=%.2f)" % (x,y,theta))

            # ── Seteo de Gait (único mecanismo de cambio de marcha) ───────────
            elif action == "gait":
                user_cfg = msg.get("config", {})
                # admite dict {"StepHeight":0.03,...} o lista [["StepHeight",0.03],...]
                if not isinstance(user_cfg, (dict, list)):
                    raise ValueError("config debe ser dict o lista de pares")
                CURRENT_GAIT = _config_to_move_list(user_cfg)
                self.sendMessage(json.dumps({"gaitApplied": CURRENT_GAIT}))
                log("Gait", "Nuevo gait config = %s" % CURRENT_GAIT)

            elif action == "getGait":
                self.sendMessage(json.dumps({"gait": CURRENT_GAIT}))
                log("Gait", "getGait → %s" % CURRENT_GAIT)

            # ── Seteo/consulta de CAPs de velocidad ───────────────────────────
            elif action == "caps":
                vx = msg.get("vx", None)
                vy = msg.get("vy", None)
                wz = msg.get("wz", None)
                def clamp01(v):
                    try:
                        v = float(v)
                        if v < 0: v = 0.0
                        if v > 1: v = 1.0
                        return v
                    except Exception:
                        return None
                updated = {}
                if vx is not None:
                    CAP_LIMITS["vx"] = clamp01(vx); updated["vx"] = CAP_LIMITS["vx"]
                if vy is not None:
                    CAP_LIMITS["vy"] = clamp01(vy); updated["vy"] = CAP_LIMITS["vy"]
                if wz is not None:
                    CAP_LIMITS["wz"] = clamp01(wz); updated["wz"] = CAP_LIMITS["wz"]
                self.sendMessage(json.dumps({"caps": CAP_LIMITS, "updated": updated}))
                log("Caps", "CAP_LIMITS = %s (updated %s)" % (CAP_LIMITS, updated))

            elif action == "getCaps":
                self.sendMessage(json.dumps({"caps": CAP_LIMITS}))
                log("Caps", "getCaps → %s" % CAP_LIMITS)

            # ── Atajo para leer todo de una ───────────────────────────────────
            elif action == "getConfig":
                self.sendMessage(json.dumps({"gait": CURRENT_GAIT, "caps": CAP_LIMITS}))
                log("Config", "getConfig → gait=%s caps=%s" % (CURRENT_GAIT, CAP_LIMITS))

            # ── Protecciones de pie ───────────────────────────────────────────
            elif action == "footProtection":
                enable = bool(msg.get("enable", True))
                motion.setMotionConfig([["ENABLE_FOOT_CONTACT_PROTECTION", enable]])
                self.sendMessage(json.dumps({"footProtection": enable}))
                log("SIM", "FootContactProtection set to %s" % enable)

            # ── Movimiento articular directo ──────────────────────────────────
            elif action == "move":
                joint = msg.get("joint","")
                val   = float(msg.get("value",0))
                motion.setAngles(str(joint), val, 0.1)
                log("SIM", "setAngles('%s',%.2f)" % (joint,val))

            # ── Postura ───────────────────────────────────────────────────────
            elif action == "posture":
                pst = msg.get("value","Stand")
                posture.goToPosture(str(pst), 0.7)
                log("SIM", "goToPosture('%s')" % pst)

            # ── LEDs ──────────────────────────────────────────────────────────
            elif action == "led":
                grp = msg.get("group", "ChestLeds")
                if isinstance(grp, unicode): grp = grp.encode('utf-8')
                r, g, b = map(float, (msg.get("r",0), msg.get("g",0), msg.get("b",0)))
                duration = float(msg.get("duration", 0.0))
                rgb_int = (int(r*255) << 16) | (int(g*255) << 8) | int(b*255)
                if grp in ("LeftEarLeds", "RightEarLeds"):
                    intensity = (rgb_int & 0xFF) / 255.0
                    leds.fade(grp, intensity, duration)
                    log("SIM", "fade('%s',%.2f,%.2f)" % (grp, intensity, duration))
                else:
                    leds.fadeRGB(grp, rgb_int, duration)
                    log("SIM", "fadeRGB('%s',0x%06X,%.2f)" % (grp, rgb_int, duration))

            # ── Hablar ────────────────────────────────────────────────────────
            elif action == "say":
                txt = msg.get("text","")
                tts.say(str(txt))
                log("SIM", "say('%s')" % txt)

            # ── Idioma TTS ────────────────────────────────────────────────────
            elif action == "language":
                lang = msg.get("value","")
                try:
                    tts.setLanguage(str(lang))
                    log("SIM", "setLanguage('%s')" % lang)
                except Exception as e:
                    log("WS", "Error setLanguage('%s'): %s" % (lang, e))

            # ── Autonomous Life ───────────────────────────────────────────────
            elif action == "autonomous":
                enable = bool(msg.get("enable", False))
                new_state = "interactive" if enable else "disabled"
                life.setState(new_state)
                log("SIM", "AutonomousLife.setState('%s')" % new_state)

            # ── Kick (ejecuta behavior si existe) ─────────────────────────────
            elif action == "kick":
                try:
                    behavior_name = "kicknao-f6eb94/behavior_1"
                    if behavior.isBehaviorInstalled(behavior_name):
                        for bhv in behavior.getRunningBehaviors():
                            behavior.stopBehavior(bhv)
                        behavior.runBehavior(behavior_name)
                        log("SIM", "Ejecutando kick behavior: '%s'" % behavior_name)
                    else:
                        log("WS", "⚠ Behavior kick no instalado: '%s'" % behavior_name)
                        installed = behavior.getInstalledBehaviors()
                        kicks = [b for b in installed if "kick" in b.lower()]
                        if kicks:
                            behavior.runBehavior(kicks[0])
                            log("SIM", "Ejecutando kick alternativo: '%s'" % kicks[0])
                        else:
                            log("WS", "⚠ No se encontró behavior de kick")
                except Exception as e:
                    log("WS", "Error ejecutando kick: %s" % e)

            # ── Nuevo: ejecutar behavior "siu" (o buscar por substring "siu") ───
            elif action == "siu":
                try:
                    # nombre preferido del behavior (ajusta si conoces el path exacto)
                    behavior_name = "siu-17777b/behavior_1"
                    if behavior.isBehaviorInstalled(behavior_name):
                        # detener otros behaviors en ejecución
                        for bhv in behavior.getRunningBehaviors():
                            try:
                                behavior.stopBehavior(bhv)
                            except Exception:
                                pass
                        behavior.runBehavior(behavior_name)
                        log("SIM", "Ejecutando behavior 'siu' -> '%s'" % behavior_name)
                        try:
                            self.sendMessage(json.dumps({"siu": "started", "behavior": behavior_name}))
                        except Exception:
                            pass
                    else:
                        # buscar cualquier behavior que contenga "siu" en el nombre
                        installed = behavior.getInstalledBehaviors()
                        matches = [b for b in installed if "siu" in b.lower()]
                        if matches:
                            target = matches[0]
                            for bhv in behavior.getRunningBehaviors():
                                try:
                                    behavior.stopBehavior(bhv)
                                except Exception:
                                    pass
                            behavior.runBehavior(target)
                            log("SIM", "Ejecutando behavior 'siu' alternativo: '%s'" % target)
                            try:
                                self.sendMessage(json.dumps({"siu": "started", "behavior": target}))
                            except Exception:
                                pass
                        else:
                            log("WS", "⚠ Behavior 'siu' no encontrado entre instalados")
                            try:
                                self.sendMessage(json.dumps({"siu": "not_found"}))
                            except Exception:
                                pass
                except Exception as e:
                    log("WS", "Error ejecutando siu: %s" % e)
                    try:
                        self.sendMessage(json.dumps({"siu": "error", "reason": str(e)}))
                    except Exception:
                        pass

            # ── Nuevo: ejecutar behavior arbitrario por nombre (runBehavior) ───
            elif action == "runBehavior":
                try:
                    bname = msg.get("behavior", "")
                    if not bname:
                        raise ValueError("Se esperaba 'behavior' en el mensaje")
                    # si el cliente pasa un nombre parcial, intentar match por substring
                    if behavior.isBehaviorInstalled(bname):
                        target = bname
                    else:
                        installed = behavior.getInstalledBehaviors()
                        matches = [b for b in installed if bname.lower() in b.lower()]
                        if matches:
                            target = matches[0]
                        else:
                            log("WS", "runBehavior: no se encontró behavior para '%s'" % bname)
                            self.sendMessage(json.dumps({"runBehavior": "not_found", "query": bname}))
                            target = None
                    if target:
                        # detener behaviors activos
                        for bhv in behavior.getRunningBehaviors():
                            try:
                                behavior.stopBehavior(bhv)
                            except Exception:
                                pass
                        behavior.runBehavior(target)
                        log("WS", "runBehavior -> Ejecutando '%s'" % target)
                        self.sendMessage(json.dumps({"runBehavior": "started", "behavior": target}))
                except Exception as e:
                    log("WS", "Error runBehavior: %s" % e)
                    try:
                        self.sendMessage(json.dumps({"runBehavior": "error", "reason": str(e)}))
                    except Exception:
                        pass

            # ── Volumen ─────────────────────────────────────────────────────
            elif action == "volume":
                vol = float(msg.get("value", 50))
                audio.setOutputVolume(vol)
                log("SIM", "AudioDevice.setOutputVolume(%.1f)" % vol)

            # ── Estado de batería ─────────────────────────────────────────────
            elif action == "getBattery":
                level = battery.getBatteryCharge()
                low   = (level < 20)
                full  = (level >= 95)
                payload = json.dumps({"battery": level, "low": low, "full": full})
                self.sendMessage(payload)
                log("SIM","getBattery → %d%% low=%s full=%s"%(level,low,full))

            # ── Estado Autonomous Life ────────────────────────────────────────
            elif action == "getAutonomousLife":
                try:
                    current_state = life.getState()
                    is_enabled = current_state != "disabled"
                    self.sendMessage(json.dumps({"autonomousLifeEnabled": is_enabled}))
                    log("SIM","getAutonomousLife → enabled=%s"%(is_enabled))
                except Exception as e:
                    log("WS", "Error getAutonomousLife: %s" % e)
                    self.sendMessage(json.dumps({"autonomousLifeEnabled": False}))

            else:
                log("WS", "⚠ Acción desconocida '%s'" % action)

        except Exception as e:
            log("WS", "Excepción en %s: %s" % (action, e))

# ─── Arranque WS ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log("Server", "Iniciando WS en ws://0.0.0.0:%d" % WS_PORT)
    srv = None
    try:
        while True:
            try:
                srv = SimpleWebSocketServer("", WS_PORT, RobotWS)
                break
            except socket.error as e:
                if e.errno == errno.EADDRINUSE:
                    log("Server", "Puerto %d ocupado, reintentando en 3s…" % WS_PORT)
                    time.sleep(3)
                else:
                    raise
        log("Server", "Servidor WebSocket iniciado")
        logger.info("Control server WebSocket activo en puerto {}".format(WS_PORT))
        
        # Mensaje TTS de confirmación
        try:
            tts.say("nao control iniciado")
            logger.info("Mensaje TTS de inicio enviado")
        except Exception as e:
            logger.warning("No se pudo enviar mensaje TTS: {}".format(e))
        
        srv.serveforever()
    except KeyboardInterrupt:
        log("Server", "Interrupción de teclado detectada")
        cleanup(signal.SIGINT, None)
    except Exception as e:
        log("Server", "Error fatal: {}".format(e))
        cleanup(signal.SIGTERM, None)
    finally:
        if srv:
            try:
                srv.close()
            except Exception:
                pass
