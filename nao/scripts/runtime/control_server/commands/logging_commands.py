#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
logging_commands.py - Comandos de data logging CSV

Implementa comandos para controlar el sistema de logging de datos
de sensores para entrenamiento de modelos ML usando Command Pattern.
"""

from __future__ import print_function
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand


class StartLoggingCommand(BaseCommand):
    """Comando para iniciar logging de datos de sensores."""
    
    def __init__(self, nao_facade, logger, logging_state=None, data_logger_class=None, sensor_reader_class=None):
        """
        Inicializar comando con estado compartido.
        
        Args:
            nao_facade: Facade NAO
            logger: Logger
            logging_state: Diccionario compartido con estado de logging
            data_logger_class: Clase DataLogger (para instanciar)
            sensor_reader_class: Clase SensorReader (para instanciar)
        """
        super(StartLoggingCommand, self).__init__(nao_facade, logger)
        self.logging_state = logging_state or {"active": False, "instance": None, "sensor_reader": None}
        self.data_logger_class = data_logger_class
        self.sensor_reader_class = sensor_reader_class
    
    def execute(self, message, websocket):
        """Ejecutar comando startLogging."""
        try:
            # Verificar disponibilidad
            if not self.data_logger_class or not self.sensor_reader_class:
                websocket.sendMessage(json.dumps({
                    "startLogging": {"success": False, "error": "Data logger no disponible"}
                }))
                return False
            
            # Verificar si ya está activo
            if self.logging_state.get("active", False):
                websocket.sendMessage(json.dumps({
                    "startLogging": {"success": False, "error": "Logging ya activo"}
                }))
                return False
            
            # Obtener parámetros
            duration = float(message.get("duration", 300))  # 5 minutos por defecto
            frequency = float(message.get("frequency", 10))  # 10 Hz por defecto
            output_file = message.get("output", "")
            
            # Generar nombre de archivo si no se proporciona
            if not output_file:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = "/home/nao/logs/adaptive_data_{}.csv".format(timestamp)
                # En Windows para testing
                if os.name == 'nt':
                    output_file = "C:/tmp/adaptive_data_{}.csv".format(timestamp)
            
            # Crear directorio si no existe
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                except Exception:
                    pass
            
            # Inicializar componentes
            ip = getattr(self.nao, 'ip', '127.0.0.1')
            port = getattr(self.nao, 'port', 9559)
            
            sensor_reader = self.sensor_reader_class(ip, port)
            data_logger = self.data_logger_class(output_file, sensor_reader)
            
            if data_logger.start_logging():
                self.logging_state["active"] = True
                self.logging_state["instance"] = data_logger
                self.logging_state["sensor_reader"] = sensor_reader
                
                response = {
                    "startLogging": {
                        "success": True,
                        "output": output_file,
                        "duration": duration,
                        "frequency": frequency
                    }
                }
                self.logger.info("DataLogger: Logging iniciado: {} ({}s @ {}Hz)".format(
                    output_file, duration, frequency))
            else:
                response = {"startLogging": {"success": False, "error": "No se pudo iniciar logging"}}
            
            websocket.sendMessage(json.dumps(response))
            return response["startLogging"]["success"]
            
        except Exception as e:
            self.logger.error("Error iniciando logging: {}".format(e))
            websocket.sendMessage(json.dumps({
                "startLogging": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "startLogging"


class StopLoggingCommand(BaseCommand):
    """Comando para detener logging de datos."""
    
    def __init__(self, nao_facade, logger, logging_state=None):
        super(StopLoggingCommand, self).__init__(nao_facade, logger)
        self.logging_state = logging_state or {"active": False, "instance": None}
    
    def execute(self, message, websocket):
        """Ejecutar comando stopLogging."""
        try:
            if not self.logging_state.get("active") or not self.logging_state.get("instance"):
                websocket.sendMessage(json.dumps({
                    "stopLogging": {"success": False, "error": "Logging no activo"}
                }))
                return False
            
            data_logger = self.logging_state["instance"]
            samples_written = getattr(data_logger, 'samples_written', 0)
            
            data_logger.stop_logging()
            self.logging_state["active"] = False
            self.logging_state["instance"] = None
            self.logging_state["sensor_reader"] = None
            
            response = {
                "stopLogging": {
                    "success": True,
                    "samples": samples_written
                }
            }
            websocket.sendMessage(json.dumps(response))
            self.logger.info("DataLogger: Logging detenido. Muestras: {}".format(samples_written))
            return True
            
        except Exception as e:
            self.logger.error("Error deteniendo logging: {}".format(e))
            websocket.sendMessage(json.dumps({
                "stopLogging": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "stopLogging"


class GetLoggingStatusCommand(BaseCommand):
    """Comando para obtener estado del logging."""
    
    def __init__(self, nao_facade, logger, logging_state=None, data_logger_available=False):
        super(GetLoggingStatusCommand, self).__init__(nao_facade, logger)
        self.logging_state = logging_state or {"active": False, "instance": None}
        self.data_logger_available = data_logger_available
    
    def execute(self, message, websocket):
        """Ejecutar comando getLoggingStatus."""
        try:
            samples = 0
            output_file = ""
            
            data_logger = self.logging_state.get("instance")
            if data_logger:
                samples = getattr(data_logger, 'samples_written', 0)
                output_file = getattr(data_logger, 'output_file', "")
            
            response = {
                "loggingStatus": {
                    "active": self.logging_state.get("active", False),
                    "available": self.data_logger_available,
                    "samples": samples,
                    "output": output_file
                }
            }
            websocket.sendMessage(json.dumps(response))
            return True
            
        except Exception as e:
            self.logger.error("Error obteniendo estado logging: {}".format(e))
            websocket.sendMessage(json.dumps({"loggingStatus": {"error": str(e)}}))
            return False
    
    def get_action_name(self):
        return "getLoggingStatus"


class LogSampleCommand(BaseCommand):
    """Comando para registrar una muestra manual."""
    
    def __init__(self, nao_facade, logger, logging_state=None):
        super(LogSampleCommand, self).__init__(nao_facade, logger)
        self.logging_state = logging_state or {"active": False, "instance": None}
    
    def execute(self, message, websocket):
        """Ejecutar comando logSample."""
        try:
            if not self.logging_state.get("active") or not self.logging_state.get("instance"):
                websocket.sendMessage(json.dumps({
                    "logSample": {"success": False, "error": "Logging no activo"}
                }))
                return False
            
            data_logger = self.logging_state["instance"]
            success = data_logger.log_sample()
            samples = getattr(data_logger, 'samples_written', 0)
            
            response = {
                "logSample": {
                    "success": success,
                    "samples": samples
                }
            }
            websocket.sendMessage(json.dumps(response))
            return success
            
        except Exception as e:
            self.logger.error("Error logging sample: {}".format(e))
            websocket.sendMessage(json.dumps({
                "logSample": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "logSample"


class SetLoggingFrequencyCommand(BaseCommand):
    """Comando para cambiar frecuencia de logging."""
    
    def __init__(self, nao_facade, logger, logging_state=None):
        super(SetLoggingFrequencyCommand, self).__init__(nao_facade, logger)
        self.logging_state = logging_state or {"active": False, "instance": None}
    
    def execute(self, message, websocket):
        """Ejecutar comando setLoggingFrequency."""
        try:
            frequency = float(message.get("frequency", 10))
            
            if frequency <= 0 or frequency > 100:
                websocket.sendMessage(json.dumps({
                    "setLoggingFrequency": {
                        "success": False,
                        "error": "Frecuencia debe estar entre 0.1 y 100 Hz"
                    }
                }))
                return False
            
            data_logger = self.logging_state.get("instance")
            if data_logger and hasattr(data_logger, 'set_frequency'):
                data_logger.set_frequency(frequency)
            
            response = {
                "setLoggingFrequency": {
                    "success": True,
                    "frequency": frequency
                }
            }
            websocket.sendMessage(json.dumps(response))
            self.logger.info("Logging frequency set to {} Hz".format(frequency))
            return True
            
        except Exception as e:
            self.logger.error("Error setting logging frequency: {}".format(e))
            websocket.sendMessage(json.dumps({
                "setLoggingFrequency": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "setLoggingFrequency"
