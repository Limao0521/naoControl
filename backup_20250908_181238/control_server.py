#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server.py – WebSocket → NAOqi dispatcher + Head‐Touch Web‐Launcher (single-config, adaptive gait)

• ws://0.0.0.0:6671
• JSON actions:
    walk, walkTo, move, gait, getGait, caps, getCaps, getConfig,
    footProtection, posture, led, say, language, autonomous, kick,
    volume, getBattery, getAutonomousLife, turnLeft, turnRight,
    adaptiveLightGBM, getLightGBMStats,
    startLogging, stopLogging, getLoggingStatus, logSample ← NEW

• Watchdog            elif action == "move":
                joint = msg.get("joint","")
                val   = float(msg.get("value",0))
                motion.setAngles(str(joint), val, 0.1)
                logger.info("Move: setAngles(%s, %.2f)" % (joint,val))ne la marcha si no recibe walk en WATCHDOG s

Cambios clave (versión "single-config + adaptive"):
- Único conjunto de parámetros de marcha (gait) modificable por WS.
- CAPs (vx,vy,wz) editables por WS.
- NUEVO: Bucle adaptativo que lee FSR + IMU, calcula CoP y ajusta marcha
  suavemente (sin saltos) con histeresis y rampas en velocidades.
- Soporte para LightGBM AutoML adaptativo con logging CSV
- Control de data logger integrado para generar datasets de entrenamiento
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
    logger.info("Sistema de logging centralizado conectado")
except ImportError:
    # Fallback si no está disponible
    class FallbackLogger:
        def debug(self, msg): print("DEBUG [CONTROL] {}".format(msg))
        def info(self, msg): print("INFO [CONTROL] {}".format(msg))
        def warning(self, msg): print("WARNING [CONTROL] {}".format(msg))
        def error(self, msg): print("ERROR [CONTROL] {}".format(msg))
        def critical(self, msg): print("CRITICAL [CONTROL] {}".format(msg))
    logger = FallbackLogger()
    print("WARNING: Sistema de logging centralizado no disponible, usando fallback")

# — Configuración general —
IP_NAO     = "127.0.0.1"
PORT_NAO   = 9559
WS_PORT    = 6671
WATCHDOG   = 0.6
WEB_DIR    = "/home/nao/Webs/ControllerWebServer"
HTTP_PORT  = "8000"

# Importar data logger
try:
    from data_logger import DataLogger, SensorReader
    DATA_LOGGER_AVAILABLE = True
    logger.info("Data logger disponible")
except (ImportError, AttributeError) as e:
    logger.warning("Data logger no disponible: {}".format(e))
    DATA_LOGGER_AVAILABLE = False

# Importar LightGBM AutoML de caminata adaptativa
try:
    from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
    adaptive_walker = AdaptiveWalkLightGBM("models_npz_automl", mode="production")
    logger.info("LightGBM AutoML inicializada - MODO PRODUCTION (parámetros óptimos pasto)")
    ADAPTIVE_WALK_ENABLED = True
except (ImportError, AttributeError, SyntaxError) as e:
    logger.warning("LightGBM AutoML adaptativo no disponible: {}".format(e))
    adaptive_walker = None
    ADAPTIVE_WALK_ENABLED = False

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

# ─── Función auxiliar para operaciones NAO seguras ────────────────────────────
def safe_nao_call(func, success_msg=None, error_prefix="NAO", *args, **kwargs):
    """Ejecuta una función NAO con manejo seguro de excepciones"""
    try:
        result = func(*args, **kwargs)
        if success_msg:
            logger.info("NAO: %s" % success_msg)
        return result
    except Exception as e:
        logger.warning("%s: %s" % (error_prefix, e))
        return None

# ─── Setup inicial seguro ──────────────────────────────────────────────────────
# Fall manager ON → auto-recover
motion.setFallManagerEnabled(True)
logger.info("NAO: Fall manager ENABLED → auto-recover ON")

# Mantener Autonomous Life desactivado y rigidez activa para control directo
life.setState("disabled")
motion.setStiffnesses("Body", 1.0)
logger.info("NAO: AutonomousLife disabled; Body stiffness ON")

# Activar balanceo de brazos durante el caminar (mejora estabilidad)
safe_nao_call(motion.setMoveArmsEnabled, "MoveArmsEnabled(True, True)", "NAO", True, True)

# Mantener protección de contacto de pie activada por defecto
safe_nao_call(motion.setMotionConfig, "FootContactProtection = True", "NAO", [["ENABLE_FOOT_CONTACT_PROTECTION", True]])

# ─── Callback de caída ─────────────────────────────────────────────────────────
def onFall(_key, _value, _msg):
    logger.info("FallEvt: detected! Recuperando postura...")
    try:
        posture.goToPosture("Stand", 0.7)
    except Exception as e:
        logger.error("FallEvt: Recover error: %s" % e)

