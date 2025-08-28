#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server.py – WebSocket → NAOqi dispatcher + Head‐Touch Web‐Launcher (single-config, adaptive gait)

• ws://0.0.0.0:6671
• JSON actions:
    walk, walkTo, move, gait, getGait, caps, getCaps, getConfig,
    footProtection, posture, led, say, language, autonomous, kick,
    volume, getBattery, getAutonomousLife,
    reloadPage, setAudio, setVideo, getWebStreams
    enableXGBoost, disableXGBoost, getXGBoostStats

Usa gait/caps por separado para caminar reactivo.
Head-touch → launcher web (auto-config IP).
Modo adaptativo XGBoost opcional para mejorar la marcha.
"""

import sys
import os
import time
import math
import threading
import json
import socket
import errno
import signal
import subprocess
import logging

# Configurar logger
logger = logging.getLogger(__name__)

# ─── Imports robóticos ────────────────────────────────────────────────────────
try:
    from naoqi import ALProxy
except ImportError:
    print("NAOqi no disponible; usando proxy dummy")
    class ALProxy:
        def __init__(self, service, ip="127.0.0.1", port=9559):
            self.service = service
            self.ip = ip
            self.port = port
        
        def __getattr__(self, name):
            def dummy_method(*args, **kwargs):
                print("[DUMMY %s] %s(*%s, **%s)" % (self.service, name, args, kwargs))
                return None
            return dummy_method

# ─── Imports de network ───────────────────────────────────────────────────────
try:
    from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer
except ImportError:
    print("SimpleWebSocketServer no disponible")
    sys.exit(1)

# ─── Funciones auxiliares ─────────────────────────────────────────────────────
def get_local_ips():
    import subprocess
    try:
        result = subprocess.check_output("hostname -I", shell=True)
        return result.strip().split()
    except:
        return ["127.0.0.1"]

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def log(tag, msg):
    print("[%s] %s" % (tag, msg))

def clamp(x, a, b):
    return max(a, min(b, x))

def dict_to_pairs(d):
    return [(k, d.get(k, 0.0)) for k in ("LHipRoll", "LHipPitch", "LKneePitch", "LAnklePitch", "LAnkleRoll", "RAnkleRoll", "RAnklePitch", "RKneePitch", "RHipPitch", "RHipRoll")]

# ─── Configuración NAOqi ──────────────────────────────────────────────────────
ROBOT_IP = os.environ.get("NAO_IP", "192.168.68.149")
ROBOT_PORT = int(os.environ.get("NAO_PORT", "9559"))

# ─── Variables globales ───────────────────────────────────────────────────────
# Estados del robot
motion_proxy = None
memory_proxy = None
tts_proxy = None
leds_proxy = None
battery_proxy = None
audio_proxy = None
posture_proxy = None
autonomous_proxy = None
fall_manager_proxy = None

# Estado de caminar
_last_walk = [0.0, 0.0, 0.0]

# Configuración de gait y caps
CURRENT_GAIT = {
    "LHipRoll": 0.0, "LHipPitch": 0.0, "LKneePitch": 0.0, "LAnklePitch": 0.0, "LAnkleRoll": 0.0,
    "RAnkleRoll": 0.0, "RAnklePitch": 0.0, "RKneePitch": 0.0, "RHipPitch": 0.0, "RHipRoll": 0.0
}

CAP_LIMITS = {"vx": 1.0, "vy": 1.0, "wz": 1.0}
GAIT_APPLIED = []
CAPS_APPLIED = {"vx": 1.0, "vy": 1.0, "wz": 1.0}
GAIT_REF = CURRENT_GAIT.copy()
CAPS_REF = CAP_LIMITS.copy()

# Configuración de adaptación
CAPS_UP_RATE = 0.01
CAPS_DOWN_RATE = 0.005

# XGBoost adaptativo
adaptive_walker = None

# ─── Inicialización NAOqi ─────────────────────────────────────────────────────
def init_naoqi():
    global motion_proxy, memory_proxy, tts_proxy, leds_proxy, battery_proxy
    global audio_proxy, posture_proxy, autonomous_proxy, fall_manager_proxy
    
    try:
        log("NAOqi", "Conectando a %s:%d..." % (ROBOT_IP, ROBOT_PORT))
        motion_proxy = ALProxy("ALMotion", ROBOT_IP, ROBOT_PORT)
        memory_proxy = ALProxy("ALMemory", ROBOT_IP, ROBOT_PORT)
        tts_proxy = ALProxy("ALTextToSpeech", ROBOT_IP, ROBOT_PORT)
        leds_proxy = ALProxy("ALLeds", ROBOT_IP, ROBOT_PORT)
        battery_proxy = ALProxy("ALBattery", ROBOT_IP, ROBOT_PORT)
        audio_proxy = ALProxy("ALAudioDevice", ROBOT_IP, ROBOT_PORT)
        posture_proxy = ALProxy("ALRobotPosture", ROBOT_IP, ROBOT_PORT)
        autonomous_proxy = ALProxy("ALAutonomousLife", ROBOT_IP, ROBOT_PORT)
        fall_manager_proxy = ALProxy("ALFallManager", ROBOT_IP, ROBOT_PORT)
        
        # Configurar parámetros de movimiento
        motion_proxy.setMotionConfig([["ENABLE_FOOT_CONTACT_PROTECTION", True]])
        
        log("NAOqi", "✓ Conexión establecida")
        return True
    except Exception as e:
        log("NAOqi", "✗ Error de conexión: %s" % e)
        return False

# ─── Callback de caída ────────────────────────────────────────────────────────
def onFall(eventName, value, subscriberIdentifier):
    log("Fall", "Robot caído: %s" % value)
    if value == 1:  # El robot se ha caído
        try:
            if motion_proxy:
                motion_proxy.stopMove()
                motion_proxy.rest()
            log("Fall", "Robot parado por caída")
        except Exception as e:
            log("Fall", "Error manejando caída: %s" % e)

# ─── XGBoost adaptativo ───────────────────────────────────────────────────────
def init_adaptive_walker():
    global adaptive_walker
    try:
        # Intentar cargar el módulo XGBoost adaptativo
        adaptive_walker_module = __import__("adaptive_walk_xgboost")
        adaptive_walker = adaptive_walker_module.AdaptiveWalkController(
            robot_ip=ROBOT_IP,
            robot_port=ROBOT_PORT
        )
        log("XGBoost", "✓ Controlador adaptativo inicializado")
        return True
    except Exception as e:
        log("XGBoost", "✗ Error inicializando adaptativo: %s" % e)
        return False

# ─── Bucle adaptativo ─────────────────────────────────────────────────────────
def adaptive_loop():
    global GAIT_APPLIED, CAPS_APPLIED, GAIT_REF, CAPS_REF
    
    while True:
        try:
            time.sleep(0.1)  # 10 Hz
            
            # Adaptar gait usando XGBoost si está disponible
            if adaptive_walker and hasattr(adaptive_walker, 'adapt_gait'):
                try:
                    new_gait = adaptive_walker.adapt_gait()
                    if new_gait:
                        GAIT_REF.update(new_gait)
                except Exception as e:
                    log("Adapt", "Error adaptando gait: %s" % e)
            
            # Aplicar cambios suaves en gait
            new_app = {}
            for k, target in GAIT_REF.items():
                current = CURRENT_GAIT.get(k, 0.0)
                delta = target - current
                if abs(delta) < 0.001:
                    new_app[k] = target
                else:
                    new_app[k] = current + delta * 0.1  # Suavizado
            
            CURRENT_GAIT.update(new_app)
            GAIT_APPLIED = dict_to_pairs(new_app)

            # CAPS: rampas por componente
            for k in ("vx","vy","wz"):
                a = CAPS_APPLIED.get(k, 1.0)
                b = CAPS_REF.get(k, 1.0)
                if a > b:
                    a = max(b, a - CAPS_DOWN_RATE)
                else:
                    a = min(b, a + CAPS_UP_RATE)
                CAPS_APPLIED[k] = clamp(a, 0.0, 1.0)

        except Exception as e:
            log("Adapt", "Error adaptive_loop: %s" % e)

# ─── Cleanup functions ────────────────────────────────────────────────────────
web_proc = None

def cleanup(signum, *args, **kwargs):
    cleanup_all_subscriptions()
    if web_proc:
        web_proc.terminate()
    sys.exit(0)

def cleanup_all_subscriptions():
    try:
        log("Cleanup", "Limpieza suscripciones NAOqi...")
        events_to_cleanup = ["RobotHasFallen","TouchChanged","FaceDetected",
                             "WordRecognized","SpeechDetected"]
        for event in events_to_cleanup:
            try:
                if memory_proxy:
                    memory_proxy.unsubscribeToEvent(event, "control_server")
            except:
                pass
        log("Cleanup", "✓ Suscripciones limpiadas")
    except Exception as e:
        log("Cleanup", "Error limpiando: %s" % e)

# ─── WebSocket Handler ────────────────────────────────────────────────────────
class RobotWS(WebSocket):
    def handleMessage(self):
        global _last_walk, CURRENT_GAIT, CAP_LIMITS, GAIT_APPLIED, CAPS_APPLIED, GAIT_REF, CAPS_REF
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
                # Normaliza magnitud del vector (x,y) si excede 1.0
                norm = math.hypot(vx, vy)
                if norm > 1.0:
                    vx, vy = vx/norm, vy/norm

                # Aplicar CAPS suavizados
                vx *= CAPS_APPLIED["vx"]
                vy *= CAPS_APPLIED["vy"]
                wz *= CAPS_APPLIED["wz"]

                _last_walk = [vx, vy, wz]
                if motion_proxy:
                    motion_proxy.moveToward(vx, vy, wz)
                log("Walk", "→ (%.2f, %.2f, %.2f)" % (vx, vy, wz))

            # ── Caminar a posición ────────────────────────────────────────────
            elif action == "walkTo":
                x = float(msg.get("x", 0))
                y = float(msg.get("y", 0))
                theta = float(msg.get("theta", 0))
                if motion_proxy:
                    motion_proxy.walkTo(x, y, theta)
                log("WalkTo", "→ (%.2f, %.2f, %.2f)" % (x, y, theta))

            # ── Mover cabeza/brazos ───────────────────────────────────────────
            elif action == "move":
                chain = msg.get("chain", "")
                angles = msg.get("angles", [])
                times = msg.get("times", [])
                absolute = msg.get("absolute", True)
                
                if motion_proxy and chain and angles and times:
                    motion_proxy.angleInterpolation(chain, angles, times, absolute)
                log("Move", "%s → %s" % (chain, angles))

            # ── Configurar gait ───────────────────────────────────────────────
            elif action == "gait":
                new_gait = msg.get("gait", {})
                GAIT_REF.update(new_gait)
                log("Gait", "Nuevo gait: %s" % new_gait)

            # ── Obtener gait actual ───────────────────────────────────────────
            elif action == "getGait":
                self.sendMessage(json.dumps({"currentGait": CURRENT_GAIT}))

            # ── Configurar caps ───────────────────────────────────────────────
            elif action == "caps":
                new_caps = msg.get("caps", {})
                CAPS_REF.update(new_caps)
                log("Caps", "Nuevas caps: %s" % new_caps)

            # ── Obtener caps actuales ─────────────────────────────────────────
            elif action == "getCaps":
                self.sendMessage(json.dumps({"currentCaps": CAPS_APPLIED}))

            # ── Obtener configuración ─────────────────────────────────────────
            elif action == "getConfig":
                config = {
                    "gait": CURRENT_GAIT,
                    "caps": CAPS_APPLIED,
                    "lastWalk": _last_walk
                }
                self.sendMessage(json.dumps({"config": config}))

            # ── Protección de pies ────────────────────────────────────────────
            elif action == "footProtection":
                enabled = msg.get("enabled", True)
                if motion_proxy:
                    motion_proxy.setMotionConfig([["ENABLE_FOOT_CONTACT_PROTECTION", enabled]])
                log("FootProt", "Protección: %s" % enabled)

            # ── Postura ───────────────────────────────────────────────────────
            elif action == "posture":
                posture_name = msg.get("name", "Stand")
                speed = msg.get("speed", 0.5)
                if posture_proxy:
                    posture_proxy.goToPosture(posture_name, speed)
                log("Posture", "%s (speed=%.1f)" % (posture_name, speed))

            # ── LEDs ──────────────────────────────────────────────────────────
            elif action == "led":
                name = msg.get("name", "")
                color = msg.get("color", 0x00FF00)
                duration = msg.get("duration", 1.0)
                if leds_proxy and name:
                    leds_proxy.fadeRGB(name, color, duration)
                log("LED", "%s → 0x%06X" % (name, color))

            # ── Texto a voz ───────────────────────────────────────────────────
            elif action == "say":
                text = msg.get("text", "")
                if tts_proxy and text:
                    tts_proxy.say(text)
                log("TTS", "Diciendo: '%s'" % text)

            # ── Idioma ────────────────────────────────────────────────────────
            elif action == "language":
                lang = msg.get("language", "Spanish")
                if tts_proxy:
                    tts_proxy.setLanguage(lang)
                log("TTS", "Idioma: %s" % lang)

            # ── Vida autónoma ─────────────────────────────────────────────────
            elif action == "autonomous":
                enabled = msg.get("enabled", True)
                if autonomous_proxy:
                    if enabled:
                        autonomous_proxy.setState("solitary")
                    else:
                        autonomous_proxy.setState("disabled")
                log("Autonomous", "Estado: %s" % ("enabled" if enabled else "disabled"))

            # ── Patada ────────────────────────────────────────────────────────
            elif action == "kick":
                leg = msg.get("leg", "RLeg")
                if motion_proxy:
                    # Implementación básica de patada
                    if leg == "RLeg":
                        motion_proxy.setAngles("RKneePitch", 2.0, 0.5)
                        time.sleep(0.5)
                        motion_proxy.setAngles("RKneePitch", 0.5, 0.3)
                    else:
                        motion_proxy.setAngles("LKneePitch", 2.0, 0.5)
                        time.sleep(0.5)
                        motion_proxy.setAngles("LKneePitch", 0.5, 0.3)
                log("Kick", "Patada con %s" % leg)

            # ── Volumen ───────────────────────────────────────────────────────
            elif action == "volume":
                level = int(msg.get("level", 50))
                if audio_proxy:
                    audio_proxy.setOutputVolume(level)
                log("Audio", "Volumen: %d" % level)

            # ── Batería ───────────────────────────────────────────────────────
            elif action == "getBattery":
                battery_level = 100  # Valor por defecto
                if battery_proxy:
                    try:
                        battery_level = battery_proxy.getBatteryCharge()
                    except:
                        pass
                self.sendMessage(json.dumps({"battery": battery_level}))

            # ── Estado vida autónoma ──────────────────────────────────────────
            elif action == "getAutonomousLife":
                state = "unknown"
                if autonomous_proxy:
                    try:
                        state = autonomous_proxy.getState()
                    except:
                        pass
                self.sendMessage(json.dumps({"autonomousLife": state}))

            # ── Control XGBoost Adaptativo ────────────────────────────────────
            elif action == "enableXGBoost":
                try:
                    if not adaptive_walker:
                        init_adaptive_walker()
                    
                    if adaptive_walker:
                        if hasattr(adaptive_walker, 'enable_adaptations'):
                            adaptive_walker.enable_adaptations()
                        self.sendMessage(json.dumps({
                            "adaptiveXGBoost": {
                                "enabled": True,
                                "status": "XGBoost adaptativo habilitado"
                            }
                        }))
                        logger.info("XGBoost adaptativo habilitado")
                    else:
                        self.sendMessage(json.dumps({
                            "adaptiveXGBoost": {
                                "enabled": False,
                                "error": "No se pudo inicializar XGBoost"
                            }
                        }))
                        logger.warning("XGBoost adaptativo no disponible")
                except Exception as e:
                    logger.error("Error habilitando XGBoost: {}".format(e))
                    self.sendMessage(json.dumps({"adaptiveXGBoost": {"error": str(e)}}))

            elif action == "disableXGBoost":
                try:
                    if adaptive_walker and hasattr(adaptive_walker, 'disable_adaptations'):
                        adaptive_walker.disable_adaptations()
                        self.sendMessage(json.dumps({
                            "adaptiveXGBoost": {
                                "enabled": False,
                                "status": "XGBoost adaptativo deshabilitado"
                            }
                        }))
                        logger.info("XGBoost adaptativo deshabilitado")
                    else:
                        self.sendMessage(json.dumps({
                            "adaptiveXGBoost": {
                                "enabled": False,
                                "error": "XGBoost no está inicializado"
                            }
                        }))
                        logger.warning("XGBoost adaptativo no disponible")
                except Exception as e:
                    logger.error("Error controlando XGBoost: {}".format(e))
                    self.sendMessage(json.dumps({"adaptiveXGBoost": {"error": str(e)}}))

            # ── Estadísticas XGBoost Adaptativo ───────────────────────────────
            elif action == "getXGBoostStats":
                try:
                    if adaptive_walker:
                        stats = {
                            "model_loaded": adaptive_walker.xgb_model.ok if hasattr(adaptive_walker, 'xgb_model') else False,
                            "adaptations_enabled": getattr(adaptive_walker, 'adaptations_enabled', True)
                        }
                        self.sendMessage(json.dumps({"xgboostStats": stats}))
                        logger.debug("Estadísticas XGBoost enviadas: {}".format(stats))
                    else:
                        self.sendMessage(json.dumps({"xgboostStats": {"available": False}}))
                except Exception as e:
                    logger.error("Error obteniendo estadísticas XGBoost: {}".format(e))
                    self.sendMessage(json.dumps({"xgboostStats": {"error": str(e)}}))

            else:
                log("WS", "⚠ Acción desconocida '%s'" % action)
                
        except Exception as e:
            log("WS", "Excepción en %s: %s" % (action, e))

    def handleConnected(self):
        log("WS", "Cliente conectado desde %s" % self.address[0])

    def handleClose(self):
        log("WS", "Cliente desconectado")

# ─── Función principal ────────────────────────────────────────────────────────
def main():
    global srv
    srv = None
    
    # Manejar señales de interrupción
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Inicializar NAOqi
    if not init_naoqi():
        log("Main", "Continuando sin NAOqi...")
    
    # Suscribirse a eventos de caída
    if memory_proxy:
        try:
            memory_proxy.subscribeToEvent("RobotHasFallen", "control_server", "onFall")
        except Exception as e:
            log("Main", "Error suscribiendo a RobotHasFallen: %s" % e)
    
    # Inicializar XGBoost adaptativo
    init_adaptive_walker()
    
    # Lanzar el hilo adaptativo
    adap = threading.Thread(target=adaptive_loop)
    adap.daemon = True
    adap.start()
    
    # Iniciar servidor WebSocket
    try:
        log("Server", "Iniciando servidor WebSocket en puerto 6671...")
        srv = SimpleWebSocketServer('0.0.0.0', 6671, RobotWS)
        log("Server", "✓ Servidor iniciado en ws://0.0.0.0:6671")
        srv.serveforever()
    except KeyboardInterrupt:
        log("Server", "Interrupción de teclado detectada")
        cleanup(None)
    except Exception as e:
        log("Server", "Error fatal: {}".format(e))
        sys.exit(1)
    finally:
        if srv:
            try:
                srv.close()
            except:
                pass

if __name__ == "__main__":
    main()
