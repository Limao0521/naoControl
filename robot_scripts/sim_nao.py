#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim_nao.py – Simulador de NAO para desarrollo de la interfaz web final

Este script expone dos servicios:

1) Un servidor WebSocket en 0.0.0.0:6671 que acepta mensajes JSON
   con las acciones:
     • walk     → {action:"walk", vx, vy, wz}
     • move     → {action:"move", joint:"<JointName>", value:<float>}
     • posture  → {action:"posture", value:"<PostureName>"}
     • led      → {action:"led", r:<0–1>, g:<0–1>, b:<0–1>}
     • say      → {action:"say", text:"<texto>"}
     • getInfo  → {action:"getInfo"}
   Y responde con un mensaje JSON de estado para getInfo:
     {info:{battery:<int>, joints:{JointName:{pos:<float>,temp:<float>},…}}}

2) Un servidor HTTP en 0.0.0.0:8080 que simula la cámara MJPEG:
   • Al recibir un GET /video.mjpeg imprime un log y devuelve texto plano
     para indicar «conexión establecida».

Para ejecutar:
  pip install websockets
  python sim_nao.py
"""

import asyncio
import json
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import websockets

# ───────────────────────────────────────── CONFIGURACIÓN ────────────────
WS_HOST  = "0.0.0.0"  # Escucha en todas las interfaces
WS_PORT  = 6671       # Puerto WebSocket
CAM_HOST = "0.0.0.0"  # Escucha en todas las interfaces
CAM_PORT = 8080       # Puerto HTTP para cámara
WATCHDOG = 0.6        # Segundos que consideramos para watchdog (no usado aquí)

# ───────────────────────────────────────── HTTP SERVER (Cámara sim) ─────
class CameraHandler(BaseHTTPRequestHandler):
    """Maneja peticiones HTTP a /video.mjpeg simulando la cámara."""

    def do_GET(self):
        """Se llama al recibir GET. Solo aceptamos /video.mjpeg."""
        if self.path != "/video.mjpeg":
            # Cualquier otra ruta devuelve 404
            self.send_response(404)
            self.end_headers()
            return

        # Log de conexión de cámara
        client = self.client_address
        print(f"[CAM] GET /video.mjpeg desde {client[0]}:{client[1]}")

        # Respondemos un texto plano (no un MJPEG real)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Simulated camera stream connected\n")

def start_camera_server():
    """Arranca el HTTPServer en un hilo separado."""
    httpd = HTTPServer((CAM_HOST, CAM_PORT), CameraHandler)
    print(f"[CAM] Servidor HTTP corriendo en http://{CAM_HOST}:{CAM_PORT}")
    httpd.serve_forever()

# ───────────────────────────────────────── WEBSOCKET HANDLER ────────────
async def ws_handler(websocket):
    """
    Maneja un cliente WebSocket.

    Parámetro:
      websocket: instancia WebSocket de la conexión entrante.

    No usamos el parámetro 'path' porque la versión de websockets ya no lo pasa.
    """
    client = websocket.remote_address
    print(f"[WS] Cliente conectado: {client[0]}:{client[1]}")

    try:
        # Iteramos sobre cada mensaje que venga del cliente
        async for raw in websocket:
            print(f"[WS] Mensaje recibido: {raw}")
            # Intentar decodificar JSON
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                print("[WS] ⚠ JSON inválido")
                continue

            action = msg.get("action")
            # ─── WALK ─────────────────────────────────────
            if action == "walk":
                vx = msg.get("vx", 0.0)
                vy = msg.get("vy", 0.0)
                wz = msg.get("wz", 0.0)
                print(f"[SIM] Acción WALK → vx={vx}, vy={vy}, wz={wz}")

            # ─── MOVE ─────────────────────────────────────
            elif action == "move":
                joint = msg.get("joint")
                val   = msg.get("value")
                print(f"[SIM] Acción MOVE → joint='{joint}', value={val}")

            # ─── POSTURE ──────────────────────────────────
            elif action == "posture":
                posture = msg.get("value")
                print(f"[SIM] Acción POSTURE → '{posture}'")

            # ─── LED ──────────────────────────────────────
            elif action == "led":
                r = msg.get("r", 0.0)
                g = msg.get("g", 0.0)
                b = msg.get("b", 0.0)
                print(f"[SIM] Acción LED → R={r}, G={g}, B={b}")

            # ─── SAY ──────────────────────────────────────
            elif action == "say":
                text = msg.get("text", "")
                print(f"[SIM] Acción SAY → \"{text}\"")

            # ─── GET INFO ─────────────────────────────────
            elif action == "getInfo":
                # Simular carga de batería
                batt = random.randint(50, 100)
                # Simular posiciones y temperaturas de articulaciones
                joints = {
                    "HeadYaw":   {"pos": random.uniform(-1,1),  "temp": random.uniform(30,40)},
                    "HeadPitch": {"pos": random.uniform(-1,1),  "temp": random.uniform(30,40)},
                    "LShoulderPitch": {"pos": random.uniform(-1,1), "temp": random.uniform(30,40)},
                    "RShoulderPitch": {"pos": random.uniform(-1,1), "temp": random.uniform(30,40)}
                }
                info = {"battery": batt, "joints": joints}
                resp = json.dumps({"info": info})
                await websocket.send(resp)
                print("[SIM] Respuesta getInfo enviada")

            else:
                print(f"[SIM] ⚠ Acción desconocida: {action}")

    except websockets.ConnectionClosed:
        print(f"[WS] Cliente desconectado: {client[0]}:{client[1]}")

# ───────────────────────────────────────── ENTRYPOINT ────────────────
if __name__ == "__main__":
    # Iniciar servidor de cámara en un hilo demonio
    cam_thread = threading.Thread(target=start_camera_server, daemon=True)
    cam_thread.start()

    # Iniciar servidor WebSocket
    print(f"[WS] Iniciando WebSocket en ws://{WS_HOST}:{WS_PORT}")
    asyncio.run(websockets.serve(ws_handler, WS_HOST, WS_PORT))
    # Nota: websockets.serve retorna un awaitable que sirve forever
