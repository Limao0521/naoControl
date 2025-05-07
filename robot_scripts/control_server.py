#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server.py – WebSocket → NAOqi dispatcher
• ws://0.0.0.0:6671
• JSON actions: walk, move, posture, led, say
• Watchdog detiene la marcha si no recibe walk en WATCHDOG s
"""

from __future__ import print_function
import sys, os, time, math, threading, json, socket, errno
from datetime import datetime
from naoqi import ALProxy

# Incluir SimpleWebSocketServer.py local
sys.path.insert(0, os.path.dirname(__file__))
from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer

# Configuración
IP_NAO    = "127.0.0.1"
PORT_NAO  = 9559
WS_PORT   = 6671
WATCHDOG  = 0.6

def log(tag, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print("{0} [{1}] {2}".format(ts, tag, msg))

# Proxies NAOqi
motion  = ALProxy("ALMotion",         IP_NAO, PORT_NAO)
posture = ALProxy("ALRobotPosture",   IP_NAO, PORT_NAO)
life    = ALProxy("ALAutonomousLife", IP_NAO, PORT_NAO)
leds    = ALProxy("ALLeds",           IP_NAO, PORT_NAO)
tts     = ALProxy("ALTextToSpeech",   IP_NAO, PORT_NAO)
battery = ALProxy("ALBattery",        IP_NAO, PORT_NAO)
# eliminamos ALMemory/getInfo problemático

# Setup inicial
life.setState("disabled")
motion.setStiffnesses("Body", 1.0)
log("NAO", "AutonomousLife disabled; Body stiffness ON")

last_walk = time.time()

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
                vx = float(msg.get("vx",0.0))
                vy = float(msg.get("vy",0.0))
                wz = float(msg.get("wz",0.0))
                norm = math.hypot(vx, vy)
                if norm>1.0:
                    vx,vy = vx/norm, vy/norm
                motion.moveToward(vx, vy, wz)
                last_walk = time.time()
                log("SIM", "moveToward(vx=%.2f,vy=%.2f,wz=%.2f)" % (vx,vy,wz))

            elif action == "move":
                joint = msg.get("joint","")
                val   = float(msg.get("value",0.0))
                # usamos overload escalar
                motion.setAngles(str(joint), val, 0.1)
                log("SIM", "setAngles('%s', %.2f)" % (joint,val))

            elif action == "posture":
                pst = msg.get("value","Stand")
                posture.goToPosture(str(pst), 0.7)
                log("SIM", "goToPosture('%s')" % pst)

            elif action == "led":
                grp = msg.get("group","ChestLeds")
                # asegurar str
                if isinstance(grp, unicode):
                    grp = grp.encode('utf-8')
                r = float(msg.get("r",0.0))
                g = float(msg.get("g",0.0))
                b = float(msg.get("b",0.0))
                leds.fadeRGB(grp, r, g, b, 0.0)
                log("SIM", "fadeRGB('%s',%.2f,%.2f,%.2f)" % (grp,r,g,b))

            elif action == "say":
                txt = msg.get("text","")
                tts.say(str(txt))
                log("SIM", "say('%s')" % txt)

            else:
                log("WS", "⚠ Acción desconocida '%s'" % action)

        except Exception as e:
            log("WS", "Excepción en %s: %s" % (action, e))


# Watchdog para stopMove
def watchdog():
    global last_walk
    log("Watchdog","Iniciado (%.1fs)"%WATCHDOG)
    while True:
        time.sleep(0.05)
        if time.time() - last_walk > WATCHDOG:
            motion.stopMove()
            last_walk = time.time()
            log("Watchdog","stopMove() tras timeout")

wd = threading.Thread(target=watchdog)
wd.setDaemon(True)
wd.start()

# Servidor WS (reintenta si el puerto está ocupado)
if __name__ == "__main__":
    log("Server","Iniciando WS en ws://0.0.0.0:%d" % WS_PORT)
    while True:
        try:
            srv = SimpleWebSocketServer("", WS_PORT, RobotWS)
            break
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:
                log("Server","⚠ Puerto %d ocupado, reintentando en 3s…" % WS_PORT)
                time.sleep(3)
            else:
                raise
    srv.serveforever()
