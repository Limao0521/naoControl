#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
walk_ws_server.py
────────────────────────────────────────────────────────────────────────
• Escucha WebSocket en 0.0.0.0:6671
• Recibe ASCII "walk vx vy wz" 
• Llama a ALMotion.moveToward(vx, vy, wz)
• Watch-dog detiene al robot si pasan > WATCHDOG s sin comandos

Pensado para Python 2.7 en el NAO. Solo depende de SimpleWebSocketServer.py
(colócalo en la misma carpeta).
"""

import sys, os, time, math, threading
from naoqi import ALProxy

# Hacer que importe el módulo local SimpleWebSocketServer.py
sys.path.insert(0, os.path.dirname(__file__))
from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer

# ───────── CONFIGURACIÓN ───────────────────────────────────────────
IP_NAO   = "127.0.0.1"   # IP del NAO si corre local; ajústalo si es remoto
PORT_NAO = 9559          # Puerto NAOqi
WS_PORT  = 6671          # Debe coincidir con logic.js
WATCHDOG = 0.6           # Segundos sin datos → stopMove()

# ───────── INICIALIZACIÓN NAOqi ────────────────────────────────────
motion  = ALProxy("ALMotion",         IP_NAO, PORT_NAO)
life    = ALProxy("ALAutonomousLife", IP_NAO, PORT_NAO)
posture = ALProxy("ALRobotPosture",   IP_NAO, PORT_NAO)

# Desactivar comportamientos automáticos y activar servos
life.setState("disabled")
motion.setStiffnesses("Body", 1.0)
posture.goToPosture("Stand", 0.5)

# Hora del último comando recibido
last_cmd = time.time()

# ───────── MANEJADOR WebSocket ─────────────────────────────────────
class WalkWS(WebSocket):
    """Cada vez que un cliente WS se conecta, instancia esta clase."""

    def handleConnected(self):
        # Imprimir dirección del cliente que se conecta
        print("[WS] Cliente conectado desde {}:{}".format(
            self.address[0], self.address[1]))

    def handleClose(self):
        # Avisar cuando el cliente cierra la conexión
        print("[WS] Cliente desconectado {}".format(
            "{}:{}".format(self.address[0], self.address[1])))

    def handleMessage(self):
        """Procesa cada mensaje entrante de texto."""
        global last_cmd

        data = self.data.strip()
        # Log de la petición completa
        print("[WS] Petición recibida: '{}'".format(data))

        parts = data.split()
        # Validar sintaxis: 4 tokens y primer token "walk"
        if len(parts) != 4 or parts[0] != "walk":
            print("[WS]   Ignorando: formato inválido")
            return

        # Convertir tokens a float
        try:
            vx = float(parts[1])
            vy = float(parts[2])
            wz = float(parts[3])
        except ValueError:
            print("[WS]   Ignorando: valores no numéricos")
            return

        # Normalizar plano para que la velocidad lineal ≤ 1.0
        norm = math.hypot(vx, vy)
        if norm > 1.0:
            vx = vx / norm
            vy = vy / norm
            print("[WS]   Normalizado a vx={:.2f}, vy={:.2f}".format(vx, vy))

        # Ejecutar comando de movimiento
        try:
            motion.moveToward(vx, vy, wz)
            print("[WS] Enviado moveToward({}, {}, {})".format(
                round(vx,2), round(vy,2), round(wz,2)))
        except Exception as e:
            print("[WS] ERROR en moveToward:", e)

        # Actualizar temporizador del watchdog
        last_cmd = time.time()

# ───────── WATCHDOG EN HILO ────────────────────────────────────────
def watchdog_loop():
    """Detiene al robot si no llegan comandos durante WATCHDOG segundos."""
    global last_cmd
    while True:
        time.sleep(0.05)
        if time.time() - last_cmd > WATCHDOG:
            motion.stopMove()
            print("[Watchdog] Sin datos >{:.2f}s ⇒ stopMove()".format(WATCHDOG))
            last_cmd = time.time()

# Crear hilo demonio para el watchdog (compatible con Python 2.7)
wd = threading.Thread(target=watchdog_loop)
wd.setDaemon(True)
wd.start()

# ───────── SERVIDOR WEBSOCKET ─────────────────────────────────────
server = SimpleWebSocketServer("", WS_PORT, WalkWS)
print("[walk_ws_server] Escuchando WebSocket en ws://0.0.0.0:{}".format(WS_PORT))

try:
    # Bucle principal: atiende conexiones entrantes indefinidamente
    server.serveforever()
except KeyboardInterrupt:
    # Ctrl-C → parar motores y salir
    motion.stopMove()
    print("\n[walk_ws_server] Interrumpido: motores detenidos")
