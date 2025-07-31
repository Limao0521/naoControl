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
import socket
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

def get_server_ip():
    """Obtiene automáticamente la IP del servidor (gateway de la red local)."""
    try:
        # Crear un socket para obtener la IP local del NAO
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Conectar a una IP externa (no se envía tráfico real)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Obtener la IP del gateway (asumiendo que es la .1 de la red)
        ip_parts = local_ip.split('.')
        gateway_ip = '.'.join(ip_parts[:3]) + '.1'
        
        # Intentar hacer ping al gateway para verificar conectividad
        response = os.system("ping -c 1 " + gateway_ip + " > /dev/null 2>&1")
        if response == 0:
            return gateway_ip
        else:
            # Si el gateway no responde, usar la IP base de la red + .100
            return '.'.join(ip_parts[:3]) + '.100'
    except Exception:
        # IP por defecto si hay algún error
        return "192.168.1.100"

# Proxies NAOqi
memory = ALProxy("ALMemory", IP_NAO, PORT_NAO)
tts    = ALProxy("ALTextToSpeech", IP_NAO, PORT_NAO)

# Procesos externos; inicialmente ninguno
server_proc = None
http_proc   = None
camera_proc = None

def start_services():
    """Arranca control_server.py y el HTTP server."""
    global server_proc, http_proc, camera_proc
    
    services_started = 0
    total_services = 3
    
    # Iniciar control server
    if not server_proc:
        try:
            server_proc = subprocess.Popen(["python2", CONTROL_PY])
            time.sleep(2)  # Esperar un momento para que el proceso se inicie
            
            # Verificar que el proceso sigue corriendo
            if server_proc.poll() is None:
                services_started += 1
            else:
                server_proc = None
        except Exception:
            server_proc = None
    else:
        services_started += 1
    
    # Iniciar cámara
    if 'camera_proc' not in globals():
        camera_proc = None
    
    if not camera_proc:
        try:
            # Obtener IP del servidor dinámicamente
            server_ip = get_server_ip()
            camera_proc = subprocess.Popen([
                "python2", CAMERA_PY, 
                "--server_ip", server_ip,
                "--nao_ip", IP_NAO,
                "--nao_port", str(PORT_NAO),
                "--http_port", "8080"
            ])
            time.sleep(2)  # Esperar un momento para que el proceso se inicie
            
            # Verificar que el proceso sigue corriendo
            if camera_proc.poll() is None:
                services_started += 1
            else:
                camera_proc = None
        except Exception:
            camera_proc = None
    else:
        services_started += 1
    
    # Iniciar servidor HTTP
    if not http_proc:
        try:
            http_proc = subprocess.Popen(
                ["python2", "-m", "SimpleHTTPServer", HTTP_PORT],
                cwd=WEB_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(1)  # Esperar un momento para que el servidor HTTP se inicie
            
            # Verificar que el proceso sigue corriendo
            if http_proc.poll() is None:
                services_started += 1
            else:
                http_proc = None
        except Exception:
            http_proc = None
    else:
        services_started += 1
    
    # Mensaje final según el resultado
    if services_started == total_services:
        tts.say("Todos los servicios iniciados correctamente")
    else:
        tts.say("Error: algunos servicios no pudieron iniciarse")

def stop_services():
    """Detiene ambos procesos, si están corriendo."""
    global server_proc, http_proc, camera_proc
    
    if http_proc:
        try:
            http_proc.terminate()
            http_proc.wait()
            http_proc = None
        except Exception:
            http_proc = None
    
    if 'camera_proc' in globals() and camera_proc:
        try:
            camera_proc.terminate()
            camera_proc.wait()
            camera_proc = None
        except Exception:
            camera_proc = None
    
    if server_proc:
        try:
            server_proc.terminate()
            server_proc.wait()
            server_proc = None
        except Exception:
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
                if server_proc or http_proc or (camera_proc if 'camera_proc' in globals() else False):
                    stop_services()
                    tts.say("Modo de control detenido")
                else:
                    tts.say("Iniciando modo de control")
                    start_services()
        time.sleep(0.1)

if __name__ == "__main__":
    main()
