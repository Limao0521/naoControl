#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server.py – WebSocket → NAOqi dispatcher + Head‐Touch Web‐Launcher

• ws://0.0.0.0:6671
• JSON actions: walk, walkTo, move, gait, setTerrain, footProtection, posture, led, say, language, autonomous, kick, volume, getBattery, getAutonomousLife
• Watchdog detiene la marcha si no recibe walk en WATCHDOG s
• Pulsar head tactile togglea el servidor HTTP en puerto 8000

Cambios clave (versión “terrain-gait”):
- Añadidos presets de terreno (default/carpet/turf/slippery) y acción setTerrain
- Acción gait para configurar parámetros de marcha personalizados (StepHeight, MaxStepX/Y/Theta, Frequency/MaxStepFrequency, TorsoWx/TorsoWy)
- walk aplica el gait/preset actual; clampa vx, vy, wz según presets
- walkTo con mismo gait
- Protecciones por defecto: FootContactProtection ON; brazos de balanceo ON
"""

from __future__ import print_function
import sys, os, time, math, threading, json, socket, errno, subprocess, signal
from datetime import datetime
from naoqi import ALProxy

# ───── Rutas WS local ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/home/nao/SimpleWebSocketServer-0.1.2")
from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer

# — Configuración general —
IP_NAO     = "127.0.0.1"
PORT_NAO   = 9559
WS_PORT    = 6671
WATCHDOG   = 0.6
WEB_DIR    = "/home/nao/Websx/ControllerWebServer"
HTTP_PORT  = "8000"

def log(tag, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print("{0} [{1}] {2}".format(ts, tag, msg))

# ───── Proxies NAOqi ───────────────────────────────────────────────────────────
motion     = ALProxy("ALMotion",         IP_NAO, PORT_NAO)
posture    = ALProxy("ALRobotPosture",   IP_NAO, PORT_NAO)
life       = ALProxy("ALAutonomousLife", IP_NAO, PORT_NAO)
leds       = ALProxy("ALLeds",           IP_NAO, PORT_NAO)
tts        = ALProxy("ALTextToSpeech",   IP_NAO, PORT_NAO)
battery    = ALProxy("ALBattery",        IP_NAO, PORT_NAO)
memory     = ALProxy("ALMemory",         IP_NAO, PORT_NAO)
audio      = ALProxy("ALAudioDevice",    IP_NAO, PORT_NAO)
behavior   = ALProxy("ALBehaviorManager", IP_NAO, PORT_NAO)

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

# ─── Callback de caída: incorporamos Stand al detectar evento ──────────────────
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

# ─── Presets de terreno y gait config ──────────────────────────────────────────
# Valores dentro de rangos oficiales:
#  - StepHeight: default ≈ 0.020 m; máximo ≈ 0.040 m
#  - MaxStepX/Y/Theta ajustan recortes de paso/giros
#  - Frequency (0..1) reduce la cadencia de paso
# Ver doc Aldebaran “Locomotion control API”.
TERRAIN_PRESETS = {
    # Caps limitan fracciones de velocidad pedidas por el front (vx,vy,wz) para suavizar
    "default": {
        "moveConfig": [],  # usa config de NAOqi por defecto
        "caps": {"vx":1.0, "vy":1.0, "wz":1.0}
    },
    "carpet": {
        "moveConfig": [
            ["StepHeight", 0.025],
            ["MaxStepX", 0.030],
            ["MaxStepY", 0.12],
            ["MaxStepTheta", 0.30],
            ["Frequency", 0.6]  # para NAOqi 2.1.x; ver compat más abajo
        ],
        "caps": {"vx":0.7, "vy":0.5, "wz":0.6}
    },
    "turf": {
        "moveConfig": [
            ["StepHeight", 0.030],   # mayor despeje del pie
            ["MaxStepX", 0.028],     # pasos más cortos
            ["MaxStepY", 0.10],
            ["MaxStepTheta", 0.25],
            ["Frequency", 0.5]       # cadencia más baja
        ],
        "caps": {"vx":0.6, "vy":0.4, "wz":0.5}
    },
    "slippery": {
        "moveConfig": [
            ["StepHeight", 0.020],   # normal, evita levantar de más
            ["MaxStepX", 0.020],
            ["MaxStepY", 0.08],
            ["MaxStepTheta", 0.20],
            ["Frequency", 0.4]
        ],
        "caps": {"vx":0.5, "vy":0.3, "wz":0.4}
    }
}

_current_terrain = "default"
_current_move_config = TERRAIN_PRESETS[_current_terrain]["moveConfig"][:]

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

# ─── Watchdog para detener la marcha si el front deja de enviar walk ───────────
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

# ─── Limpieza de suscripciones y procesos ──────────────────────────────────────
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
        # Reportar preset actual al conectar
        try:
            self.sendMessage(json.dumps({"terrain": _current_terrain}))
        except Exception:
            pass

    def handleClose(self):
        log("WS", "Desconectado %s" % (self.address,))

    def handleMessage(self):
        global _last_walk, _current_terrain, _current_move_config
        raw = self.data.strip()
        log("WS", "Recibido RAW: %s" % raw)
        try:
            msg = json.loads(raw)
        except Exception as e:
            log("WS", "JSON inválido: %s (%s)" % (raw, e))
            return

        action = msg.get("action")
        try:
            # ── Caminar reactivo con preset/gait ────────────────────────────────
            if action == "walk":
                vx, vy, wz = map(float, (msg.get("vx",0), msg.get("vy",0), msg.get("wz",0)))
                # Limitar magnitud del vector plano (x,y)
                norm = math.hypot(vx, vy)
                if norm > 1.0:
                    vx, vy = vx/norm, vy/norm

                # Caps por terreno para reducir agresividad en césped/turf
                caps = TERRAIN_PRESETS.get(_current_terrain, TERRAIN_PRESETS["default"])["caps"]
                vx = max(-caps["vx"], min(caps["vx"], vx))
                vy = max(-caps["vy"], min(caps["vy"], vy))
                wz = max(-caps["wz"], min(caps["wz"], wz))

                # Aplicar movimiento con gait actual
                move_cfg = _config_to_move_list(_current_move_config)
                _apply_moveToward(vx, vy, wz, move_cfg)
                _last_walk = time.time()
                log("SIM", "moveToward(vx=%.2f, vy=%.2f, wz=%.2f) cfg=%s" %
                    (vx, vy, wz, move_cfg))

            # ── Caminar a un objetivo (bloqueante) con mismo gait ───────────────
            elif action == "walkTo":
                x = float(msg.get("x", 0.0))
                y = float(msg.get("y", 0.0))
                theta = float(msg.get("theta", 0.0))
                move_cfg = _config_to_move_list(_current_move_config)
                try:
                    motion.moveTo(x, y, theta, move_cfg)
                except Exception as e:
                    log("WalkTo", "moveTo with cfg failed: %s → retry sin cfg" % e)
                    motion.moveTo(x, y, theta)
                log("SIM", "moveTo(x=%.2f,y=%.2f,th=%.2f)" % (x,y,theta))

            # ── Seteo de Gait custom (directo) ──────────────────────────────────
            elif action == "gait":
                # Permite dict con claves válidas (StepHeight, MaxStepX/Y/Theta, Frequency, TorsoWx/Wy…)
                user_cfg = msg.get("config", {})
                if not isinstance(user_cfg, dict):
                    raise ValueError("config debe ser dict")
                _current_move_config = _config_to_move_list(user_cfg)
                self.sendMessage(json.dumps({"gaitApplied": _current_move_config}))
                log("Gait", "Nuevo gait config = %s" % _current_move_config)

            # ── Selección de terreno (presets) ─────────────────────────────────
            elif action == "setTerrain":
                mode = str(msg.get("mode","default")).lower()
                if mode not in TERRAIN_PRESETS:
                    raise ValueError("Terreno inválido: %s" % mode)
                _current_terrain = mode
                _current_move_config = TERRAIN_PRESETS[mode]["moveConfig"][:]
                payload = {"terrain": _current_terrain, "gait": _current_move_config}
                self.sendMessage(json.dumps(payload))
                log("Terrain", "Preset '%s' aplicado: %s" % (mode, _current_move_config))

            # ── Protecciones de pie (usar con cuidado) ─────────────────────────
            elif action == "footProtection":
                enable = bool(msg.get("enable", True))
                motion.setMotionConfig([["ENABLE_FOOT_CONTACT_PROTECTION", enable]])
                self.sendMessage(json.dumps({"footProtection": enable}))
                log("SIM", "FootContactProtection set to %s" % enable)

            # ── Movimiento articular directo ───────────────────────────────────
            elif action == "move":
                joint = msg.get("joint","")
                val   = float(msg.get("value",0))
                motion.setAngles(str(joint), val, 0.1)
                log("SIM", "setAngles('%s',%.2f)" % (joint,val))

            # ── Postura ────────────────────────────────────────────────────────
            elif action == "posture":
                pst = msg.get("value","Stand")
                posture.goToPosture(str(pst), 0.7)
                log("SIM", "goToPosture('%s')" % pst)

            # ── LEDs ───────────────────────────────────────────────────────────
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

            # ── Hablar ─────────────────────────────────────────────────────────
            elif action == "say":
                txt = msg.get("text","")
                tts.say(str(txt))
                log("SIM", "say('%s')" % txt)

            # ── Idioma TTS ─────────────────────────────────────────────────────
            elif action == "language":
                lang = msg.get("value","")
                try:
                    tts.setLanguage(str(lang))
                    log("SIM", "setLanguage('%s')" % lang)
                except Exception as e:
                    log("WS", "Error setLanguage('%s'): %s" % (lang, e))

            # ── Autonomous Life ────────────────────────────────────────────────
            elif action == "autonomous":
                enable = bool(msg.get("enable", False))
                new_state = "interactive" if enable else "disabled"
                life.setState(new_state)
                log("SIM", "AutonomousLife.setState('%s')" % new_state)

            # ── Kick (ejecuta behavior si existe) ──────────────────────────────
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

            # ── Volumen ────────────────────────────────────────────────────────
            elif action == "volume":
                vol = float(msg.get("value", 50))
                audio.setOutputVolume(vol)
                log("SIM", "AudioDevice.setOutputVolume(%.1f)" % vol)

            # ── Estado de batería ──────────────────────────────────────────────
            elif action == "getBattery":
                level = battery.getBatteryCharge()
                low   = (level < 20)
                full  = (level >= 95)
                payload = json.dumps({"battery": level, "low": low, "full": full})
                self.sendMessage(payload)
                log("SIM","getBattery → %d%% low=%s full=%s"%(level,low,full))

            # ── Estado Autonomous Life ─────────────────────────────────────────
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