try:
    memory.subscribeToEvent("RobotHasFallen", __name__, "onFall")
    logger.info("NAO: Suscrito a evento RobotHasFallen")
except Exception as e:
    logger.warning("NAO: Warn subscribe RobotHasFallen: %s" % e)

# ─── Funciones auxiliares ─────────────────────────────────────────────────────
def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)

def lerp(a, b, t):
    return (1.0 - t) * a + t * b

def ema(prev, x, alpha):
    return (1.0 - alpha) * prev + alpha * x

def pairs_to_dict(pairs):
    d = {}
    for k, v in pairs:
        d[k] = float(v)
    return d

def dict_to_pairs(d):
    return [[k, float(v)] for k, v in d.items()]

def merge_pairs(base_pairs, override_pairs):
    d = pairs_to_dict(base_pairs) if base_pairs else {}
    d.update(pairs_to_dict(override_pairs))
    return dict_to_pairs(d)

def _config_to_move_list(config_dict_or_list):
    """
    Acepta dict o lista y devuelve lista [[key, val], ...] solo con claves válidas.
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
    Llama moveToward con config. Si falla reintenta sin config.
    """
    try:
        motion.moveToward(vx, vy, wz, move_cfg_pairs)
    except Exception as e:
        logger.warning("Walk: moveToward with config failed: %s → retry no-config" % e)
        motion.moveToward(vx, vy, wz)

def _apply_absolute_limits(vx, vy, wz):
    """
    Aplicar límites absolutos a las velocidades antes de cualquier otro procesamiento.
    
    Límites forzados:
    - vx: entre -0.6 y 0.6
    - vy: entre -0.45 y 0.45
    - wz: sin límites adicionales (solo CAPS normales)
    
    Estos límites se aplican SIEMPRE, independientemente de CAPS o otros sistemas.
    """
    # Limitar vx entre -0.6 y 0.6
    if vx > 0.4:
        vx = 0.4
    elif vx < -0.4:
        vx = -0.4

    # Limitar vy entre -0.45 y 0.45
    if vy > 0.25:
        vy = 0.25
    elif vy < -0.25:
        vy = -0.25
    
    # wz sin límites adicionales (se deja para CAPS)
    return vx, vy, wz

# ─── Estados de Gait con suavizado ─────────────────────────────────────────────
GAIT_TARGET = []       # Objetivo único: manual o adaptativo [["MaxStepX", val], ...]
GAIT_SOURCE = "none"   # Fuente: "manual", "adaptive", "none"

# Aplicado (lo que realmente mandamos a moveToward):
GAIT_APPLIED = []      # lista de pares suavizada

# Parámetros de suavizado
ALPHA_GAIT = 0.15      # 0..1 (más bajo = más suave)

# Modo adaptativo
ADAPTIVE = {"enabled": False, "mode": "auto", "slip": False, "last_event": 0.0}

# Estado de caminar
_last_walk = time.time()

# ─── Data Logger state ─────────────────────────────────────────────────────────
data_logger_instance = None
sensor_reader_instance = None
logging_active = False

# ─── Watchdog ──────────────────────────────────────────────────────────────────
def watchdog():
    global _last_walk
    logger.info("Watchdog: Iniciado (%.1fs)" % WATCHDOG)
    while True:
        time.sleep(0.05)
        if time.time() - _last_walk > WATCHDOG:
            safe_nao_call(motion.stopMove, "Watchdog: stopMove() tras timeout", "Watchdog")
            _last_walk = time.time()

wd = threading.Thread(target=watchdog)
wd.setDaemon(True)
wd.start()

def adaptive_loop():
    global GAIT_APPLIED, GAIT_TARGET, GAIT_SOURCE
    logger.info("Adapt: Loop adaptativo iniciado")
    
    # Iniciales
    GAIT_TARGET = []
    GAIT_SOURCE = "none"
    GAIT_APPLIED = []
    
    while True:
        try:
            time.sleep(0.1)  # 10 Hz
            
            # LightGBM AutoML adaptativo si está disponible
            if ADAPTIVE_WALK_ENABLED and adaptive_walker and ADAPTIVE["enabled"]:
                try:
                    # Predecir parámetros de marcha con LightGBM AutoML
                    adaptive_params = adaptive_walker.predict_gait_parameters()
                    if adaptive_params:
                        # Convertir a formato esperado
                        adaptive_gait = []
                        for param, value in adaptive_params.items():
                            if param in ["MaxStepX", "MaxStepY", "MaxStepTheta", "StepHeight", "Frequency"]:
                                adaptive_gait.append([param, value])
                        
                        if adaptive_gait:
                            GAIT_TARGET = adaptive_gait
                            GAIT_SOURCE = "adaptive"
                            logger.debug("LightGBM AutoML adaptativo: {}".format(adaptive_params))
                except Exception as e:
                    logger.warning("Error en LightGBM AutoML adaptativo: {}".format(e))
            
            # Suavizar gait hacia objetivo único
            if GAIT_TARGET:
                target_d = pairs_to_dict(GAIT_TARGET)
                applied_d = pairs_to_dict(GAIT_APPLIED) if GAIT_APPLIED else {}
                
                all_keys = set(target_d.keys()) | set(applied_d.keys())
                new_applied = {}
                for k in all_keys:
                    current = applied_d.get(k, target_d.get(k, 0.0))
                    target = target_d.get(k, current)
                    new_applied[k] = lerp(current, target, ALPHA_GAIT)
                GAIT_APPLIED = dict_to_pairs(new_applied)
        
        except Exception as e:
            logger.error("Adapt: Error adaptive_loop: %s" % e)

