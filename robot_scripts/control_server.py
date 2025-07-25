#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server.py – WebSocket → NAOqi dispatcher + Head‐Touch Web‐Launcher

• ws://0.0.0.0:6671
• JSON actions: walk, move, posture, led, say, language
• Watchdog detiene la marcha si no recibe walk en WATCHDOG s
• Pulsar head tactile togglea el servidor HTTP en puerto 8000
"""

from __future__ import print_function
import sys, os, time, math, threading, json, socket, errno, subprocess, signal
from datetime import datetime
from naoqi import ALProxy

# Añadir carpeta local para SimpleWebSocketServer.py
sys.path.insert(0, os.path.dirname(__file__))
from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer

# — Configuración general —
IP_NAO     = "127.0.0.1"
PORT_NAO   = 9559
WS_PORT    = 6671
WATCHDOG   = 0.6
WEB_DIR    = "/home/nao/controll/ControllerWebServer"
HTTP_PORT  = "8000"

def log(tag, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print("{0} [{1}] {2}".format(ts, tag, msg))
    
# Proxies NAOqi
motion     = ALProxy("ALMotion",         IP_NAO, PORT_NAO)
posture    = ALProxy("ALRobotPosture",   IP_NAO, PORT_NAO)
life       = ALProxy("ALAutonomousLife", IP_NAO, PORT_NAO)
leds       = ALProxy("ALLeds",           IP_NAO, PORT_NAO)
tts        = ALProxy("ALTextToSpeech",   IP_NAO, PORT_NAO)
battery    = ALProxy("ALBattery",        IP_NAO, PORT_NAO)
memory     = ALProxy("ALMemory",         IP_NAO, PORT_NAO)
audio      = ALProxy("ALAudioDevice",    IP_NAO, PORT_NAO)   

# ─── Fall Recovery ────────────────────────────────────────────────────
# Habilita el manejador de caídas para que el robot se levante solo
motion.setFallManagerEnabled(True)
log("NAO", "Fall manager ENABLED → auto-recover ON")

def onFall(_key, _value, _msg):
    log("FallEvt", "detected! Recuperando postura...")
    posture.goToPosture("Stand", 0.7)

# Registrar callback
memory.subscribeToEvent("RobotHasFallen", __name__, "onFall")
# ───────────────────────────────────────────────────

# Estado global del proceso HTTP
web_proc = None

# Limpieza al matar el servidor
def cleanup(signum, frame):
    global web_proc
    log("Server", "Recibido señal {}, limpiando…".format(signum))
    if web_proc:
        web_proc.terminate()
        web_proc.wait()
        log("Launcher", "HTTP server detenido (pid {}).".format(web_proc.pid))
    sys.exit(0)

signal.signal(signal.SIGINT,  cleanup)
signal.signal(signal.SIGTERM, cleanup)

# Setup NAO
life.setState("disabled")
motion.setStiffnesses("Body", 1.0)
log("NAO", "AutonomousLife disabled; Body stiffness ON")

# Watchdog para detener movimiento
last_walk = time.time()
def watchdog():
    global last_walk
    log("Watchdog", "Iniciado (%.1fs)" % WATCHDOG)
    while True:
        time.sleep(0.05)
        if time.time() - last_walk > WATCHDOG:
            motion.stopMove()
            last_walk = time.time()
            log("Watchdog", "stopMove() tras timeout")

            

wd = threading.Thread(target=watchdog)
wd.setDaemon(True)
wd.start()

# WebSocket handler
class RobotWS(WebSocket):
    def handleConnected(self):
        log("WS", "Conectado %s" % (self.address,))
    def handleClose(self):
        log("WS", "Desconectado %s" % (self.address,))
    def handleMessage(self):
        global last_walk
        raw = self.data.strip()
        log("WS", "Recibido RAW: %s" % raw)
        try:
            msg = json.loads(raw)
        except Exception as e:
            log("WS", "JSON inválido: %s (%s)" % (raw, e))
            return

        action = msg.get("action")
        try:
            if action == "walk":
                vx, vy, wz = map(float, (msg.get("vx",0), msg.get("vy",0), msg.get("wz",0)))
                norm = math.hypot(vx, vy)
                if norm > 1.0:
                    vx, vy = vx/norm, vy/norm
                motion.moveToward(vx, vy, wz)
                last_walk = time.time()
                log("SIM", "moveToward(vx=%.2f,vy=%.2f,wz=%.2f)" % (vx,vy,wz))

            elif action == "move":
                joint = msg.get("joint","")
                val   = float(msg.get("value",0))
                motion.setAngles(str(joint), val, 0.1)
                log("SIM", "setAngles('%s',%.2f)" % (joint,val))

            elif action == "posture":
                pst = msg.get("value","Stand")
                posture.goToPosture(str(pst), 0.7)
                log("SIM", "goToPosture('%s')" % pst)

            elif action == "led":
                grp = msg.get("group","ChestLeds")
                if isinstance(grp, unicode): grp = grp.encode('utf-8')
                r, g, b = map(float, (msg.get("r",0), msg.get("g",0), msg.get("b",0)))
                leds.fadeRGB(grp, r, g, b, 0.0)
                log("SIM", "fadeRGB('%s',%.2f,%.2f,%.2f)" % (grp,r,g,b))

            elif action == "say":
                txt = msg.get("text","")
                tts.say(str(txt))
                log("SIM", "say('%s')" % txt)

            elif action == "language":
                lang = msg.get("value","")
                try:
                    tts.setLanguage(str(lang))
                    log("SIM", "setLanguage('%s')" % lang)
                except Exception as e:
                    log("WS", "Error setLanguage('%s'): %s" % (lang, e))

            elif action == "autonomous":
                enable = bool(msg.get("enable", False))
                # “interactive” habilita Autonomous Life; “disabled” lo apaga
                new_state = "interactive" if enable else "disabled"
                life.setState(new_state)
                log("SIM", "AutonomousLife.setState('%s')" % new_state)
            elif action == "volume":
                vol = float(msg.get("value", 50))
                audio.setOutputVolume(vol)
                
                log("SIM", "AudioDevice.setOutputVolume(%.1f)" % vol)

            else:
                log("WS", "⚠ Acción desconocida '%s'" % action)

        except Exception as e:
            log("WS", "Excepción en %s: %s" % (action, e))

# Arranque del servidor WebSocket con reintento si el puerto está ocupado
if __name__ == "__main__":
    log("Server", "Iniciando WS en ws://0.0.0.0:%d" % WS_PORT)
    while True:
        try:
            srv = SimpleWebSocketServer("", WS_PORT, RobotWS)
            break
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:
                log("Server", "⚠ Puerto %d ocupado, reintentando en 3s…" % WS_PORT)
                time.sleep(3)
            else:
                raise
    srv.serveforever()
