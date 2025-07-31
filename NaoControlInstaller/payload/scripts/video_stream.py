#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
camera_stream_udp.py – Servidor MJPEG + envío UDP de video desde NAO

Combina las funcionalidades de camera_stream.py y full_server.py:
- Captura video usando ALVideoDevice (NAOqi).
- Sirve un stream MJPEG vía HTTP (puerto configurable).
- Envía cada frame comprimido JPEG por UDP al servidor remoto.
"""
import socket
import threading
import time
import argparse
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from naoqi import ALProxy
import numpy as np
import cv2
import pickle

# Variables globales para el frame JPEG y sincronización\latest_jpeg = None
lock = threading.Lock()

class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/video.mjpeg':
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
        self.end_headers()
        while True:
            with lock:
                frame = latest_jpeg
            if frame:
                self.wfile.write(b"--jpgboundary\r\n")
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
            time.sleep(1.0 / args.fps)


def grabber(video_proxy, client_name, server_ip, server_port, fps):
    global latest_jpeg
    # configurar socket UDP
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1000000)

    client = video_proxy.subscribeCamera(client_name, 0, 11, 13, fps)
    while True:
        res = video_proxy.getImageRemote(client)
        if res is None:
            time.sleep(1.0/fps)
            continue
        # reconstruir imagen
        width, height = res[0], res[1]
        arr = np.frombuffer(res[6], dtype=np.uint8)
        img = arr.reshape((height, width, 3))
        # comprimir a JPEG
        ret, jpg = cv2.imencode('.jpg', img)
        if not ret:
            continue
        frame_bytes = jpg.tobytes()
        # actualizar frame para MJPEG
        with lock:
            latest_jpeg = frame_bytes
        # enviar por UDP (pickle de numpy ndarray para consistencia)
        try:
            payload = pickle.dumps(jpg)
            udp_sock.sendto(payload, (server_ip, server_port))
        except Exception as e:
            print("Error enviando frame UDP:", e)
        time.sleep(1.0/fps)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Streamer MJPEG + UDP video desde NAO')
    parser.add_argument('--nao_ip',    required=False, default='127.0.0.1', help='IP del robot NAO')
    parser.add_argument('--nao_port',  required=False, default=9559, type=int, help='Puerto NAOqi del robot')
    parser.add_argument('--http_port', required=False, default=8080, type=int, help='Puerto HTTP para MJPEG')
    parser.add_argument('--server_ip', required=True, help='IP del servidor UDP destino')
    parser.add_argument('--server_port', required=False, default=6666, type=int, help='Puerto UDP destino')
    parser.add_argument('--fps',       required=False, default=30, type=int, help='Frames por segundo')
    args = parser.parse_args()

    # Inicializar proxy de vídeo
    video = ALProxy('ALVideoDevice', args.nao_ip, args.nao_port)
    client_name = 'camera_stream_udp'

    # Lanzar hilo de captura (daemon)
    t = threading.Thread(target=grabber,
                         args=(video, client_name, args.server_ip, args.server_port, args.fps))
    t.setDaemon(True)
    t.start()

    # Arrancar servidor HTTP para MJPEG
    server = HTTPServer(('', args.http_port), MJPEGHandler)
    print("Camera MJPEG + UDP stream en http://0.0.0.0:%d/video.mjpeg" % args.http_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Servidor detenido")
        server.shutdown()
