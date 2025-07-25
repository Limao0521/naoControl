#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
camera_stream.py – MJPEG stream en Python 2.7 usando ALVideoDevice

Utiliza el proxy ALVideoDevice para capturar un fotograma cada 100 ms
y lo sirve vía HTTP multipart/x-mixed-replace en el puerto 8080.
"""

from naoqi import ALProxy
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import cv2, numpy as np, threading, time

IP_NAO      = "127.0.0.1"
PORT_NAO    = 9559
HTTP_PORT   = 8080
FPS         = 30
CAMERA_NAME = "camera_stream"

# Inicializar proxy de vídeo
video = ALProxy("ALVideoDevice", IP_NAO, PORT_NAO)
client = video.subscribeCamera(CAMERA_NAME, 0, 11, 13, FPS)  # cámara 0, 640×480 RGB

latest_jpeg = None
lock = threading.Lock()

def grabber():
    global latest_jpeg
    while True:
        res = video.getImageRemote(client)
        if res is None:
            time.sleep(1.0/FPS)
            continue
        width, height = res[0], res[1]
        arr = np.frombuffer(res[6], dtype=np.uint8)
        img = arr.reshape((height, width, 3))
        ret, jpg = cv2.imencode('.jpg', img)
        if ret:
            with lock:
                latest_jpeg = jpg.tobytes()
        time.sleep(1.0/FPS)

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
                self.send_header('Content-Type','image/jpeg')
                self.send_header('Content-Length', str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
            time.sleep(1.0/FPS)

if __name__ == '__main__':
    # Arranca hilo de captura como demonio (Python 2 compatible)
    t = threading.Thread(target=grabber)
    t.setDaemon(True)
    t.start()

    server = HTTPServer(('', HTTP_PORT), MJPEGHandler)
    print("Camera MJPEG stream en http://0.0.0.0:%d/video.mjpeg" % HTTP_PORT)
    server.serve_forever()