# Lanzar el hilo adaptativo
adap = threading.Thread(target=adaptive_loop)
adap.setDaemon(True)
adap.start()

# ─── Limpieza de suscripciones y procesos ─────────────────────────────────────
web_proc = None

def cleanup_all_subscriptions():
    try:
        logger.info("Cleanup: Limpieza suscripciones NAOqi...")
        events_to_cleanup = ["RobotHasFallen","TouchChanged","FaceDetected",
                             "WordRecognized","SpeechDetected"]
        for event in events_to_cleanup:
            try:
                memory.unsubscribeToEvent(event, __name__)
            except Exception:
                pass
    except Exception as e:
        logger.error("Cleanup: Error limpieza subs: %s" % e)

def cleanup(signum, frame=None):
    global web_proc
    logger.info("Server: Señal {}, limpiando…".format(signum))
    
    # Mensaje TTS de cierre
    try:
        tts.say("nao control apagado")
        logger.info("Mensaje TTS de cierre enviado")
    except Exception as e:
        logger.warning("No se pudo enviar mensaje TTS de cierre: {}".format(e))
    
    try:
        cleanup_all_subscriptions()
    except Exception as e:
        logger.error("Cleanup: Error limpieza completa: {}".format(e))
    
    if web_proc:
        try:
            web_proc.terminate()
            web_proc.wait()
            logger.info("Cleanup: HTTP server detenido")
        except Exception as e:
            logger.error("Cleanup: Error deteniendo HTTP server: {}".format(e))
    
    try:
        logger.info("Cleanup: Liberando NAOqi...")
        motion.stopMove()
        motion.waitUntilMoveIsFinished()
        logger.info("Cleanup: NAOqi OK")
    except Exception as e:
        logger.error("Cleanup: Error liberando NAOqi: {}".format(e))
    
    logger.info("Cleanup: Bye")
    sys.exit(0)

signal.signal(signal.SIGINT,  cleanup)
signal.signal(signal.SIGTERM, cleanup)

