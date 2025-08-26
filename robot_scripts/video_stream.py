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
import sys
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from naoqi import ALProxy
import numpy as np
import cv2
import pickle

# Importar sistema de logging
try:
    from logger import create_logger
    logger = create_logger("CAMERA")
except ImportError:
    # Fallback si no está disponible
    class FallbackLogger:
        def debug(self, msg): print("DEBUG [CAMERA] {}".format(msg))
        def info(self, msg): print("INFO [CAMERA] {}".format(msg))
        def warning(self, msg): print("WARNING [CAMERA] {}".format(msg))
        def error(self, msg): print("ERROR [CAMERA] {}".format(msg))
        def critical(self, msg): print("CRITICAL [CAMERA] {}".format(msg))
    logger = FallbackLogger()

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
    logger.info("Iniciando grabber de video - FPS: {}, Server: {}:{}".format(fps, server_ip, server_port))
    
    # configurar socket UDP con optimizaciones
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2000000)  # Buffer más grande
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    logger.info("Socket UDP configurado con buffer de 2MB")
    
    # Usar resolución configurable para optimizar framerate
    # 0=160x120, 1=320x240, 2=640x480, 3=1280x960
    resolution = args.resolution
    colorspace = 13  # BGR - compatible con OpenCV
    
    try:
        client = video_proxy.subscribeCamera(client_name, 0, resolution, colorspace, fps)
        resolution_map = {0: "160x120", 1: "320x240", 2: "640x480", 3: "1280x960"}
        logger.info("Cámara suscrita - Resolución: {}, Colorspace: BGR".format(resolution_map.get(resolution, "Unknown")))
    except Exception as e:
        logger.error("Error suscribiendo cámara: {}".format(e))
        return
    
    # Configurar parámetros de compresión optimizados
    jpeg_params = [int(cv2.IMWRITE_JPEG_QUALITY), 75,  # Reducir calidad de 90 a 75
                   int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
                   int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1]
    logger.info("Parámetros JPEG configurados - Calidad: 75, Optimizado: True")
    
    frame_count = 0
    fps_start_time = time.time()
    error_count = 0
    
    try:
        while True:
            start_time = time.time()
            
            # Usar getImageRemote que es más rápido que getImageLocal
            res = video_proxy.getImageRemote(client)
            if res is None:
                error_count += 1
                if error_count % 100 == 0:
                    logger.warning("Sin frames recibidos - Errores consecutivos: {}".format(error_count))
                time.sleep(0.001)  # Reducir sleep de 0.005 a 0.001
                continue
            
            if error_count > 0:
                logger.info("Frames recuperados después de {} errores".format(error_count))
                error_count = 0
                
            width, height = res[0], res[1]
            
            # Optimizar creación del array numpy
            arr = np.frombuffer(res[6], dtype=np.uint8)
            img = arr.reshape((height, width, 3))
            
            # Comprimir JPEG con parámetros optimizados
            ret, jpg = cv2.imencode('.jpg', img, jpeg_params)
            if not ret:
                logger.warning("Error comprimiendo frame JPEG")
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
                logger.error("Error enviando frame UDP: {}".format(e))
            
            # Monitorear FPS real cada 30 frames
            frame_count += 1
            if frame_count % 30 == 0:
                elapsed_fps = time.time() - fps_start_time
                real_fps = 30.0 / elapsed_fps
                logger.info("FPS real: {:.1f} - Frames procesados: {}".format(real_fps, frame_count))
                fps_start_time = time.time()
            
            # Control de framerate más preciso
            elapsed = time.time() - start_time
            target_frame_time = 1.0 / fps
            sleep_time = target_frame_time - elapsed
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            # Si estamos atrasados, no hacemos sleep para intentar recuperar
            
    except Exception as e:
        logger.error("Error crítico en grabber: {}".format(e))
    finally:
        try:
            video_proxy.unsubscribe(client)
            logger.info("Cliente de cámara desuscrito correctamente")
        except Exception as e:
            logger.error("Error desuscribiendo cliente: {}".format(e))


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

    logger.info("=== INICIANDO SISTEMA DE VIDEO STREAMING ===")
    logger.info("Configuración:")
    logger.info("  NAO: {}:{}".format(args.nao_ip, args.nao_port))
    logger.info("  HTTP: puerto {}".format(args.http_port))
    logger.info("  UDP: {}:{}".format(args.server_ip, args.server_port))
    logger.info("  FPS: {}".format(args.fps))
    logger.info("  Resolución: {}".format(args.resolution))

    # Inicializar proxy de vídeo
    try:
        video = ALProxy('ALVideoDevice', args.nao_ip, args.nao_port)
        logger.info("Proxy ALVideoDevice inicializado correctamente")
    except Exception as e:
        logger.critical("Error inicializando ALVideoDevice: {}".format(e))
        sys.exit(1)
    
    client_name = 'camera_stream_udp'

    # Lanzar hilo de captura (daemon)
    logger.info("Iniciando hilo de captura de video...")
    t = threading.Thread(target=grabber,
                         args=(video, client_name, args.server_ip, args.server_port, args.fps))
    t.setDaemon(True)
    t.start()

    # Arrancar servidor HTTP para MJPEG
    try:
        server = HTTPServer(('', args.http_port), MJPEGHandler)
        resolution_names = ["160x120", "320x240", "640x480", "1280x960"]
        resolution_name = resolution_names[args.resolution] if args.resolution < len(resolution_names) else "Unknown"
        
        logger.info("Servidor HTTP MJPEG iniciado en puerto {}".format(args.http_port))
        logger.info("Stream disponible en: http://0.0.0.0:{}/video.mjpeg".format(args.http_port))
        logger.info("Configuración activa: FPS={}, Resolución={}".format(args.fps, resolution_name))
        
        print("Camera MJPEG + UDP stream en http://0.0.0.0:%d/video.mjpeg" % args.http_port)
        print("Configuración: FPS=%d, Resolución=%s" % (args.fps, resolution_name))
        
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Interrupción de teclado detectada - Cerrando servidor...")
        print("Servidor detenido")
        # Desuscribir correctamente del video
        try:
            video.unsubscribe(client_name)
            logger.info("Cliente de video desuscrito correctamente")
        except Exception as e:
            logger.error("Error desuscribiendo cliente: {}".format(e))
        server.shutdown()
    except Exception as e:
        logger.error("Error en servidor HTTP: {}".format(e))
        server.shutdown()
