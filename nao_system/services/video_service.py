#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
services.video_service

Servicio para captura y distribución de video desde NAO. Soporta envío
por UDP y streaming MJPEG cuando los proxies NAOqi están disponibles.
Encabezado informativo añadido.
Fecha: 2025-09-08
"""

import threading
import time
import socket
import json
from ..interfaces.base_interfaces import IVideoStreamer
from ..core.config import DEFAULT_VIDEO_RESOLUTION, UDP_VIDEO_PORT

class VideoStreamService(IVideoStreamer):
    """Servicio de streaming de video para NAO"""
    
    def __init__(self, nao_adapter, logger=None):
        self.nao_adapter = nao_adapter
        self.logger = logger
        self.running = False
        self.video_proxy = None
        self.subscriber_id = None
        self.resolution = DEFAULT_VIDEO_RESOLUTION
        self.latest_frame = None
        self.udp_socket = None
        self.target_host = None
        self.target_port = UDP_VIDEO_PORT
        
        if self.logger:
            self.logger.info("VideoStreamService inicializado")
    
    def start_stream(self, resolution=None, target_host=None, target_port=None):
        """Iniciar streaming de video"""
        try:
            if self.running:
                if self.logger:
                    self.logger.warning("Stream ya está ejecutándose")
                return False
            
            if not self.nao_adapter.is_connected():
                if self.logger:
                    self.logger.warning("NAO no conectado - no se puede iniciar stream")
                return False
            
            # Configurar parámetros
            self.resolution = resolution or self.resolution
            self.target_host = target_host
            self.target_port = target_port or self.target_port
            
            # Obtener proxy de video
            self.video_proxy = self.nao_adapter.get_proxy('video')
            if not self.video_proxy:
                # Crear proxy de video si no existe
                try:
                    import naoqi
                    self.video_proxy = naoqi.ALProxy("ALVideoDevice", 
                                                   self.nao_adapter.nao_ip, 
                                                   self.nao_adapter.nao_port)
                except Exception as e:
                    if self.logger:
                        self.logger.error("Error creando proxy de video: {}".format(e))
                    return False
            
            # Suscribirse al stream
            self.subscriber_id = self.video_proxy.subscribeCamera(
                "VideoStreamService", 
                0,  # Cámara superior
                self.resolution,
                11,  # RGB
                30   # FPS
            )
            
            # Configurar UDP si se especifica destino
            if self.target_host:
                self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                if self.logger:
                    self.logger.info("UDP configurado para {}:{}".format(self.target_host, self.target_port))
            
            self.running = True
            
            # Iniciar hilo de captura
            self.capture_thread = threading.Thread(target=self._capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            if self.logger:
                self.logger.info("Stream de video iniciado (resolución: {})".format(self.resolution))
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error iniciando stream: {}".format(e))
            return False
    
    def stop_stream(self):
        """Detener streaming de video"""
        try:
            self.running = False
            
            # Esperar a que termine el hilo
            if hasattr(self, 'capture_thread') and self.capture_thread.is_alive():
                self.capture_thread.join(timeout=2.0)
            
            # Desuscribirse del stream
            if self.video_proxy and self.subscriber_id:
                try:
                    self.video_proxy.unsubscribe(self.subscriber_id)
                except Exception as e:
                    if self.logger:
                        self.logger.warning("Error desuscribiendo video: {}".format(e))
            
            # Cerrar socket UDP
            if self.udp_socket:
                try:
                    self.udp_socket.close()
                except Exception:
                    pass
                self.udp_socket = None
            
            self.subscriber_id = None
            self.latest_frame = None
            
            if self.logger:
                self.logger.info("Stream de video detenido")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error deteniendo stream: {}".format(e))
            return False
    
    def get_latest_frame(self):
        """Obtener último frame capturado"""
        return self.latest_frame
    
    def _capture_loop(self):
        """Bucle principal de captura"""
        if self.logger:
            self.logger.info("Iniciando captura de video")
        
        while self.running:
            try:
                if not self.video_proxy:
                    time.sleep(0.1)
                    continue
                
                # Obtener imagen
                image_data = self.video_proxy.getImageRemote(self.subscriber_id)
                if not image_data:
                    time.sleep(0.1)
                    continue
                
                # Extraer datos de la imagen
                width = image_data[0]
                height = image_data[1]
                channels = image_data[2]
                timestamp = image_data[4]
                image_buffer = image_data[6]
                
                # Crear frame info
                frame_info = {
                    'width': width,
                    'height': height,
                    'channels': channels,
                    'timestamp': timestamp,
                    'data_size': len(image_buffer)
                }
                
                self.latest_frame = frame_info
                
                # Enviar por UDP si está configurado
                if self.udp_socket and self.target_host:
                    try:
                        # Enviar metadata primero
                        metadata = json.dumps(frame_info).encode('utf-8')
                        self.udp_socket.sendto(metadata, (self.target_host, self.target_port))
                        
                        # Enviar datos de imagen (limitado por tamaño de UDP)
                        max_chunk_size = 64000  # Tamaño máximo por paquete UDP
                        
                        for i in range(0, len(image_buffer), max_chunk_size):
                            chunk = image_buffer[i:i+max_chunk_size]
                            self.udp_socket.sendto(chunk, (self.target_host, self.target_port + 1))
                        
                    except Exception as e:
                        if self.logger:
                            self.logger.warning("Error enviando UDP: {}".format(e))
                
                # Liberar imagen
                self.video_proxy.releaseImage(self.subscriber_id)
                
                # Control de frame rate
                time.sleep(1.0/30.0)  # ~30 FPS
                
            except Exception as e:
                if self.logger:
                    self.logger.error("Error en captura: {}".format(e))
                time.sleep(0.5)
        
        if self.logger:
            self.logger.info("Captura de video detenida")
    
    def get_status(self):
        """Obtener estado del servicio"""
        return {
            'running': self.running,
            'resolution': self.resolution,
            'subscriber_id': self.subscriber_id,
            'udp_enabled': self.udp_socket is not None,
            'target_host': self.target_host,
            'target_port': self.target_port,
            'has_latest_frame': self.latest_frame is not None
        }
