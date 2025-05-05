#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server.py – WebSocket → NAOqi dispatcher

• ws://0.0.0.0:6671
• JSON actions: walk, move, posture, led, say, getInfo
• Watchdog detiene la marcha si no recibe walk en WATCHDOG s
"""

from __future__ import print_function
import sys, os, time, math, threading, json
from datetime import datetime
from naoqi import ALProxy

# Incluir SimpleWebSocketServer.py local
sys.path.insert(0, os.path.dirname(__file__))
from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer

# Configuración
IP_NAO   = "127.0.0.1"
PORT_NAO = 9559
WS_PORT  = 6671
WATCHDOG = 0.6

def log(tag, msg):
    """Timestamp + etiqueta."""
    ts = datetime.now().strftime("%H:%M:%S")
    print("{0} [{1}] {2}".format(ts, tag, msg))

# Inicializar proxies NAOqi
motion  = ALProxy("ALMotion",         IP_NAO, PORT_NAO)
life    = ALProxy("ALAutonomousLife", IP_NAO, PORT_NAO)
leds    = ALProxy("ALLeds",           IP_NAO, PORT_NAO)
tts     = ALProxy("ALTextToSpeech",   IP_NAO, PORT_NAO)
battery = ALProxy("ALBattery",        IP_NAO, PORT_NAO)
memory  = ALProxy("ALMemory",         IP_NAO, PORT_NAO)

# Setup inicial
life.setState("disabled")
motion.setStiffnesses("Body", 1.0)
log("NAO", "AutonomousLife disabled; Body stiffness ON")

last_walk = time.time()

class RobotWS(WebSocket):
    def handleConnected(self):
        log("WS", "Conectado {}".format(self.address))

    def handleClose(self):
        log("WS", "Desconectado {}".format(self.address))

    def handleMessage(self):
        global last_walk
        raw = self.data.strip()
        log("WS", "Recibido RAW: {}".format(raw))

        # Parsear JSON
        try:
            msg = json.loads(raw)
        except Exception as e:
            log("WS", "JSON inválido: {} ({})".format(raw, e))
            return

        action = msg.get("action")

        if action == "walk":
            vx = float(msg.get("vx", 0.0))
            vy = float(msg.get("vy", 0.0))
            wz = float(msg.get("wz", 0.0))
            norm = math.hypot(vx, vy)
            if norm > 1.0:
                vx, vy = vx/norm, vy/norm
                log("WS", "walk normalizado a vx={:.2f}, vy={:.2f}".format(vx,vy))
            motion.moveToward(vx, vy, wz)
            last_walk = time.time()
            log("SIM", "moveToward(vx={:.2f},vy={:.2f},wz={:.2f})".format(vx,vy,wz))

        elif action == "move":
            joint = msg.get("joint")
            val   = float(msg.get("value", 0.0))
            motion.setAngles(joint, val, 0.1)
            log("SIM", "setAngles('{}',{:.2f},speed=0.1)".format(joint,val))

        elif action == "posture":
            posture = msg.get("value")
            motion.goToPosture(posture, 0.5)
            log("SIM", "goToPosture('{}',speed=0.5)".format(posture))

        elif action == "led":
            group = msg.get("group", "ChestLeds")
            r, g, b = float(msg.get("r",0)), float(msg.get("g",0)), float(msg.get("b",0))
            leds.fadeRGB(group, r, g, b, 0.0)
            log("SIM", "fadeRGB('{}',{:.2f},{:.2f},{:.2f},t=0)".format(group,r,g,b))

        elif action == "say":
            text = msg.get("text","")
            tts.say(text)
            log("SIM", "say('{}')".format(text))

        elif action == "getInfo":
            batt = battery.getBatteryCharge()
            pos  = motion.getAngles("Body", True)
            temp = memory.getListData("Device/SubDeviceList/Body/Temperature/Sensor/Value")
            joints = motion.getJointNames("Body")
            info = {
                "battery": batt,
                "joints": {
                    j: {"pos": pos[i], "temp": temp[i]}
                    for i,j in enumerate(joints)
                }
            }
            payload = json.dumps({"info":info})
            self.sendMessage(payload)
            log("SIM", "getInfo → enviado info de {} joints".format(len(joints)))

        else:
            log("WS", "⚠ Acción desconocida '{}'".format(action))


# Watchdog para stopMove
def watchdog():
    global last_walk
    log("Watchdog", "Iniciado ({}s)".format(WATCHDOG))
    while True:
        time.sleep(0.05)
        if time.time() - last_walk > WATCHDOG:
            motion.stopMove()
            last_walk = time.time()
            log("Watchdog", "stopMove() invoked after timeout")

# Arrancar watchdog
wd = threading.Thread(target=watchdog)
wd.setDaemon(True)
wd.start()

# Iniciar WebSocket server
if __name__ == "__main__":
    log("Server", f"Iniciando WS en ws://0.0.0.0:{WS_PORT}")
    srv = SimpleWebSocketServer("", WS_PORT, RobotWS)
    srv.serveforever()
