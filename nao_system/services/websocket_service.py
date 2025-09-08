#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
services.websocket_service

Implementación de servidor WebSocket que expone la API JSON para control
remoto del robot. Contiene un handler que delega en `SystemManager`.
Encabezado informativo añadido.
Fecha: 2025-09-08
"""

import json
import threading
import time
from datetime import datetime

try:
    from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    # Clases dummy para compatibilidad
    class WebSocket(object):
        def __init__(self, server, sock, address):
            pass
        def sendMessage(self, message):
            pass
    
    class SimpleWebSocketServer(object):
        def __init__(self, host, port, handler):
            pass
        def serveforever(self):
            pass
        def close(self):
            pass

from ..interfaces.base_interfaces import IWebSocketServer
from ..core.config import WEBSOCKET_PORT

class NAOWebSocketHandler(WebSocket):
    """Manejador de conexiones WebSocket"""
    
    def __init__(self, server, sock, address):
        super(NAOWebSocketHandler, self).__init__(server, sock, address)
        self.system_manager = None
        self.logger = None
    
    def set_system_manager(self, system_manager):
        """Asignar el system manager"""
        self.system_manager = system_manager
        if hasattr(system_manager, 'logger'):
            self.logger = system_manager.logger
    
    def handleConnected(self):
        if self.logger:
            self.logger.info("Cliente WebSocket conectado desde: {}".format(self.address))
        
        # Enviar estado inicial
        self.send_status()
    
    def handleClose(self):
        if self.logger:
            self.logger.info("Cliente WebSocket desconectado: {}".format(self.address))
    
    def handleMessage(self):
        """Procesar mensajes recibidos"""
        try:
            if not self.data:
                return
            
            # Parsear mensaje JSON
            try:
                msg = json.loads(self.data)
            except ValueError as e:
                self.send_error("JSON inválido: {}".format(e))
                return
            
            action = msg.get("action", "")
            
            if self.logger:
                self.logger.debug("WebSocket recibido: {}".format(action))
            
            # Procesar diferentes acciones
            if action == "walk":
                self.handle_walk(msg)
            elif action == "stop":
                self.handle_stop()
            elif action == "posture":
                self.handle_posture(msg)
            elif action == "say":
                self.handle_say(msg)
            elif action == "getStatus":
                self.send_status()
            elif action == "adaptiveWalk":
                self.handle_adaptive_walk(msg)
            elif action == "getSensorData":
                self.handle_get_sensor_data()
            else:
                self.send_error("Acción desconocida: {}".format(action))
        
        except Exception as e:
            if self.logger:
                self.logger.error("Error procesando mensaje WebSocket: {}".format(e))
            self.send_error("Error interno: {}".format(e))
    
    def handle_walk(self, msg):
        """Manejar comando de caminata"""
        try:
            vx = float(msg.get("x", 0.0))
            vy = float(msg.get("y", 0.0))
            wz = float(msg.get("theta", 0.0))
            
            if self.system_manager:
                success = self.system_manager.walk(vx, vy, wz)
                self.send_response({"action": "walk", "success": success})
            else:
                self.send_error("Sistema no disponible")
        
        except Exception as e:
            self.send_error("Error en walk: {}".format(e))
    
    def handle_stop(self):
        """Manejar comando de parada"""
        try:
            if self.system_manager:
                success = self.system_manager.stop_walk()
                self.send_response({"action": "stop", "success": success})
            else:
                self.send_error("Sistema no disponible")
        
        except Exception as e:
            self.send_error("Error en stop: {}".format(e))
    
    def handle_posture(self, msg):
        """Manejar cambio de postura"""
        try:
            posture = msg.get("posture", "Stand")
            
            if self.system_manager:
                success = self.system_manager.set_posture(posture)
                self.send_response({"action": "posture", "posture": posture, "success": success})
            else:
                self.send_error("Sistema no disponible")
        
        except Exception as e:
            self.send_error("Error en posture: {}".format(e))
    
    def handle_say(self, msg):
        """Manejar comando de TTS"""
        try:
            text = msg.get("text", "")
            
            if self.system_manager:
                success = self.system_manager.say(text)
                self.send_response({"action": "say", "text": text, "success": success is not None})
            else:
                self.send_error("Sistema no disponible")
        
        except Exception as e:
            self.send_error("Error en say: {}".format(e))
    
    def handle_adaptive_walk(self, msg):
        """Manejar caminata adaptiva"""
        try:
            if not self.system_manager:
                self.send_error("Sistema no disponible")
                return
            
            adaptive_service = self.system_manager.get_service('adaptive_walk')
            if not adaptive_service:
                self.send_error("Servicio de caminata adaptiva no disponible")
                return
            
            command = msg.get("command", "")
            
            if command == "start":
                x = float(msg.get("x", 0.02))
                y = float(msg.get("y", 0.0))
                theta = float(msg.get("theta", 0.0))
                success = adaptive_service.start_adaptive_walk(x, y, theta)
                self.send_response({"action": "adaptiveWalk", "command": "start", "success": success})
            
            elif command == "stop":
                success = adaptive_service.stop_adaptive_walk()
                self.send_response({"action": "adaptiveWalk", "command": "stop", "success": success})
            
            elif command == "setMode":
                mode = msg.get("mode", "production")
                success = adaptive_service.set_mode(mode)
                self.send_response({"action": "adaptiveWalk", "command": "setMode", "mode": mode, "success": success})
            
            elif command == "getStatus":
                status = adaptive_service.get_status()
                self.send_response({"action": "adaptiveWalk", "command": "getStatus", "status": status})
            
            else:
                self.send_error("Comando adaptiveWalk desconocido: {}".format(command))
        
        except Exception as e:
            self.send_error("Error en adaptiveWalk: {}".format(e))
    
    def handle_get_sensor_data(self):
        """Obtener datos de sensores"""
        try:
            if self.system_manager:
                sensor_data = self.system_manager.get_sensor_data()
                self.send_response({"action": "getSensorData", "data": sensor_data})
            else:
                self.send_error("Sistema no disponible")
        
        except Exception as e:
            self.send_error("Error obteniendo datos de sensores: {}".format(e))
    
    def send_status(self):
        """Enviar estado del sistema"""
        try:
            if self.system_manager:
                status = self.system_manager.get_system_status()
                self.send_response({"action": "status", "data": status})
            else:
                self.send_response({"action": "status", "data": {"error": "Sistema no disponible"}})
        
        except Exception as e:
            self.send_error("Error obteniendo estado: {}".format(e))
    
    def send_response(self, data):
        """Enviar respuesta JSON"""
        try:
            message = json.dumps(data)
            self.sendMessage(message)
        except Exception as e:
            if self.logger:
                self.logger.error("Error enviando respuesta WebSocket: {}".format(e))
    
    def send_error(self, error_msg):
        """Enviar mensaje de error"""
        try:
            error_data = {
                "error": True,
                "message": error_msg,
                "timestamp": datetime.now().isoformat()
            }
            self.send_response(error_data)
        except Exception as e:
            if self.logger:
                self.logger.error("Error enviando error WebSocket: {}".format(e))

class WebSocketService(IWebSocketServer):
    """Servicio WebSocket para el sistema NAO"""
    
    def __init__(self, system_manager, logger=None):
        self.system_manager = system_manager
        self.logger = logger
        self.server = None
        self.server_thread = None
        self.running = False
        
        # Configurar el manejador para que use el system manager
        def create_handler(server, sock, address):
            handler = NAOWebSocketHandler(server, sock, address)
            handler.set_system_manager(self.system_manager)
            return handler
        
        self.handler_factory = create_handler
    
    def start_server(self, port=None):
        """Iniciar servidor WebSocket"""
        if not WEBSOCKET_AVAILABLE:
            if self.logger:
                self.logger.error("SimpleWebSocketServer no disponible")
            return False
        
        try:
            port = port or WEBSOCKET_PORT
            
            # Crear servidor personalizado
            self.server = SimpleWebSocketServer('', port, self.handler_factory)
            self.server_thread = threading.Thread(target=self.server.serveforever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            self.running = True
            
            if self.logger:
                self.logger.info("Servidor WebSocket iniciado en puerto {}".format(port))
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error iniciando servidor WebSocket: {}".format(e))
            return False
    
    def stop_server(self):
        """Detener servidor WebSocket"""
        try:
            if self.server and self.running:
                self.server.close()
                self.running = False
                
                if self.logger:
                    self.logger.info("Servidor WebSocket detenido")
                
                return True
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error deteniendo servidor WebSocket: {}".format(e))
            return False
    
    def send_message(self, message):
        """Enviar mensaje a todos los clientes conectados"""
        # Esta funcionalidad requeriría mantener una lista de clientes activos
        # Por simplicidad, no implementada en esta versión
        pass
    
    def get_status(self):
        """Obtener estado del servicio"""
        return {
            'running': self.running,
            'port': WEBSOCKET_PORT,
            'websocket_available': WEBSOCKET_AVAILABLE
        }
