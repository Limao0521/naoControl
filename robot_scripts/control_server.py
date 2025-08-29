#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server.py – WebSocket → NAOqi dispatcher + Head‐Touch Web‐Launcher (single-config, adaptive gait)

• ws://0.0.0.0:6671
• JSON actions:
    walk, walkTo, move, gait, getGait, caps, getCaps, getConfig,
    footProtection, posture, led, say, language, autonomous, kick,
    volume, getBattery, getAutonomousLife, turnLeft, turnRight,
    adaptiveGait, adaptiveLightGBM, getLightGBMStats,
    startLogging, stopLogging, getLoggingStatus, logSample ← NEW

• Watchdog            elif action == "move":
                joint = msg.get("joint","")
                val   = float(msg.get("value",0))
                motion.setAngles(str(joint), val, 0.1)
                log("Move", "setAngles(%s, %.2f)" % (joint,val))ne la marcha si no recibe walk en WATCHDOG s

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
    adaptive_walker = AdaptiveWalkLightGBM("models_npz_automl")
    logger.info("LightGBM AutoML de caminata adaptativa inicializada")
    ADAPTIVE_WALK_ENABLED = True
except (ImportError, AttributeError, SyntaxError) as e:
    logger.warning("LightGBM AutoML adaptativo no disponible: {}".format(e))
    adaptive_walker = None
    ADAPTIVE_WALK_ENABLED = False

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
        log("Walk", "moveToward with config failed: %s → retry no-config" % e)
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
    if vx > 0.6:
        vx = 0.6
    elif vx < -0.6:
        vx = -0.6
    
    # Limitar vy entre -0.45 y 0.45
    if vy > 0.45:
        vy = 0.45
    elif vy < -0.45:
        vy = -0.45
    
    # wz sin límites adicionales (se deja para CAPS)
    return vx, vy, wz

# ─── Único Gait + CAPs (por defecto NAOqi) ─────────────────────────────────────
CURRENT_GAIT = []  # e.g.: [["StepHeight",0.03],["MaxStepX",0.028],["MaxStepY",0.10],["MaxStepTheta",0.22],["Frequency",0.50]]
CAP_LIMITS  = {"vx": 0.5, "vy": 0.5, "wz": 0.5}

# ─── Estados de Gait y CAPS con suavizado ─────────────────────────────────────
GAIT_REF = []          # lista de pares [["MaxStepX", val], ...]
CAPS_REF = {"vx":0.5, "vy":0.5, "wz":0.5}

# Aplicado (lo que realmente mandamos a moveToward):
GAIT_APPLIED = []      # lista de pares suavizada
CAPS_APPLIED = {"vx":0.5, "vy":0.5, "wz":0.5}

# Parámetros de suavizado
ALPHA_GAIT = 0.15      # 0..1 (más bajo = más suave)
CAPS_DOWN_RATE = 0.05  # cuánto bajan por ciclo (rápido)
CAPS_UP_RATE   = 0.02  # cuánto suben por ciclo (lento)

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

# ─── Función de verificación de Golden Lock ────────────────────────────────────
def _check_golden_lock():
    """
    Verifica si existen parámetros golden bloqueados.
    Retorna (locked, golden_params) donde:
    - locked: True si hay parámetros bloqueados válidos
    - golden_params: dict con los parámetros a aplicar o None
    """
    try:
        lock_file = os.path.join(os.path.dirname(__file__), "golden_params_lock.json")
        if not os.path.exists(lock_file):
            return False, None
            
        with open(lock_file, 'r') as f:
            lock_data = json.load(f)
        
        # Verificar que el lock sea válido y no haya expirado
        if not lock_data.get("locked", False):
            return False, None
            
        # Verificar expiración si está definida
        expires_at = lock_data.get("expires_at")
        if expires_at and time.time() > expires_at:
            logger.info("Golden lock expirado, removiendo...")
            os.remove(lock_file)
            return False, None
            
        # Extraer parámetros golden
        golden_params = lock_data.get("locked_parameters")
        if not golden_params:
            return False, None
            
        logger.debug("Golden parameters activos: {}".format(golden_params))
        return True, golden_params
        
    except Exception as e:
        logger.warning("Error verificando golden lock: {}".format(e))
        return False, None

