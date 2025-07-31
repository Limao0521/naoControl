#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
launcher.py – Arranca/Detiene control_server.py + HTTP server
   con un long-press (>=5 s) del sensor táctil medio de la cabeza.
   Además, al iniciar pronuncia el mensaje de verificación.
"""

import time
import subprocess
import signal
import os
from naoqi import ALProxy

# — Configuración —
IP_NAO     = "127.0.0.1"
PORT_NAO   = 9559
PRESS_HOLD = 5.0            # segundos mínimos de pulsación
# Ajusta estas rutas según dónde tengas los scripts
CONTROL_PY = "/home/nao/scripts/control_server.py"
WEB_DIR    = "/home/nao/Webs/ControllerWebServer"
CAMERA_PY  = "/home/nao/scripts/video_stream.py"
HTTP_PORT  = "8000"

# Proxies NAOqi
memory = ALProxy("ALMemory", IP_NAO, PORT_NAO)
tts    = ALProxy("ALTextToSpeech", IP_NAO, PORT_NAO)

# Procesos externos; inicialmente ninguno
server_proc = None
http_proc   = None

def start_services():
    """Arranca control_server.py y el HTTP server."""
    global server_proc, http_proc
    if not server_proc:
        server_proc = subprocess.Popen(["python2", CONTROL_PY])
        server_proc = subprocess.Popen(["python2", CAMERA_PY])
    if not http_proc:
        http_proc = subprocess.Popen(
            ["python2", "-m", "SimpleHTTPServer", HTTP_PORT],
            cwd=WEB_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

def stop_services():
    """Detiene ambos procesos, si están corriendo."""
    global server_proc, http_proc
    if http_proc:
        http_proc.terminate()
        http_proc.wait()
        http_proc = None
    if server_proc:
        server_proc.terminate()
        server_proc.wait()
        server_proc = None

def cleanup(sig, frame):
    """Manejador de señales para limpiar al cerrar."""
    stop_services()
    os._exit(0)

# Captura Ctrl+C, SIGTERM, etc.
signal.signal(signal.SIGINT,  cleanup)
signal.signal(signal.SIGTERM, cleanup)

def main():
    # Mensaje de verificación al iniciarse el launcher
    try:
        tts.say("Oprime mi cabeza cinco segundos para iniciar el modo de control")
    except Exception:
        pass

    pressed     = False
    press_start = 0.0

    while True:
        # Lee el tactil medio de la cabeza
        try:
            curr = memory.getData("MiddleTactilTouched")
        except Exception:
            curr = 0

        # Detecta el flanco 0→1 (comienzo de pulsación)
        if curr == 1 and not pressed:
            pressed     = True
            press_start = time.time()

        # Detecta fin de pulsación tras un hold largo
        elif curr == 0 and pressed:
            elapsed = time.time() - press_start
            pressed = False
            if elapsed >= PRESS_HOLD:
                # Toggle: si ya hay procesos, los para; si no, los arranca
                if server_proc or http_proc:
                    stop_services()
                    tts.say("Modo de control detenido")
                else:
                    start_services()
                    tts.say("Modo de control iniciado")
        time.sleep(0.1)

if __name__ == "__main__":
    main()