# ─── WebSocket handler ─────────────────────────────────────────────────────────
class RobotWS(WebSocket):
    def handleConnected(self):
        logger.info("WS: Conectado %s" % (self.address,))
        # Al conectar, reporta config actual (aplicada) para no romper clientes
        try:
            self.sendMessage(json.dumps({"gait": GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET}))
        except Exception:
            pass

    def handleClose(self):
        logger.info("WS: Desconectado %s" % (self.address,))

    def handleMessage(self):
        global _last_walk, GAIT_APPLIED, GAIT_TARGET, GAIT_SOURCE
        global data_logger_instance, sensor_reader_instance, logging_active
        raw = self.data.strip()
        logger.debug("WS: Recibido RAW: %s" % raw)
        
        try:
            msg = json.loads(raw)
        except Exception as e:
            logger.warning("WS: JSON inválido: %s (%s)" % (raw, e))
            return

        action = msg.get("action")
        try:
            # ── Caminar reactivo con gait actual (solo límites absolutos) ─────────
            if action == "walk":
                vx, vy, wz = map(float, (msg.get("vx",0), msg.get("vy",0), msg.get("wz",0)))
                
                # 🚨 LÍMITES ABSOLUTOS FORZADOS (aplicados SIEMPRE)
                # Estos son los límites máximos para caminar en pasto
                vx, vy, wz = _apply_absolute_limits(vx, vy, wz)
                
                # Normaliza magnitud del vector (x,y) si excede 1.0
                norm = math.hypot(vx, vy)
                if norm > 1.0:
                    vx, vy = vx/norm, vy/norm

                # LightGBM AutoML Adaptativo: Predecir parámetros de marcha óptimos
                adaptive_cfg = None
                if ADAPTIVE_WALK_ENABLED and adaptive_walker and ADAPTIVE["enabled"]:
                    try:
                        adaptive_params = adaptive_walker.predict_gait_parameters()
                        if adaptive_params:
                            adaptive_cfg = _config_to_move_list(adaptive_params)
                            logger.debug("LightGBM AutoML adaptativo: {}".format(adaptive_params))
                    except Exception as e:
                        logger.warning("Error en LightGBM AutoML adaptativo: {}".format(e))

                # Usar configuración adaptativa si está disponible, sino la configuración actual
                move_cfg = adaptive_cfg if adaptive_cfg else _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET)
                _apply_moveToward(vx, vy, wz, move_cfg)
                _last_walk = time.time()
                
                cfg_source = "LightGBM" if adaptive_cfg else "Manual"
                logger.info("Walk: moveToward(vx=%.2f, vy=%.2f, wz=%.2f) cfg=%s [%s]" %
                    (vx, vy, wz, move_cfg, cfg_source))

            # ── Caminar a un objetivo (bloqueante) con mismo gait ─────────────
            elif action == "walkTo":
                x = float(msg.get("x", 0.0))
                y = float(msg.get("y", 0.0))
                theta = float(msg.get("theta", 0.0))
                move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET)
                try:
                    motion.moveTo(x, y, theta, move_cfg)
                except Exception as e:
                    logger.warning("WalkTo: moveTo with cfg failed: %s → retry sin cfg" % e)
                    motion.moveTo(x, y, theta)
                logger.info("WalkTo: moveTo(x=%.2f,y=%.2f,th=%.2f)" % (x,y,theta))

            # ── Girar sobre su propio eje - Izquierda ─────────────────────────
            elif action == "turnLeft":
                angular_speed = float(msg.get("speed", 0.5))
                duration = float(msg.get("duration", 0.0))
                
                # No hay límites adicionales para wz (el input del front y los límites absolutos lo manejan)
                
                if duration > 0:
                    # Giro por tiempo específico
                    move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET)
                    _apply_moveToward(0.0, 0.0, angular_speed, move_cfg)
                    time.sleep(duration)
                    motion.stopMove()
                    logger.info("Turn: turnLeft(speed=%.2f, duration=%.2f) - COMPLETADO" % (angular_speed, duration))
                else:
                    # Giro continuo hasta que se detenga
                    move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET)
                    _apply_moveToward(0.0, 0.0, angular_speed, move_cfg)
                    _last_walk = time.time()
                    logger.info("Turn: turnLeft(speed=%.2f) - CONTINUO" % angular_speed)

            # ── Girar sobre su propio eje - Derecha ───────────────────────────
            elif action == "turnRight":
                angular_speed = float(msg.get("speed", 0.5))
                duration = float(msg.get("duration", 0.0))
                
                # Hacer negativo para giro a la derecha, sin límites adicionales de caps
                angular_speed = -angular_speed
                
                if duration > 0:
                    # Giro por tiempo específico
                    move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET)
                    _apply_moveToward(0.0, 0.0, angular_speed, move_cfg)
                    time.sleep(duration)
                    motion.stopMove()
                    logger.info("Turn: turnRight(speed=%.2f, duration=%.2f) - COMPLETADO" % (abs(angular_speed), duration))
                else:
                    # Giro continuo hasta que se detenga
                    move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET)
                    _apply_moveToward(0.0, 0.0, angular_speed, move_cfg)
                    _last_walk = time.time()
                    logger.info("Turn: turnRight(speed=%.2f) - CONTINUO" % abs(angular_speed))

            # ── Seteo de Gait (manual por WS) ─────────────────────────────────
            elif action == "gait":
                user_cfg = msg.get("config", {})
                # admite dict {"StepHeight":0.03,...} o lista [["StepHeight",0.03],...]
                if not isinstance(user_cfg, (dict, list)):
                    raise ValueError("config debe ser dict o lista de pares")
                GAIT_TARGET = _config_to_move_list(user_cfg)
                GAIT_SOURCE = "manual"
                self.sendMessage(json.dumps({"gaitApplied": GAIT_TARGET}))
                logger.info("Gait: Nuevo gait config (manual) = %s" % GAIT_TARGET)

            elif action == "getGait":
                response_data = {
                    "gait": GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET,
                    "target": GAIT_TARGET,
                    "applied": GAIT_APPLIED,
                    "source": GAIT_SOURCE
                }
                self.sendMessage(json.dumps(response_data))
                logger.info("Gait: getGait → applied=%s target=%s source=%s" % (GAIT_APPLIED, GAIT_TARGET, GAIT_SOURCE))

            # ── Atajo para leer configuración (sin caps) ──────────────────────
            elif action == "getConfig":
                self.sendMessage(json.dumps({"gait": (GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET),
                                             "adaptive": ADAPTIVE}))
                logger.info("Config: getConfig → gait=%s adaptive=%s" % ((GAIT_APPLIED if GAIT_APPLIED else GAIT_TARGET), ADAPTIVE))

            # ── Protecciones de pie ───────────────────────────────────────────
            elif action == "footProtection":
                enable = bool(msg.get("enable", True))
                motion.setMotionConfig([["ENABLE_FOOT_CONTACT_PROTECTION", enable]])
                self.sendMessage(json.dumps({"footProtection": enable}))
                logger.info("FootProt: FootContactProtection set to %s" % enable)

            # ── Movimiento articular directo ──────────────────────────────────
            elif action == "move":
                joint = msg.get("joint","")
                val   = float(msg.get("value",0))
                logger.info("Move: setAngles(%s, %.2f)" % (joint,val))

            # ── Postura ───────────────────────────────────────────────────────
            elif action == "posture":
                pst = msg.get("value","Stand")
                posture.goToPosture(str(pst), 0.7)
                logger.info("Posture: goToPosture('%s')" % pst)

            # ── LEDs ──────────────────────────────────────────────────────────
            elif action == "led":
                grp = msg.get("group", "ChestLeds")
                # Python 2/3 compatibility para unicode
                try:
                    unicode_type = unicode
                except NameError:
                    unicode_type = str
                if isinstance(grp, unicode_type):
                    try:
                        grp = grp.encode('utf-8')
                    except Exception:
                        pass
                r, g, b = map(float, (msg.get("r",0), msg.get("g",0), msg.get("b",0)))
                duration = float(msg.get("duration", 0.0))
                rgb_int = (int(r*255) << 16) | (int(g*255) << 8) | int(b*255)
                if grp in ("LeftEarLeds", "RightEarLeds"):
                    intensity = (rgb_int & 0xFF) / 255.0
                    leds.fade(grp, intensity, duration)
                    logger.info("LED: fade('%s',%.2f,%.2f)" % (grp, intensity, duration))
                else:
                    leds.fadeRGB(grp, rgb_int, duration)
                    logger.info("LED: fadeRGB('%s',0x%06X,%.2f)" % (grp, rgb_int, duration))

            # ── Hablar ────────────────────────────────────────────────────────
            elif action == "say":
                txt = msg.get("text","")
                tts.say(str(txt))
                logger.info("TTS: say('%s')" % txt)

            # ── Idioma TTS ────────────────────────────────────────────────────
            elif action == "language":
                lang = msg.get("value","")
                try:
                    tts.setLanguage(str(lang))
                    logger.info("TTS: setLanguage('%s')" % lang)
                except Exception as e:
                    logger.warning("WS: Error setLanguage('%s'): %s" % (lang, e))

            # ── Autonomous Life ───────────────────────────────────────────────
            elif action == "autonomous":
                enable = bool(msg.get("enable", False))
                new_state = "interactive" if enable else "disabled"
                life.setState(new_state)
                logger.info("Autonomous: AutonomousLife.setState('%s')" % new_state)

            # ── Kick (ejecuta behavior si existe) ─────────────────────────────
            elif action == "kick":
                try:
                    behavior_name = "kicknao-f6eb94/behavior_1"
                    if behavior and behavior.isBehaviorInstalled(behavior_name):
                        for bhv in behavior.getRunningBehaviors():
                            behavior.stopBehavior(bhv)
                        behavior.runBehavior(behavior_name)
                        logger.info("Kick: Ejecutando kick behavior: '%s'" % behavior_name)
                    else:
                        logger.warning("WS: ⚠ Behavior kick no instalado: '%s'" % behavior_name)
                        installed = behavior.getInstalledBehaviors()
                        kicks = [b for b in installed if "kick" in b.lower()]
                        if kicks:
                            behavior.runBehavior(kicks[0])
                            logger.info("Kick: Ejecutando kick alternativo: '%s'" % kicks[0])
                        else:
                                logger.warning("WS: ⚠ No se encontró behavior de kick")
                except Exception as e:
                    logger.warning("WS: Error ejecutando kick: %s" % e)

            # ── Volumen ─────────────────────────────────────────────────────
            elif action == "volume":
                vol = float(msg.get("value", 50))
                audio.setOutputVolume(vol)
                logger.info("Audio: AudioDevice.setOutputVolume(%.1f)" % vol)

            # ── Estado de batería ─────────────────────────────────────────────
            elif action == "getBattery":
                level = 100  # Valor por defecto
                try:
                    level = battery.getBatteryCharge()
                except:
                    pass
                low   = (level < 20)
                full  = (level >= 95)
                payload = json.dumps({"battery": level, "low": low, "full": full})
                self.sendMessage(payload)
                logger.info("Battery: getBattery → %d%% low=%s full=%s"%(level,low,full))

            # ── Estado Autonomous Life ────────────────────────────────────────
            elif action == "getAutonomousLife":
                try:
                    current_state = life.getState()
                    is_enabled = current_state != "disabled"
                    self.sendMessage(json.dumps({"autonomousLifeEnabled": is_enabled}))
                    logger.info("Autonomous: getAutonomousLife → enabled=%s"%(is_enabled))
                except Exception as e:
                    logger.warning("WS: Error getAutonomousLife: %s" % e)
                    self.sendMessage(json.dumps({"autonomousLifeEnabled": False}))

            # ── Control LightGBM AutoML Adaptativo ───────────────────────────────
            elif action == "adaptiveLightGBM":
                try:
                    enable = msg.get("enabled", True)
                    mode = str(msg.get("mode", ADAPTIVE["mode"]))  # Soporte para modo
                    
                    if adaptive_walker:
                        # Configurar modo adaptativo
                        ADAPTIVE["enabled"] = enable
                        if mode in ("auto", "slippery"):
                            ADAPTIVE["mode"] = mode
                        ADAPTIVE["last_event"] = 0.0  # reset suave
                        
                        stats = {}
                        if hasattr(adaptive_walker, 'get_stats'):
                            stats = adaptive_walker.get_stats()
                        
                        self.sendMessage(json.dumps({
                            "adaptiveLightGBM": {
                                "enabled": enable,
                                "mode": ADAPTIVE["mode"],
                                "available": ADAPTIVE_WALK_ENABLED,
                                "stats": stats
                            }
                        }))
                        logger.info("LightGBM AutoML adaptativo {} - Modo: {} - Stats: {}".format(
                            "habilitado" if enable else "deshabilitado", ADAPTIVE["mode"], stats))
                    else:
                        self.sendMessage(json.dumps({
                            "adaptiveLightGBM": {
                                "enabled": False,
                                "available": False,
                                "error": "LightGBM AutoML no disponible"
                            }
                        }))
                        logger.warning("LightGBM AutoML adaptativo no disponible")
                except Exception as e:
                    logger.error("Error controlando LightGBM: {}".format(e))
                    self.sendMessage(json.dumps({"adaptiveLightGBM": {"error": str(e)}}))

            # ── Estadísticas LightGBM AutoML Adaptativo ──────────────────────────
            elif action == "getLightGBMStats":
                try:
                    if adaptive_walker:
                        stats = {}
                        if hasattr(adaptive_walker, 'get_stats'):
                            stats = adaptive_walker.get_stats()
                        self.sendMessage(json.dumps({"lightGBMStats": stats}))
                        logger.debug("Estadísticas LightGBM enviadas: {}".format(stats))
                    else:
                        self.sendMessage(json.dumps({"lightGBMStats": {"error": "LightGBM no disponible"}}))
                        logger.warning("LightGBM no disponible para estadísticas")
                except Exception as e:
                    logger.error("Error obteniendo estadísticas LightGBM: {}".format(e))
                    self.sendMessage(json.dumps({"lightGBMStats": {"error": str(e)}}))

            # ── Control Data Logger ───────────────────────────────────────────
            elif action == "startLogging":
                try:
                    if not DATA_LOGGER_AVAILABLE:
                        self.sendMessage(json.dumps({"startLogging": {"success": False, "error": "Data logger no disponible"}}))
                        return
                    
                    if logging_active:
                        self.sendMessage(json.dumps({"startLogging": {"success": False, "error": "Logging ya activo"}}))
                        return
                    
                    # Obtener parámetros
                    duration = float(msg.get("duration", 300))  # 5 minutos por defecto
                    frequency = float(msg.get("frequency", 10))  # 10 Hz por defecto
                    output_file = msg.get("output", "")
                    
                    # Generar nombre de archivo si no se proporciona
                    if not output_file:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_file = "/home/nao/logs/adaptive_data_{}.csv".format(timestamp)
                        # En Windows para testing
                        if os.name == 'nt':
                            output_file = "C:/tmp/adaptive_data_{}.csv".format(timestamp)
                    
                    # Inicializar componentes
                    sensor_reader_instance = SensorReader(IP_NAO, PORT_NAO)
                    data_logger_instance = DataLogger(output_file, sensor_reader_instance)
                    
                    if data_logger_instance.start_logging():
                        logging_active = True
                        response = {
                            "startLogging": {
                                "success": True,
                                "output": output_file,
                                "duration": duration,
                                "frequency": frequency
                            }
                        }
                        logger.info("DataLogger: Logging iniciado: {} ({}s @ {}Hz)".format(output_file, duration, frequency))
                    else:
                        response = {"startLogging": {"success": False, "error": "No se pudo iniciar logging"}}
                    
                    self.sendMessage(json.dumps(response))
                    
                except Exception as e:
                    logger.error("Error iniciando logging: {}".format(e))
                    self.sendMessage(json.dumps({"startLogging": {"success": False, "error": str(e)}}))

            elif action == "stopLogging":
                try:
                    if not logging_active or not data_logger_instance:
                        self.sendMessage(json.dumps({"stopLogging": {"success": False, "error": "Logging no activo"}}))
                        return
                    
                    samples_written = data_logger_instance.samples_written
                    data_logger_instance.stop_logging()
                    logging_active = False
                    
                    response = {
                        "stopLogging": {
                            "success": True,
                            "samples": samples_written
                        }
                    }
                    self.sendMessage(json.dumps(response))
                    logger.info("DataLogger: Logging detenido. Muestras: {}".format(samples_written))
                    
                except Exception as e:
                    logger.error("Error deteniendo logging: {}".format(e))
                    self.sendMessage(json.dumps({"stopLogging": {"success": False, "error": str(e)}}))

            elif action == "getLoggingStatus":
                try:
                    samples = 0
                    output_file = ""
                    if data_logger_instance:
                        samples = data_logger_instance.samples_written
                        output_file = data_logger_instance.output_file
                    
                    response = {
                        "loggingStatus": {
                            "active": logging_active,
                            "available": DATA_LOGGER_AVAILABLE,
                            "samples": samples,
                            "output": output_file
                        }
                    }
                    self.sendMessage(json.dumps(response))
                    
                except Exception as e:
                    logger.error("Error obteniendo estado logging: {}".format(e))
                    self.sendMessage(json.dumps({"loggingStatus": {"error": str(e)}}))

            elif action == "logSample":
                try:
                    if not logging_active or not data_logger_instance:
                        self.sendMessage(json.dumps({"logSample": {"success": False, "error": "Logging no activo"}}))
                        return
                    
                    success = data_logger_instance.log_sample()
                    samples = data_logger_instance.samples_written
                    
                    response = {
                        "logSample": {
                            "success": success,
                            "samples": samples
                        }
                    }
                    self.sendMessage(json.dumps(response))
                    
                except Exception as e:
                    logger.error("Error logging sample: {}".format(e))
                    self.sendMessage(json.dumps({"logSample": {"success": False, "error": str(e)}}))

            # ── Control de modo adaptativo ────────────────────────────────────
            elif action == "setAdaptiveMode":
                try:
                    mode = msg.get("mode", "")
                    if adaptive_walker and mode in ["training", "production"]:
                        adaptive_walker.set_mode(mode)
                        current_mode = adaptive_walker.get_mode()
                        logger.info("Modo adaptativo cambiado a: {}".format(current_mode))
                        self.sendMessage(json.dumps({
                            "setAdaptiveMode": {
                                "success": True,
                                "mode": current_mode
                            }
                        }))
                    elif not adaptive_walker:
                        self.sendMessage(json.dumps({
                            "setAdaptiveMode": {
                                "success": False,
                                "error": "Adaptive walker no disponible"
                            }
                        }))
                    else:
                        self.sendMessage(json.dumps({
                            "setAdaptiveMode": {
                                "success": False,
                                "error": "Modo inválido. Use 'training' o 'production'"
                            }
                        }))
                except Exception as e:
                    logger.error("Error cambiando modo adaptativo: {}".format(e))
                    self.sendMessage(json.dumps({
                        "setAdaptiveMode": {
                            "success": False,
                            "error": str(e)
                        }
                    }))

            elif action == "getAdaptiveMode":
                try:
                    if adaptive_walker:
                        current_mode = adaptive_walker.get_mode()
                        self.sendMessage(json.dumps({
                            "getAdaptiveMode": {
                                "success": True,
                                "mode": current_mode
                            }
                        }))
                    else:
                        self.sendMessage(json.dumps({
                            "getAdaptiveMode": {
                                "success": False,
                                "error": "Adaptive walker no disponible"
                            }
                        }))
                except Exception as e:
                    logger.error("Error obteniendo modo adaptativo: {}".format(e))
                    self.sendMessage(json.dumps({
                        "getAdaptiveMode": {
                            "success": False,
                            "error": str(e)
                        }
                    }))

            # ── Control Fall Manager ──────────────────────────────────────────
            elif action == "fallManager":
                try:
                    enable = bool(msg.get("enable", True))
                    
                    if enable:
                        # Activar Fall Manager (simple)
                        motion.setFallManagerEnabled(True)
                        status = "ENABLED"
                        logger.info("Fall Manager ENABLED: auto-recovery ON")
                    else:
                        # Desactivar Fall Manager requiere pasos especiales
                        try:
                            # Paso 1: Habilitar la desactivación del Fall Manager
                            motion.setFallManagerEnabled(False, True)  # enable=False, allowDisable=True
                            status = "DISABLED"
                            logger.info("Fall Manager DISABLED: manual control (safety override)")
                        except Exception as e1:
                            try:
                                # Método alternativo: Usar ALMemory para forzar desactivación
                                memory.insertData("FallManagerEnabled", False)
                                status = "DISABLED"
                                logger.warning("Fall Manager DISABLED via ALMemory fallback")
                            except Exception as e2:
                                # Si ambos métodos fallan, reportar error
                                raise Exception("Cannot disable Fall Manager. NAOqi safety protection active. Error 1: {} Error 2: {}".format(str(e1), str(e2)))
                    
                    self.sendMessage(json.dumps({
                        "fallManager": {
                            "success": True,
                            "enabled": enable,
                            "status": status
                        }
                    }))
                    
                except Exception as e:
                    logger.error("Error configurando Fall Manager: {}".format(e))
                    self.sendMessage(json.dumps({
                        "fallManager": {
                            "success": False,
                            "error": str(e),
                            "help": "Try: motion.setFallManagerEnabled(False, True) or restart NAOqi"
                        }
                    }))

            # ── Forzar desactivación Fall Manager (método avanzado) ──────────
            elif action == "forceDisableFallManager":
                try:
                    logger.warning("Intentando forzar desactivación del Fall Manager...")
                    
                    methods_tried = []
                    success = False
                    
                    # Método 1: setFallManagerEnabled con allowDisable
                    try:
                        motion.setFallManagerEnabled(False, True)
                        methods_tried.append("setFallManagerEnabled(False, True) - SUCCESS")
                        success = True
                    except Exception as e1:
                        methods_tried.append("setFallManagerEnabled(False, True) - FAILED: {}".format(str(e1)))
                    
                    # Método 2: ALMemory directo
                    if not success:
                        try:
                            memory.insertData("FallManagerEnabled", False)
                            methods_tried.append("ALMemory insertData - SUCCESS")
                            success = True
                        except Exception as e2:
                            methods_tried.append("ALMemory insertData - FAILED: {}".format(str(e2)))
                    
                    # Método 3: Configuración de movimiento
                    if not success:
                        try:
                            motion.setMotionConfig([["ENABLE_FALL_MANAGER", False]])
                            methods_tried.append("setMotionConfig ENABLE_FALL_MANAGER - SUCCESS")
                            success = True
                        except Exception as e3:
                            methods_tried.append("setMotionConfig - FAILED: {}".format(str(e3)))
                    
                    if success:
                        logger.info("Fall Manager forzado a DISABLED")
                        self.sendMessage(json.dumps({
                            "forceDisableFallManager": {
                                "success": True,
                                "enabled": False,
                                "status": "FORCE_DISABLED",
                                "methods_tried": methods_tried
                            }
                        }))
                    else:
                        logger.error("No se pudo forzar desactivación del Fall Manager")
                        self.sendMessage(json.dumps({
                            "forceDisableFallManager": {
                                "success": False,
                                "error": "All methods failed",
                                "methods_tried": methods_tried,
                                "help": "Fall Manager protection is active. Consider restarting NAOqi or using Choregraphe."
                            }
                        }))
                        
                except Exception as e:
                    logger.error("Error en forzar desactivación Fall Manager: {}".format(e))
                    self.sendMessage(json.dumps({
                        "forceDisableFallManager": {
                            "success": False,
                            "error": str(e)
                        }
                    }))

            # ── Obtener estado Fall Manager ───────────────────────────────────
            elif action == "getFallManager":
                try:
                    enabled = motion.getFallManagerEnabled()
                    self.sendMessage(json.dumps({
                        "getFallManager": {
                            "success": True,
                            "enabled": enabled,
                            "status": "ENABLED" if enabled else "DISABLED"
                        }
                    }))
                except Exception as e:
                    logger.error("Error obteniendo estado Fall Manager: {}".format(e))
                    self.sendMessage(json.dumps({
                        "getFallManager": {
                            "success": False,
                            "error": str(e)
                        }
                    }))
                    
            else:
                logger.warning("WS: ⚠ Acción desconocida '%s'" % action)

        except Exception as e:
            logger.warning("WS: Excepción en %s: %s" % (action, e))

# ─── Arranque WS ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Server: Iniciando WS en ws://0.0.0.0:%d" % WS_PORT)
    srv = None
    try:
        while True:
            try:
                srv = SimpleWebSocketServer("", WS_PORT, RobotWS)
                break
            except socket.error as e:
                if e.errno == errno.EADDRINUSE:
                    logger.info("Server: Puerto %d ocupado, reintentando en 3s…" % WS_PORT)
                    time.sleep(3)
                else:
                    raise
        logger.info("Server: Servidor WebSocket iniciado")
        logger.info("Control server WebSocket activo en puerto {}".format(WS_PORT))
        
        # Mensaje TTS de confirmación
        try:
            tts.say("nao control iniciado")
            logger.info("Mensaje TTS de inicio enviado")
        except Exception as e:
            logger.warning("No se pudo enviar mensaje TTS: {}".format(e))
        
        srv.serveforever()
    except KeyboardInterrupt:
        logger.info("Server: Interrupción de teclado detectada")
        cleanup(signal.SIGINT, None)
    except Exception as e:
        logger.info("Server: Error fatal: {}".format(e))
        cleanup(signal.SIGTERM, None)
    finally:
        if srv:
            try:
                srv.close()
            except Exception:
                pass