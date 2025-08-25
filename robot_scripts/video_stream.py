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
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        
        while True:
            with lock:
                frame = latest_jpeg
            if frame:
                try:
                    self.wfile.write(b"--jpgboundary\r\n")
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(frame)))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
                except:
                    # Cliente desconectado, salir del bucle
                    break
            
            # Framerate más adaptativo basado en el FPS configurado
            time.sleep(1.0 / (args.fps * 1.2))  # Slightly faster than capture rate


def grabber(video_proxy, client_name, server_ip, server_port, fps):
    global latest_jpeg
    # configurar socket UDP con optimizaciones
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2000000)  # Buffer más grande
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Usar resolución configurable para optimizar framerate
    # 0=160x120, 1=320x240, 2=640x480, 3=1280x960
    resolution = args.resolution
    colorspace = 13  # BGR - compatible con OpenCV
    client = video_proxy.subscribeCamera(client_name, 0, resolution, colorspace, fps)
    
    # Configurar parámetros de compresión optimizados
    jpeg_params = [int(cv2.IMWRITE_JPEG_QUALITY), 75,  # Reducir calidad de 90 a 75
                   int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
                   int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1]
    
    frame_count = 0
    fps_start_time = time.time()
    
    while True:
        start_time = time.time()
        
        # Usar getImageRemote que es más rápido que getImageLocal
        res = video_proxy.getImageRemote(client)
        if res is None:
            time.sleep(0.001)  # Reducir sleep de 0.005 a 0.001
            continue
            
        width, height = res[0], res[1]
        
        # Optimizar creación del array numpy
        arr = np.frombuffer(res[6], dtype=np.uint8)
        img = arr.reshape((height, width, 3))
        
        # Comprimir JPEG con parámetros optimizados
        ret, jpg = cv2.imencode('.jpg', img, jpeg_params)
        if not ret:
            continue
            
        frame_bytes = jpg.tobytes()
        
        # Actualizar frame global de manera más eficiente
        with lock:
            latest_jpeg = frame_bytes
        
        # Envío UDP optimizado
        try:
            # Enviar directamente los bytes JPEG en lugar de pickle
            udp_sock.sendto(frame_bytes, (server_ip, server_port))
        except Exception as e:
            print("Error enviando frame UDP:", e)
        
        # Monitorear FPS real cada 30 frames
        frame_count += 1
        if frame_count % 30 == 0:
            elapsed_fps = time.time() - fps_start_time
            real_fps = 30.0 / elapsed_fps
            print("FPS real: {:.1f}".format(real_fps))
            fps_start_time = time.time()
        
        # Control de framerate más preciso
        elapsed = time.time() - start_time
        target_frame_time = 1.0 / fps
        sleep_time = target_frame_time - elapsed
        
        if sleep_time > 0:
            time.sleep(sleep_time)
        # Si estamos atrasados, no hacemos sleep para intentar recuperar


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Streamer MJPEG + UDP video desde NAO')
    parser.add_argument('--nao_ip',    required=False, default='127.0.0.1', help='IP del robot NAO')
    parser.add_argument('--nao_port',  required=False, default=9559, type=int, help='Puerto NAOqi del robot')
    parser.add_argument('--http_port', required=False, default=8080, type=int, help='Puerto HTTP para MJPEG')
    parser.add_argument('--server_ip', required=True, help='IP del servidor UDP destino')
    parser.add_argument('--server_port', required=False, default=6666, type=int, help='Puerto UDP destino')
    parser.add_argument('--fps',       required=False, default=30, type=int, help='Frames por segundo (máximo recomendado: 30)')
    parser.add_argument('--resolution', required=False, default=1, type=int, 
                       help='Resolución: 0=160x120, 1=320x240, 2=640x480, 3=1280x960')
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
    print("Configuración: FPS=%d, Resolución=%dx%d" % (args.fps, 
          [160, 320, 640, 1280][args.resolution], [120, 240, 480, 960][args.resolution]))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Servidor detenido")
        # Desuscribir correctamente del video
        try:
            video.unsubscribe(client_name)
        except:
            pass
        server.shutdown()
