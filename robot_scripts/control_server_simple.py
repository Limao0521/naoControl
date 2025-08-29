#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server_simple.py – Versión simplificada para evitar desconexiones

• ws://0.0.0.0:6671
• JSON actions: walk, walkTo, move, posture, say, kick, turnLeft, turnRight
• Sin respuestas automáticas para evitar conflictos
• Manejo mínimo de errores
"""

import sys
import os
import time
import math
import threading
import json
import socket
import signal

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
def log(tag, msg):
    print("[%s] %s" % (tag, msg))

def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))

def dict_to_pairs(d):
    return [[k, v] for k, v in d.items()]

# ─── Variables globales ───────────────────────────────────────────────────────
# Proxies NAOqi
motion_proxy = None
posture_proxy = None
tts_proxy = None
leds_proxy = None
autonomous_proxy = None
audio_proxy = None
battery_proxy = None
memory_proxy = None

# Estado del robot
_last_walk = [0.0, 0.0, 0.0]
CURRENT_GAIT = {
    "MaxStepX": 0.04,
    "MaxStepY": 0.14, 
    "MaxStepTheta": 0.4,
    "StepHeight": 0.02,
    "Frequency": 0.5
}

CAPS_APPLIED = {"vx": 1.0, "vy": 1.0, "wz": 1.0}
CAPS_REF = {"vx": 1.0, "vy": 1.0, "wz": 1.0}
GAIT_APPLIED = dict_to_pairs(CURRENT_GAIT)
GAIT_REF = dict(CURRENT_GAIT)

CAPS_UP_RATE = 0.02
CAPS_DOWN_RATE = 0.04

# ─── Inicialización NAOqi ─────────────────────────────────────────────────────
def init_naoqi():
    global motion_proxy, posture_proxy, tts_proxy, leds_proxy
    global autonomous_proxy, audio_proxy, battery_proxy, memory_proxy
    
    try:
        motion_proxy = ALProxy("ALMotion")
        posture_proxy = ALProxy("ALRobotPosture")
        tts_proxy = ALProxy("ALTextToSpeech")
        leds_proxy = ALProxy("ALLeds")
        autonomous_proxy = ALProxy("ALAutonomousLife")
        audio_proxy = ALProxy("ALAudioDevice")
        battery_proxy = ALProxy("ALBattery")
        memory_proxy = ALProxy("ALMemory")
        
        log("NAOqi", "✓ Todos los proxies inicializados")
        return True
    except Exception as e:
        log("NAOqi", "Error inicializando: %s" % e)
        return False

# ─── WebSocket Handler simplificado ──────────────────────────────────────────
class SimpleRobotWS(WebSocket):
    def handleMessage(self):
        global _last_walk, CURRENT_GAIT, CAPS_APPLIED, GAIT_REF, CAPS_REF
        
        try:
            raw = self.data.strip()
            log("WS", "Recibido: %s" % raw)
            
            msg = json.loads(raw)
            action = msg.get("action")
            
            if not action:
                log("WS", "No action especificado")
                return
            
            # ── ACCIONES BÁSICAS ──────────────────────────────────────────────
            if action == "walk":
                vx = float(msg.get("vx", 0))
                vy = float(msg.get("vy", 0))
                wz = float(msg.get("wz", 0))
                
                # Normalizar si excede 1.0
                norm = math.hypot(vx, vy)
                if norm > 1.0:
                    vx, vy = vx/norm, vy/norm
                
                # Aplicar caps
                vx *= CAPS_APPLIED["vx"]
                vy *= CAPS_APPLIED["vy"] 
                wz *= CAPS_APPLIED["wz"]
                
                _last_walk = [vx, vy, wz]
                if motion_proxy:
                    motion_proxy.moveToward(vx, vy, wz)
                log("Walk", "→ (%.2f, %.2f, %.2f)" % (vx, vy, wz))
            
            elif action == "walkTo":
                x = float(msg.get("x", 0))
                y = float(msg.get("y", 0))
                theta = float(msg.get("theta", 0))
                if motion_proxy:
                    motion_proxy.walkTo(x, y, theta)
                log("WalkTo", "→ (%.2f, %.2f, %.2f)" % (x, y, theta))
            
            elif action == "move":
                chain = msg.get("chain", "")
                angles = msg.get("angles", [])
                times = msg.get("times", [])
                absolute = msg.get("absolute", True)
                
                if motion_proxy and chain and angles and times:
                    motion_proxy.angleInterpolation(chain, angles, times, absolute)
                log("Move", "%s → %s" % (chain, angles))
            
            elif action == "posture":
                posture_name = msg.get("name", "Stand")
                speed = msg.get("speed", 0.5)
                if posture_proxy:
                    posture_proxy.goToPosture(posture_name, speed)
                log("Posture", "%s (speed=%.1f)" % (posture_name, speed))
            
            elif action == "say":
                text = msg.get("text", "")
                if tts_proxy and text:
                    tts_proxy.say(text)
                log("TTS", "Diciendo: '%s'" % text)
            
            elif action == "kick":
                leg = msg.get("leg", "RLeg")
                if motion_proxy:
                    if leg == "RLeg":
                        motion_proxy.setAngles("RKneePitch", 2.0, 0.5)
                        time.sleep(0.5)
                        motion_proxy.setAngles("RKneePitch", 0.5, 0.3)
                    else:
                        motion_proxy.setAngles("LKneePitch", 2.0, 0.5)
                        time.sleep(0.5)
                        motion_proxy.setAngles("LKneePitch", 0.5, 0.3)
                log("Kick", "Patada con %s" % leg)
            
            elif action == "turnLeft":
                angle = float(msg.get("angle", 0.5))
                if motion_proxy:
                    motion_proxy.moveTo(0, 0, angle)
                log("Turn", "Izquierda %.2f rad" % angle)
            
            elif action == "turnRight":
                angle = float(msg.get("angle", -0.5))
                if motion_proxy:
                    motion_proxy.moveTo(0, 0, angle)
                log("Turn", "Derecha %.2f rad" % angle)
            
            elif action == "gait":
                new_gait = msg.get("gait", {})
                GAIT_REF.update(new_gait)
                log("Gait", "Nuevo: %s" % new_gait)
            
            elif action == "caps":
                new_caps = msg.get("caps", {})
                CAPS_REF.update(new_caps)
                log("Caps", "Nuevas: %s" % new_caps)
            
            elif action == "autonomous":
                enabled = msg.get("enabled", True)
                if autonomous_proxy:
                    if enabled:
                        autonomous_proxy.setState("solitary")
                    else:
                        autonomous_proxy.setState("disabled")
                log("Autonomous", "Estado: %s" % ("enabled" if enabled else "disabled"))
            
            elif action == "led":
                name = msg.get("name", "")
                color = msg.get("color", 0x00FF00)
                duration = msg.get("duration", 1.0)
                if leds_proxy and name:
                    leds_proxy.fadeRGB(name, color, duration)
                log("LED", "%s → 0x%06X" % (name, color))
            
            elif action == "volume":
                level = int(msg.get("level", 50))
                if audio_proxy:
                    audio_proxy.setOutputVolume(level)
                log("Audio", "Volumen: %d" % level)
            
            # ── CONSULTAS CON RESPUESTA ───────────────────────────────────────
            elif action == "getGait":
                response = {"currentGait": CURRENT_GAIT}
                self.sendMessage(json.dumps(response))
            
            elif action == "getCaps":
                response = {"currentCaps": CAPS_APPLIED}
                self.sendMessage(json.dumps(response))
            
            elif action == "getConfig":
                config = {
                    "gait": CURRENT_GAIT,
                    "caps": CAPS_APPLIED,
                    "lastWalk": _last_walk
                }
                response = {"config": config}
                self.sendMessage(json.dumps(response))
            
            elif action == "getBattery":
                battery_level = 100
                if battery_proxy:
                    try:
                        battery_level = battery_proxy.getBatteryCharge()
                    except:
                        pass
                response = {"battery": battery_level}
                self.sendMessage(json.dumps(response))
            
            elif action == "getAutonomousLife":
                state = "unknown"
                if autonomous_proxy:
                    try:
                        state = autonomous_proxy.getState()
                    except:
                        pass
                response = {"autonomousLife": state}
                self.sendMessage(json.dumps(response))
            
            else:
                log("WS", "⚠ Acción desconocida: %s" % action)
        
        except Exception as e:
            log("WS", "Error procesando mensaje: %s" % e)
    
    def handleConnected(self):
        log("WS", "Cliente conectado desde %s" % self.address[0])
    
    def handleClose(self):
        log("WS", "Cliente desconectado desde %s" % self.address[0])

# ─── Bucle adaptativo simplificado ───────────────────────────────────────────
def simple_adaptive_loop():
    global GAIT_APPLIED, CAPS_APPLIED, GAIT_REF, CAPS_REF, CURRENT_GAIT
    
    while True:
        try:
            time.sleep(0.1)  # 10 Hz
            
            # Suavizar gait
            for k, target in GAIT_REF.items():
                current = CURRENT_GAIT.get(k, 0.0)
                delta = target - current
                if abs(delta) < 0.001:
                    CURRENT_GAIT[k] = target
                else:
                    CURRENT_GAIT[k] = current + delta * 0.1
            
            GAIT_APPLIED = dict_to_pairs(CURRENT_GAIT)
            
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
            log("Adaptive", "Error: %s" % e)

# ─── Cleanup ──────────────────────────────────────────────────────────────────
srv = None

def cleanup(signum=None):
    log("Main", "Limpiando y cerrando...")
    if srv:
        try:
            srv.close()
        except:
            pass
    sys.exit(0)

# ─── Función principal ────────────────────────────────────────────────────────
def main():
    global srv
    
    # Manejar señales
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Inicializar NAOqi
    if not init_naoqi():
        log("Main", "Continuando sin NAOqi...")
    
    # Iniciar bucle adaptativo
    adaptive_thread = threading.Thread(target=simple_adaptive_loop)
    adaptive_thread.daemon = True
    adaptive_thread.start()
    
    # Iniciar servidor WebSocket
    try:
        log("Server", "Iniciando servidor simple en puerto 6671...")
        srv = SimpleWebSocketServer('0.0.0.0', 6671, SimpleRobotWS)
        log("Server", "✓ Servidor simple iniciado en ws://0.0.0.0:6671")
        srv.serveforever()
    except KeyboardInterrupt:
        log("Server", "Interrupción detectada")
        cleanup()
    except Exception as e:
        log("Server", "Error fatal: %s" % e)
        cleanup()

if __name__ == "__main__":
    main()