# ─── Bucle adaptativo simplificado con LightGBM AutoML ──────────────────────────
def adaptive_loop():
    global GAIT_APPLIED, CAPS_APPLIED, GAIT_REF, CAPS_REF, CURRENT_GAIT
    log("Adapt", "Loop adaptativo iniciado")
    
    # Iniciales
    GAIT_REF = []
    GAIT_APPLIED = []
    CAPS_REF = {"vx":1.0, "vy":1.0, "wz":1.0}
    CAPS_APPLIED = {"vx":1.0, "vy":1.0, "wz":1.0}
    
    while True:
        try:
            time.sleep(0.1)  # 10 Hz
            
            # ✨ VERIFICAR GOLDEN LOCK PRIMERO
            is_locked, golden_params = _check_golden_lock()
            
            if is_locked and golden_params:
                # Aplicar parámetros golden directamente sin variación
                adaptive_gait = []
                for param in ["MaxStepX", "MaxStepY", "MaxStepTheta", "StepHeight", "Frequency"]:
                    if param in golden_params:
                        adaptive_gait.append([param, golden_params[param]])
                
                if adaptive_gait:
                    GAIT_REF = adaptive_gait
                    logger.debug("Aplicando golden parameters: {}".format(golden_params))
                    
                # Skip el resto del loop adaptativo cuando está locked
                
            else:
                # Comportamiento adaptativo normal solo si NO está locked
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
                                GAIT_REF = adaptive_gait
                                logger.debug("LightGBM AutoML adaptativo: {}".format(adaptive_params))
                    except Exception as e:
                        logger.warning("Error en LightGBM AutoML adaptativo: {}".format(e))
            
            # Suavizar gait hacia referencia
            if GAIT_REF:
                ref_d = pairs_to_dict(GAIT_REF)
                app_d = pairs_to_dict(GAIT_APPLIED) if GAIT_APPLIED else {}
                
                all_keys = set(ref_d.keys()) | set(app_d.keys())
                new_app = {}
                for k in all_keys:
                    a = app_d.get(k, ref_d.get(k, 0.0))
                    b = ref_d.get(k, a)
                    new_app[k] = lerp(a, b, ALPHA_GAIT)
                GAIT_APPLIED = dict_to_pairs(new_app)
            
            # Suavizar caps
            for k in ("vx", "vy", "wz"):
                a = CAPS_APPLIED.get(k, 1.0)
                b = CAPS_REF.get(k, 1.0)
                if a > b:
                    a = max(b, a - CAPS_DOWN_RATE)
                else:
                    a = min(b, a + CAPS_UP_RATE)
                CAPS_APPLIED[k] = clamp(a, 0.0, 1.0)
        
        except Exception as e:
            log("Adapt", "Error adaptive_loop: %s" % e)

# Lanzar el hilo adaptativo
adap = threading.Thread(target=adaptive_loop)
adap.setDaemon(True)
adap.start()

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

