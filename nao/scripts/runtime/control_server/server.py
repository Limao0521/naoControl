#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
server.py - Control Server Refactorizado

Servidor WebSocket modular usando patrones de diseño:
- Command Pattern para actions
- Strategy Pattern para movimiento  
- Factory Pattern para crear comandos
- Facade Pattern para NAOqi
- Observer Pattern para eventos

Versión 2.0 - Arquitectura modular y mantenible
"""

from __future__ import print_function
import sys, os, time, threading, json, socket, errno, signal
from datetime import datetime

# Rutas
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/home/nao/SimpleWebSocketServer-0.1.2")
from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer

# Importar componentes modulares
from facades.nao_facade import NAOFacade
from command_factory import CommandFactory
from strategies.movement_strategies import MovementContext

# Importar sistema de logging
try:
    from logger import create_logger
    logger = create_logger("CONTROL_V2")
    logger.info("Sistema de logging centralizado conectado - Control Server v2.0")
except ImportError:
    class FallbackLogger:
        def debug(self, msg): print("DEBUG [CONTROL_V2] {}".format(msg))
        def info(self, msg): print("INFO [CONTROL_V2] {}".format(msg))
        def warning(self, msg): print("WARNING [CONTROL_V2] {}".format(msg))
        def error(self, msg): print("ERROR [CONTROL_V2] {}".format(msg))
        def critical(self, msg): print("CRITICAL [CONTROL_V2] {}".format(msg))
    logger = FallbackLogger()
    print("WARNING: Sistema de logging centralizado no disponible, usando fallback - Control Server v2.0")

# Configuración
IP_NAO = "127.0.0.1"
PORT_NAO = 9559
WS_PORT = 6671
WATCHDOG = 0.6

class ModularControlServer(object):
    """
    Servidor de control modular usando patrones de diseño.
    Centraliza la lógica de inicialización y gestión de componentes.
    """
    
    def __init__(self):
        """Inicializar servidor modular."""
        self.nao_facade = None
        self.command_factory = None
        self.movement_context = None
        self.websocket_server = None
        self.watchdog_thread = None
        self.adaptive_walker = None
        
        # Estado global
        self.last_walk_time = time.time()
        self.server_running = False
        
        logger.info("ModularControlServer v2.0 inicializado")
    
    def initialize_components(self):
        """Inicializar todos los componentes del servidor."""
        try:
            # 1. Inicializar facade NAO
            logger.info("Inicializando NAO Facade...")
            self.nao_facade = NAOFacade(IP_NAO, PORT_NAO, logger)
            
            # Verificar salud de conexión
            health = self.nao_facade.health_check()
            logger.info("NAO Health Check: {:.1f}% ({}/{} proxies disponibles)".format(
                health["health_score"], len(health["available_proxies"]), health["total_proxies"]))
            
            if not health["is_healthy"]:
                logger.warning("NAO conexión no óptima, continuando con proxies disponibles")
            
            # 2. Inicializar adaptive walker si está disponible
            try:
                from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
                self.adaptive_walker = AdaptiveWalkLightGBM("models_npz_automl", mode="production")
                logger.info("LightGBM AutoML inicializada - MODO PRODUCTION")
            except (ImportError, AttributeError, SyntaxError) as e:
                logger.warning("LightGBM AutoML adaptativo no disponible: {}".format(e))
                self.adaptive_walker = None
            
            # 3. Inicializar contexto de movimiento
            logger.info("Inicializando Movement Context...")
            self.movement_context = MovementContext(self.nao_facade, logger, self.adaptive_walker)
            
            # 4. Inicializar factory de comandos
            logger.info("Inicializando Command Factory...")
            self.command_factory = CommandFactory(self.nao_facade, logger)
            
            # 5. Inicializar watchdog
            self._start_watchdog()
            
            logger.info("Todos los componentes inicializados exitosamente")
            return True
            
        except Exception as e:
            logger.critical("Error fatal inicializando componentes: {}".format(e))
            return False
    
    def _start_watchdog(self):
        """Iniciar hilo de watchdog para detener robot si no recibe comandos."""
        def watchdog_loop():
            logger.info("Watchdog iniciado (timeout: {:.1f}s)".format(WATCHDOG))
            while self.server_running:
                time.sleep(0.05)
                if time.time() - self.last_walk_time > WATCHDOG:
                    if self.nao_facade:
                        self.nao_facade.stop_move()
                    self.last_walk_time = time.time()
        
        self.watchdog_thread = threading.Thread(target=watchdog_loop)
        self.watchdog_thread.daemon = True
        self.watchdog_thread.start()
    
    def start_server(self):
        """Iniciar servidor WebSocket."""
        if not self.initialize_components():
            logger.critical("No se pudieron inicializar componentes, abortando")
            return False
        
        logger.info("Iniciando WebSocket Server en ws://0.0.0.0:{}".format(WS_PORT))
        
        # Crear clase WebSocket con acceso a componentes
        server_instance = self
        
        class ModularWebSocket(WebSocket):
            def handleConnected(self):
                logger.info("WS: Cliente conectado desde {}".format(self.address))
                # Enviar información inicial
                try:
                    info = {
                        "server_info": {
                            "version": "2.0.0",
                            "architecture": "modular",
                            "patterns": ["Command", "Strategy", "Factory", "Facade"],
                            "health": server_instance.nao_facade.health_check() if server_instance.nao_facade else {},
                            "movement_strategies": server_instance.movement_context.get_available_strategies() if server_instance.movement_context else [],
                            "supported_actions": server_instance.command_factory.get_supported_actions() if server_instance.command_factory else []
                        }
                    }
                    self.sendMessage(json.dumps(info))
                except Exception as e:
                    logger.warning("Error enviando info inicial: {}".format(e))

            def handleClose(self):
                logger.info("WS: Cliente desconectado desde {}".format(self.address))

            def handleMessage(self):
                try:
                    # Parsear mensaje JSON
                    raw = self.data.strip()
                    logger.debug("WS: Mensaje recibido: {}".format(raw))
                    
                    try:
                        message = json.loads(raw)
                    except ValueError as e:
                        logger.warning("WS: JSON inválido: {} - Error: {}".format(raw, e))
                        return
                    
                    # Obtener action
                    action = message.get("action")
                    if not action:
                        logger.warning("WS: Mensaje sin action: {}".format(message))
                        return
                    
                    # Actualizar timestamp para watchdog si es comando de movimiento
                    if action in ['walk', 'walkTo', 'turnLeft', 'turnRight']:
                        server_instance.last_walk_time = time.time()
                    
                    # Crear y ejecutar comando
                    command = server_instance.command_factory.create_command(action)
                    
                    if command:
                        # Inyectar dependencias adicionales si es necesario
                        if hasattr(command, 'movement_context') and server_instance.movement_context:
                            command.movement_context = server_instance.movement_context
                        
                        # Ejecutar comando
                        success = command.execute(message, self)
                        
                        if success:
                            logger.debug("Comando {} ejecutado exitosamente".format(action))
                        else:
                            logger.warning("Comando {} falló en ejecución".format(action))
                    else:
                        # Comando no encontrado
                        error_response = {
                            action: {
                                "success": False,
                                "error": "Action no soportado: {}".format(action),
                                "supported_actions": server_instance.command_factory.get_supported_actions()
                            }
                        }
                        self.sendMessage(json.dumps(error_response))
                        logger.warning("WS: Action no soportado: {}".format(action))
                
                except Exception as e:
                    logger.error("WS: Error procesando mensaje: {}".format(e))
                    try:
                        error_response = {
                            "error": {
                                "success": False,
                                "error": "Error interno del servidor",
                                "details": str(e)
                            }
                        }
                        self.sendMessage(json.dumps(error_response))
                    except Exception:
                        pass  # Error enviando respuesta de error

        # Iniciar servidor
        try:
            self.server_running = True
            
            while True:
                try:
                    self.websocket_server = SimpleWebSocketServer("", WS_PORT, ModularWebSocket)
                    break
                except socket.error as e:
                    if e.errno == errno.EADDRINUSE:
                        logger.info("Puerto {} ocupado, reintentando en 3s...".format(WS_PORT))
                        time.sleep(3)
                    else:
                        raise
            
            logger.info("Control Server v2.0 iniciado exitosamente")
            logger.info("WebSocket activo en puerto {}".format(WS_PORT))
            
            # Mensaje TTS de confirmación
            if self.nao_facade:
                self.nao_facade.say("Control server modular iniciado")
            
            # Servir para siempre
            self.websocket_server.serveforever()
            
        except KeyboardInterrupt:
            logger.info("Interrupción de teclado detectada")
            self.shutdown()
        except Exception as e:
            logger.critical("Error fatal en servidor: {}".format(e))
            self.shutdown()
        
        return True
    
    def shutdown(self):
        """Cerrar servidor y limpiar recursos."""
        logger.info("Cerrando Control Server v2.0...")
        
        self.server_running = False
        
        # Mensaje TTS de cierre
        if self.nao_facade:
            self.nao_facade.say("Control server desconectado")
            time.sleep(1)  # Dar tiempo para que se reproduzca
        
        # Cerrar servidor WebSocket
        if self.websocket_server:
            try:
                self.websocket_server.close()
            except Exception as e:
                logger.warning("Error cerrando WebSocket server: {}".format(e))
        
        # Detener movimiento del robot
        if self.nao_facade:
            self.nao_facade.stop_move()
        
        # Esperar watchdog thread
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            self.watchdog_thread.join(timeout=2)
        
        logger.info("Control Server v2.0 cerrado correctamente")

# Instancia global del servidor
control_server = ModularControlServer()

def cleanup_handler(signum, frame):
    """Manejador de señales para cierre limpio."""
    logger.info("Señal {} recibida, cerrando servidor...".format(signum))
    control_server.shutdown()
    sys.exit(0)

if __name__ == "__main__":
    # Configurar manejadores de señales
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)
    
    # Iniciar servidor
    success = control_server.start_server()
    sys.exit(0 if success else 1)