#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
logger.py - Sistema de logging centralizado con WebSocket

Funcionalidades:
- Servidor WebSocket para streaming de logs en tiempo real (puerto 6672)
- Cliente de logging para enviar logs desde diferentes módulos
- Clasificación de logs por módulo [LAUNCHER], [CONTROL], [CAMERA], etc.
- Almacenamiento en archivo y memoria circular
- Compatible con Postman y otros clientes WebSocket
"""

import threading
import time
import json
import socket
import logging
import os
import sys
from datetime import datetime
from collections import deque
from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer

# Configuración
LOG_WS_PORT = 6672
LOG_UDP_PORT = 6673
MAX_LOG_HISTORY = 500  # Reducido para mejor rendimiento
LOG_FILE = "/tmp/nao_system.log"

class LogEntry:
    def __init__(self, module, level, message, timestamp=None):
        self.module = module
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self):
        return {
            'module': self.module,
            'level': self.level,
            'message': self.message,
            'timestamp': self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        }
    
    def to_string(self):
        return "{} [{}] [{}] {}".format(
            self.timestamp.strftime("%H:%M:%S.%f")[:-3],
            self.module,
            self.level,
            self.message
        )

class LogManager:
    def __init__(self):
        self.logs = deque(maxlen=MAX_LOG_HISTORY)
        self.websocket_clients = set()
        self.lock = threading.Lock()
        self.running = True
        
        # Configurar logging a archivo
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.DEBUG,
            format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        self.file_logger = logging.getLogger('NAO_SYSTEM')
        
        # Agregar log inicial
        self.add_log("LOGGER", "INFO", "Sistema de logging iniciado")
    
    def add_log(self, module, level, message):
        """Agregar un nuevo log al sistema"""
        entry = LogEntry(module, level, message)
        
        with self.lock:
            self.logs.append(entry)
        
        # Escribir a archivo
        getattr(self.file_logger, level.lower(), self.file_logger.info)(
            "[{}] {}".format(module, message)
        )
        
        # Enviar a clientes WebSocket
        self.broadcast_to_websockets(entry)
        
        # Imprimir a consola
        print(entry.to_string())
    
    def broadcast_to_websockets(self, entry):
        """Enviar log a todos los clientes WebSocket conectados"""
        if not self.websocket_clients:
            return
        
        message = json.dumps(entry.to_dict())
        disconnected = set()
        
        for client in self.websocket_clients:
            try:
                client.sendMessage(message)
            except Exception as e:
                disconnected.add(client)
        
        # Remover clientes desconectados
        for client in disconnected:
            self.websocket_clients.discard(client)
    
    def get_recent_logs(self, count=50):
        """Obtener logs recientes"""
        with self.lock:
            return list(self.logs)[-count:]
    
    def add_websocket_client(self, client):
        """Agregar cliente WebSocket"""
        self.websocket_clients.add(client)
        self.add_log("LOGGER", "INFO", "Cliente WebSocket conectado desde: {}".format(client.address))
        
        # Enviar logs recientes al cliente (solo los últimos 20 para no saturar)
        recent_logs = self.get_recent_logs(20)
        for log_entry in recent_logs:
            try:
                client.sendMessage(json.dumps(log_entry.to_dict()))
            except Exception as e:
                self.add_log("LOGGER", "WARNING", "Error enviando logs iniciales: {}".format(e))
    
    def remove_websocket_client(self, client):
        """Remover cliente WebSocket"""
        self.websocket_clients.discard(client)

# Instancia global del manager
log_manager = LogManager()

class LogWebSocket(WebSocket):
    def handleMessage(self):
        # No necesitamos manejar mensajes entrantes del cliente
        # Solo enviamos logs al cliente
        pass
    
    def handleConnected(self):
        log_manager.add_log("LOGGER", "INFO", "Cliente WebSocket conectado: {}".format(self.address))
        log_manager.add_websocket_client(self)
    
    def handleClose(self):
        log_manager.add_log("LOGGER", "INFO", "Cliente WebSocket desconectado: {}".format(self.address))
        log_manager.remove_websocket_client(self)

class UDPLogReceiver:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('127.0.0.1', LOG_UDP_PORT))
        self.running = True
    
    def start(self):
        """Iniciar receptor UDP en hilo separado"""
        thread = threading.Thread(target=self._receive_loop)
        thread.daemon = True
        thread.start()
        log_manager.add_log("LOGGER", "INFO", "Receptor UDP iniciado en puerto {}".format(LOG_UDP_PORT))
    
    def _receive_loop(self):
        """Bucle principal para recibir logs por UDP"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                log_data = json.loads(data.decode('utf-8'))
                log_manager.add_log(
                    log_data.get('module', 'UNKNOWN'),
                    log_data.get('level', 'INFO'),
                    log_data.get('message', '')
                )
            except Exception as e:
                log_manager.add_log("LOGGER", "ERROR", "Error recibiendo UDP: {}".format(str(e)))
                time.sleep(0.1)
    
    def stop(self):
        self.running = False
        self.socket.close()

class NAOLogger:
    """Cliente de logging para enviar logs al sistema centralizado"""
    def __init__(self, module_name):
        self.module_name = module_name
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def _send_log(self, level, message):
        """Enviar log por UDP al servidor"""
        try:
            log_data = {
                'module': self.module_name,
                'level': level,
                'message': message
            }
            data = json.dumps(log_data).encode('utf-8')
            self.udp_socket.sendto(data, ('127.0.0.1', LOG_UDP_PORT))
        except Exception as e:
            # Fallback a print si falla el envío
            print("{} [{}] [{}] {}".format(
                datetime.now().strftime("%H:%M:%S.%f")[:-3],
                self.module_name,
                level,
                message
            ))
    
    def debug(self, message):
        self._send_log("DEBUG", message)
    
    def info(self, message):
        self._send_log("INFO", message)
    
    def warning(self, message):
        self._send_log("WARNING", message)
    
    def error(self, message):
        self._send_log("ERROR", message)
    
    def critical(self, message):
        self._send_log("CRITICAL", message)

def create_logger(module_name):
    """Función helper para crear un logger para un módulo"""
    return NAOLogger(module_name)

def main():
    """Función principal del servidor de logs"""
    print("=== NAO LOGGING SERVER ===")
    print("WebSocket: ws://localhost:{}".format(LOG_WS_PORT))
    print("UDP: localhost:{}".format(LOG_UDP_PORT))
    print("Archivo: {}".format(LOG_FILE))
    print("Para Postman: ws://localhost:{}".format(LOG_WS_PORT))
    print("Presiona Ctrl+C para detener")
    
    # Iniciar receptor UDP
    udp_receiver = UDPLogReceiver()
    udp_receiver.start()
    
    # Iniciar servidor WebSocket
    try:
        server = SimpleWebSocketServer('', LOG_WS_PORT, LogWebSocket)
        log_manager.add_log("LOGGER", "INFO", "Servidor WebSocket iniciado en puerto {}".format(LOG_WS_PORT))
        log_manager.add_log("LOGGER", "INFO", "Listo para conectar desde Postman: ws://localhost:{}".format(LOG_WS_PORT))
        
        server.serveforever()
    except KeyboardInterrupt:
        log_manager.add_log("LOGGER", "INFO", "Cerrando servidor de logs...")
        udp_receiver.stop()
    except Exception as e:
        log_manager.add_log("LOGGER", "ERROR", "Error en servidor: {}".format(str(e)))
        udp_receiver.stop()

if __name__ == "__main__":
    main()