def cleanup(signum, frame=None):
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
            log("Cleanup", "HTTP server detenido")
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
        # Al conectar, reporta config actual (aplicada) para no romper clientes
        try:
            self.sendMessage(json.dumps({"gait": GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT,
                                         "caps": CAPS_APPLIED}))
        except Exception:
            pass

    def handleClose(self):
        log("WS", "Desconectado %s" % (self.address,))

    def handleMessage(self):
        global _last_walk, CURRENT_GAIT, CAP_LIMITS, GAIT_APPLIED, CAPS_APPLIED, GAIT_REF, CAPS_REF
        global data_logger_instance, sensor_reader_instance, logging_active
        raw = self.data.strip()
        log("WS", "Recibido RAW: %s" % raw)
        
        try:
            msg = json.loads(raw)
        except Exception as e:
            log("WS", "JSON inválido: %s (%s)" % (raw, e))
            return

        action = msg.get("action")
        try:
            # ── Caminar reactivo con gait actual + caps (suavizados) ──────────
            if action == "walk":
                vx, vy, wz = map(float, (msg.get("vx",0), msg.get("vy",0), msg.get("wz",0)))
                
                # 🚨 LÍMITES ABSOLUTOS FORZADOS (aplicados SIEMPRE antes que cualquier otra limitación)
                # vx: entre -0.6 y 0.6
                if vx > 0.6:
                    vx = 0.6
                elif vx < -0.6:
                    vx = -0.6
                
                # vy: entre -0.45 y 0.45  
                if vy > 0.45:
                    vy = 0.45
                elif vy < -0.45:
                    vy = -0.45
                
                # Normaliza magnitud del vector (x,y) si excede 1.0
                norm = math.hypot(vx, vy)
                if norm > 1.0:
                    vx, vy = vx/norm, vy/norm

                # Aplicar CAPS suavizados (después de límites absolutos)
                vx = max(-CAPS_APPLIED["vx"], min(CAPS_APPLIED["vx"], vx))
                vy = max(-CAPS_APPLIED["vy"], min(CAPS_APPLIED["vy"], vy))
                wz = max(-CAPS_APPLIED["wz"], min(CAPS_APPLIED["wz"], wz))

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
                move_cfg = adaptive_cfg if adaptive_cfg else _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT)
                _apply_moveToward(vx, vy, wz, move_cfg)
                _last_walk = time.time()
                
                cfg_source = "LightGBM" if adaptive_cfg else "Manual"
                log("Walk", "moveToward(vx=%.2f, vy=%.2f, wz=%.2f) cfg=%s caps=%s [%s]" %
                    (vx, vy, wz, move_cfg, CAPS_APPLIED, cfg_source))

            # ── Caminar a un objetivo (bloqueante) con mismo gait ─────────────
            elif action == "walkTo":
                x = float(msg.get("x", 0.0))
                y = float(msg.get("y", 0.0))
                theta = float(msg.get("theta", 0.0))
                move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT)
                try:
                    motion.moveTo(x, y, theta, move_cfg)
                except Exception as e:
                    log("WalkTo", "moveTo with cfg failed: %s → retry sin cfg" % e)
                    motion.moveTo(x, y, theta)
                log("WalkTo", "moveTo(x=%.2f,y=%.2f,th=%.2f)" % (x,y,theta))

            # ── Girar sobre su propio eje - Izquierda ─────────────────────────
            elif action == "turnLeft":
                angular_speed = float(msg.get("speed", 0.5))
                duration = float(msg.get("duration", 0.0))
                
                # Aplicar límites de caps
                angular_speed = min(CAPS_APPLIED["wz"], angular_speed)
                
                if duration > 0:
                    # Giro por tiempo específico
                    move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT)
                    _apply_moveToward(0.0, 0.0, angular_speed, move_cfg)
                    time.sleep(duration)
                    motion.stopMove()
                    log("Turn", "turnLeft(speed=%.2f, duration=%.2f) - COMPLETADO" % (angular_speed, duration))
                else:
                    # Giro continuo hasta que se detenga
                    move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT)
                    _apply_moveToward(0.0, 0.0, angular_speed, move_cfg)
                    _last_walk = time.time()
                    log("Turn", "turnLeft(speed=%.2f) - CONTINUO" % angular_speed)

            # ── Girar sobre su propio eje - Derecha ───────────────────────────
            elif action == "turnRight":
                angular_speed = float(msg.get("speed", 0.5))
                duration = float(msg.get("duration", 0.0))
                
                # Aplicar límites de caps y hacer negativo para giro a la derecha
                angular_speed = -min(CAPS_APPLIED["wz"], angular_speed)
                
                if duration > 0:
                    # Giro por tiempo específico
                    move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT)
                    _apply_moveToward(0.0, 0.0, angular_speed, move_cfg)
                    time.sleep(duration)
                    motion.stopMove()
                    log("Turn", "turnRight(speed=%.2f, duration=%.2f) - COMPLETADO" % (abs(angular_speed), duration))
                else:
                    # Giro continuo hasta que se detenga
                    move_cfg = _config_to_move_list(GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT)
                    _apply_moveToward(0.0, 0.0, angular_speed, move_cfg)
                    _last_walk = time.time()
                    log("Turn", "turnRight(speed=%.2f) - CONTINUO" % abs(angular_speed))

            # ── Seteo de Gait (manual por WS) ─────────────────────────────────
            elif action == "gait":
                user_cfg = msg.get("config", {})
                # admite dict {"StepHeight":0.03,...} o lista [["StepHeight",0.03],...]
                if not isinstance(user_cfg, (dict, list)):
                    raise ValueError("config debe ser dict o lista de pares")
                CURRENT_GAIT = _config_to_move_list(user_cfg)
                # si hay adaptativo encendido, consideramos el CURRENT_GAIT como base
                GAIT_REF = merge_pairs(CURRENT_GAIT, [])
                self.sendMessage(json.dumps({"gaitApplied": CURRENT_GAIT}))
                log("Gait", "Nuevo gait config (manual) = %s" % CURRENT_GAIT)

            elif action == "getGait":
                self.sendMessage(json.dumps({"gait": GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT}))
                log("Gait", "getGait → %s" % (GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT))

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
                    CAPS_REF["vx"] = min(CAPS_REF.get("vx",1.0), CAP_LIMITS["vx"])
                if vy is not None:
                    CAP_LIMITS["vy"] = clamp01(vy); updated["vy"] = CAP_LIMITS["vy"]
                    CAPS_REF["vy"] = min(CAPS_REF.get("vy",1.0), CAP_LIMITS["vy"])
                if wz is not None:
                    CAP_LIMITS["wz"] = clamp01(wz); updated["wz"] = CAP_LIMITS["wz"]
                    CAPS_REF["wz"] = min(CAPS_REF.get("wz",1.0), CAP_LIMITS["wz"])
                self.sendMessage(json.dumps({"caps": CAPS_APPLIED, "updated": updated}))
                log("Caps", "CAP_LIMITS(user) = %s ; caps_applied=%s" % (CAP_LIMITS, CAPS_APPLIED))

            elif action == "getCaps":
                self.sendMessage(json.dumps({"caps": CAPS_APPLIED}))
                log("Caps", "getCaps → %s" % CAPS_APPLIED)

            # ── Atajo para leer todo de una ───────────────────────────────────
            elif action == "getConfig":
                self.sendMessage(json.dumps({"gait": (GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT),
                                             "caps": CAPS_APPLIED,
                                             "adaptive": ADAPTIVE}))
                log("Config", "getConfig → gait=%s caps=%s adaptive=%s" % ((GAIT_APPLIED if GAIT_APPLIED else CURRENT_GAIT), CAPS_APPLIED, ADAPTIVE))

            # ── Protecciones de pie ───────────────────────────────────────────
            elif action == "footProtection":
                enable = bool(msg.get("enable", True))
                motion.setMotionConfig([["ENABLE_FOOT_CONTACT_PROTECTION", enable]])
                self.sendMessage(json.dumps({"footProtection": enable}))
                log("FootProt", "FootContactProtection set to %s" % enable)

            # ── Movimiento articular directo ──────────────────────────────────
            elif action == "move":
                joint = msg.get("joint","")
                val   = float(msg.get("value",0))
                log("Move", "setAngles(%s, %.2f)" % (joint,val))

            # ── Postura ───────────────────────────────────────────────────────
            elif action == "posture":
                pst = msg.get("value","Stand")
                posture.goToPosture(str(pst), 0.7)
                log("Posture", "goToPosture('%s')" % pst)

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
                    log("LED", "fade('%s',%.2f,%.2f)" % (grp, intensity, duration))
                else:
                    leds.fadeRGB(grp, rgb_int, duration)
                    log("LED", "fadeRGB('%s',0x%06X,%.2f)" % (grp, rgb_int, duration))

            # ── Hablar ────────────────────────────────────────────────────────
            elif action == "say":
                txt = msg.get("text","")
                tts.say(str(txt))
                log("TTS", "say('%s')" % txt)

            # ── Idioma TTS ────────────────────────────────────────────────────
            elif action == "language":
                lang = msg.get("value","")
                try:
                    tts.setLanguage(str(lang))
                    log("TTS", "setLanguage('%s')" % lang)
                except Exception as e:
                    log("WS", "Error setLanguage('%s'): %s" % (lang, e))

            # ── Autonomous Life ───────────────────────────────────────────────
            elif action == "autonomous":
                enable = bool(msg.get("enable", False))
                new_state = "interactive" if enable else "disabled"
                life.setState(new_state)
                log("Autonomous", "AutonomousLife.setState('%s')" % new_state)

            # ── Kick (ejecuta behavior si existe) ─────────────────────────────
            elif action == "kick":
                try:
                    behavior_name = "kicknao-f6eb94/behavior_1"
                    if behavior and behavior.isBehaviorInstalled(behavior_name):
                        for bhv in behavior.getRunningBehaviors():
                            behavior.stopBehavior(bhv)
                        behavior.runBehavior(behavior_name)
                        log("Kick", "Ejecutando kick behavior: '%s'" % behavior_name)
                    else:
                        log("WS", "⚠ Behavior kick no instalado: '%s'" % behavior_name)
                        installed = behavior.getInstalledBehaviors()
                        kicks = [b for b in installed if "kick" in b.lower()]
                        if kicks:
                            behavior.runBehavior(kicks[0])
                            log("Kick", "Ejecutando kick alternativo: '%s'" % kicks[0])
                        else:
                                log("WS", "⚠ No se encontró behavior de kick")
                except Exception as e:
                    log("WS", "Error ejecutando kick: %s" % e)

            # ── Volumen ─────────────────────────────────────────────────────
            elif action == "volume":
                vol = float(msg.get("value", 50))
                audio.setOutputVolume(vol)
                log("Audio", "AudioDevice.setOutputVolume(%.1f)" % vol)

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
                log("Battery","getBattery → %d%% low=%s full=%s"%(level,low,full))

            # ── Estado Autonomous Life ────────────────────────────────────────
            elif action == "getAutonomousLife":
                try:
                    current_state = life.getState()
                    is_enabled = current_state != "disabled"
                    self.sendMessage(json.dumps({"autonomousLifeEnabled": is_enabled}))
                    log("Autonomous","getAutonomousLife → enabled=%s"%(is_enabled))
                except Exception as e:
                    log("WS", "Error getAutonomousLife: %s" % e)
                    self.sendMessage(json.dumps({"autonomousLifeEnabled": False}))

            # ── Activar / configurar modo adaptativo ─────────────────────────
            elif action == "adaptiveGait":
                enable = bool(msg.get("enable", True))
                mode = str(msg.get("mode", ADAPTIVE["mode"]))
                ADAPTIVE["enabled"] = enable
                if mode in ("auto", "slippery"):
                    ADAPTIVE["mode"] = mode
                ADAPTIVE["last_event"] = 0.0  # reset suave
                self.sendMessage(json.dumps({"adaptiveGait": {"enabled": ADAPTIVE["enabled"], "mode": ADAPTIVE["mode"]}}))
                log("Adapt", "adaptiveGait → enabled=%s mode=%s" % (ADAPTIVE["enabled"], ADAPTIVE["mode"]))

            # ── Control LightGBM AutoML Adaptativo ───────────────────────────────
            elif action == "adaptiveLightGBM":
                try:
                    enable = msg.get("enabled", True)
                    if adaptive_walker:
                        # No hay enable/disable en LightGBM, simplemente habilitamos el modo adaptativo
                        ADAPTIVE["enabled"] = enable
                        stats = {}
                        if hasattr(adaptive_walker, 'get_stats'):
                            stats = adaptive_walker.get_stats()
                        self.sendMessage(json.dumps({
                            "adaptiveLightGBM": {
                                "enabled": enable,
                                "available": ADAPTIVE_WALK_ENABLED,
                                "stats": stats
                            }
                        }))
                        logger.info("LightGBM AutoML adaptativo {} - Stats: {}".format(
                            "habilitado" if enable else "deshabilitado", stats))
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

            # ── Compatibilidad con comando anterior ───────────────────────────────
            elif action == "adaptiveRandomForest":
                # Redirigir a adaptiveLightGBM para compatibilidad
                new_msg = msg.copy()
                new_msg["command"] = "adaptiveLightGBM"
                # Procesar como LightGBM
                try:
                    enable = new_msg.get("enabled", True)
                    if adaptive_walker:
                        ADAPTIVE["enabled"] = enable
                        stats = {}
                        if hasattr(adaptive_walker, 'get_stats'):
                            stats = adaptive_walker.get_stats()
                        # Responder con formato original para compatibilidad
                        self.sendMessage(json.dumps({
                            "adaptiveRandomForest": {
                                "enabled": enable,
                                "available": ADAPTIVE_WALK_ENABLED,
                                "stats": stats,
                                "upgraded_to": "LightGBM"
                            }
                        }))
                        logger.info("RandomForest (ahora LightGBM) adaptativo {} - Stats: {}".format(
                            "habilitado" if enable else "deshabilitado", stats))
                    else:
                        self.sendMessage(json.dumps({
                            "adaptiveRandomForest": {
                                "enabled": False,
                                "available": False,
                                "error": "LightGBM AutoML no disponible"
                            }
                        }))
                        logger.warning("LightGBM AutoML adaptativo no disponible")
                except Exception as e:
                    logger.error("Error controlando LightGBM: {}".format(e))
                    self.sendMessage(json.dumps({"adaptiveRandomForest": {"error": str(e)}}))

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

            # ── Compatibilidad estadísticas RandomForest ──────────────────────────
            elif action == "getRandomForestStats":
                try:
                    if adaptive_walker:
                        stats = {}
                        if hasattr(adaptive_walker, 'get_stats'):
                            stats = adaptive_walker.get_stats()
                        # Responder con formato original pero datos de LightGBM
                        stats["upgraded_to"] = "LightGBM"
                        self.sendMessage(json.dumps({"randomForestStats": stats}))
                        logger.debug("Estadísticas RandomForest (ahora LightGBM) enviadas: {}".format(stats))
                    else:
                        self.sendMessage(json.dumps({"randomForestStats": {"available": False, "upgraded_to": "LightGBM"}}))
                except Exception as e:
                    logger.error("Error obteniendo estadísticas RandomForest: {}".format(e))
                    self.sendMessage(json.dumps({"randomForestStats": {"error": str(e)}}))

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
                        log("DataLogger", "Logging iniciado: {} ({}s @ {}Hz)".format(output_file, duration, frequency))
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
                    log("DataLogger", "Logging detenido. Muestras: {}".format(samples_written))
                    
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
                    
            # ── Sistema Golden Parameters ──────────────────────────────────────────
            elif action == "getGoldenLockStatus":
                """Obtener estado actual del sistema de golden lock"""
                try:
                    is_locked, golden_params = _check_golden_lock()
                    
                    response = {
                        "goldenLockStatus": {
                            "locked": is_locked,
                            "parameters": golden_params if is_locked else None,
                            "lock_file_exists": os.path.exists(os.path.join(os.path.dirname(__file__), "golden_params_lock.json"))
                        }
                    }
                    self.sendMessage(json.dumps(response))
                    logger.debug("Estado golden lock enviado: locked={}".format(is_locked))
                    
                except Exception as e:
                    logger.error("Error obteniendo estado golden lock: {}".format(e))
                    self.sendMessage(json.dumps({"goldenLockStatus": {"error": str(e)}}))
                    
            elif action == "unlockGoldenParams":
                """Forzar unlock de parámetros golden"""
                try:
                    lock_file = os.path.join(os.path.dirname(__file__), "golden_params_lock.json")
                    
                    if os.path.exists(lock_file):
                        os.remove(lock_file)
                        logger.info("Golden parameters lock removido manualmente")
                        response = {"unlockGoldenParams": {"success": True, "message": "Lock removido"}}
                    else:
                        response = {"unlockGoldenParams": {"success": False, "message": "No hay lock activo"}}
                    
                    self.sendMessage(json.dumps(response))
                    
                except Exception as e:
                    logger.error("Error removiendo golden lock: {}".format(e))
                    self.sendMessage(json.dumps({"unlockGoldenParams": {"success": False, "error": str(e)}}))
                    
            elif action == "setGoldenParams":
                """Establecer parámetros golden manualmente"""
                try:
                    # Obtener parámetros del mensaje
                    golden_params = msg.get("parameters", {})
                    duration_seconds = msg.get("duration", 3600)  # 1 hora por defecto
                    
                    if not golden_params:
                        response = {"setGoldenParams": {"success": False, "error": "No se proporcionaron parámetros"}}
                    else:
                        # Crear archivo de lock
                        lock_data = {
                            "locked": True,
                            "locked_parameters": golden_params,
                            "locked_at": time.time(),
                            "expires_at": time.time() + duration_seconds,
                            "source": "manual_websocket",
                            "force_unlock": False
                        }
                        
                        lock_file = os.path.join(os.path.dirname(__file__), "golden_params_lock.json")
                        with open(lock_file, 'w') as f:
                            json.dump(lock_data, f, indent=2)
                        
                        logger.info("Golden parameters establecidos manualmente: {}".format(golden_params))
                        response = {
                            "setGoldenParams": {
                                "success": True,
                                "parameters": golden_params,
                                "duration": duration_seconds
                            }
                        }
                    
                    self.sendMessage(json.dumps(response))
                    
                except Exception as e:
                    logger.error("Error estableciendo golden parameters: {}".format(e))
                    self.sendMessage(json.dumps({"setGoldenParams": {"success": False, "error": str(e)}}))

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
