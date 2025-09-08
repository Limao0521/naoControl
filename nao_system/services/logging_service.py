#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
services.logging_service

Proveedor de logging centralizado con buffer en memoria, persistencia local
y streaming opcional vía WebSocket. Contiene implementaciones auxiliares
como `LogManager` y `NAOLogger`. Encabezado informativo añadido.
Fecha: 2025-09-08
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

try:
    from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    # Clases dummy para compatibilidad
    class WebSocket(object):
        def __init__(self, server, sock, address):
            pass
        def handleConnected(self):
            pass
        def handleClose(self):
            pass
    
    class SimpleWebSocketServer(object):
        def __init__(self, host, port, handler):
            pass
        def serveforever(self):
            pass
        def close(self):
            pass

from ..interfaces.base_interfaces import ILogger
from ..core.config import LOG_WEBSOCKET_PORT, LOG_FILE, MAX_LOG_HISTORY

class LogEntry(object):
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

class LogManager(object):
    def __init__(self):
        self.log_history = deque(maxlen=MAX_LOG_HISTORY)
        self.websocket_clients = []
        self.lock = threading.Lock()
        self.file_handler = None
        
        # Configurar archivo de log
        try:
            self.file_handler = open(LOG_FILE, 'a')
        except Exception as e:
            print("Warning: No se pudo abrir archivo de log: {}".format(e))
    
    def add_log(self, log_entry):
        with self.lock:
            self.log_history.append(log_entry)
            
            # Escribir a archivo
            if self.file_handler:
                try:
                    self.file_handler.write(log_entry.to_string() + "\n")
                    self.file_handler.flush()
                except Exception:
                    pass
            
            # Enviar a clientes WebSocket
            if self.websocket_clients:
                message = json.dumps(log_entry.to_dict())
                disconnected_clients = []
                
                for client in self.websocket_clients:
                    try:
                        client.sendMessage(message)
                    except Exception:
                        disconnected_clients.append(client)
                
                # Limpiar clientes desconectados
                for client in disconnected_clients:
                    if client in self.websocket_clients:
                        self.websocket_clients.remove(client)
    
    def get_recent_logs(self, count=50):
        with self.lock:
            recent = list(self.log_history)[-count:]
            return [log.to_dict() for log in recent]
    
    def add_websocket_client(self, client):
        with self.lock:
            self.websocket_clients.append(client)
    
    def remove_websocket_client(self, client):
        with self.lock:
            if client in self.websocket_clients:
                self.websocket_clients.remove(client)

# Instancia global del log manager
log_manager = LogManager()

class LogWebSocket(WebSocket):
    def handleConnected(self):
        log_manager.add_websocket_client(self)
        
        # Enviar logs recientes al conectar
        recent_logs = log_manager.get_recent_logs()
        for log_dict in recent_logs:
            try:
                self.sendMessage(json.dumps(log_dict))
            except Exception:
                break
    
    def handleClose(self):
        log_manager.remove_websocket_client(self)

class NAOLogger(ILogger):
    """Implementación del logger para el sistema NAO"""
    
    def __init__(self, module_name):
        self.module_name = module_name
    
    def _log(self, level, message):
        log_entry = LogEntry(self.module_name, level, message)
        log_manager.add_log(log_entry)
        
        # También imprimir en consola para debugging
        print(log_entry.to_string())
    
    def debug(self, message):
        self._log("DEBUG", message)
    
    def info(self, message):
        self._log("INFO", message)
    
    def warning(self, message):
        self._log("WARNING", message)
    
    def error(self, message):
        self._log("ERROR", message)
    
    def critical(self, message):
        self._log("CRITICAL", message)

class LoggingService(object):
    """Servicio de logging que maneja el servidor WebSocket"""
    
    def __init__(self):
        self.server = None
        self.server_thread = None
        self.running = False
    
    def start(self):
        """Iniciar el servidor de logging"""
        if not WEBSOCKET_AVAILABLE:
            print("Warning: WebSocket server no disponible para logging")
            return False
        
        try:
            self.server = SimpleWebSocketServer('', LOG_WEBSOCKET_PORT, LogWebSocket)
            self.server_thread = threading.Thread(target=self.server.serveforever)
            self.server_thread.daemon = True
            self.server_thread.start()
            self.running = True
            
            logger = NAOLogger("LOGGING")
            logger.info("Servidor de logging iniciado en puerto {}".format(LOG_WEBSOCKET_PORT))
            return True
            
        except Exception as e:
            print("Error iniciando servidor de logging: {}".format(e))
            return False
    
    def stop(self):
        """Detener el servidor de logging"""
        if self.server and self.running:
            try:
                self.server.close()
                self.running = False
                
                logger = NAOLogger("LOGGING")
                logger.info("Servidor de logging detenido")
                return True
                
            except Exception as e:
                print("Error deteniendo servidor de logging: {}".format(e))
                return False
        return True

def create_logger(module_name):
    """Factory function para crear loggers"""
    return NAOLogger(module_name)
