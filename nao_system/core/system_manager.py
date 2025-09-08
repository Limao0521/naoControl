#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
core.system_manager

Propósito: Gestor principal (SystemManager) que coordina el ciclo de vida
de los servicios del sistema NAO. Este archivo contiene únicamente código
operacional; el encabezado añadido es informativo y no cambia la lógica.
Fecha: 2025-09-08
"""

import threading
import time
from datetime import datetime

from ..interfaces.base_interfaces import ISystemManager
from ..core.config import SERVICES_CONFIG
from ..services.logging_service import LoggingService, create_logger
from ..adapters.nao_adapter import NAOAdapter, NAOMotionService, NAOSensorReader

class SystemManager(ISystemManager):
    """Gestor principal del sistema NAO"""
    
    def __init__(self):
        self.services = {}
        self.running = False
        self.logger = None
        
        # Inicializar logging primero
        self._init_logging()
        
        # Crear adaptador NAO
        self.nao_adapter = NAOAdapter(self.logger)
        
        # Inicializar servicios core
        self._init_core_services()
        
        self.logger.info("SystemManager inicializado")
    
    def _init_logging(self):
        """Inicializar sistema de logging"""
        try:
            logging_service = LoggingService()
            if logging_service.start():
                self.services['logging'] = logging_service
            
            self.logger = create_logger("SYSTEM")
            
        except Exception as e:
            print("Error inicializando logging: {}".format(e))
            # Crear logger fallback
            class FallbackLogger:
                def debug(self, msg): print("DEBUG [SYSTEM] {}".format(msg))
                def info(self, msg): print("INFO [SYSTEM] {}".format(msg))
                def warning(self, msg): print("WARNING [SYSTEM] {}".format(msg))
                def error(self, msg): print("ERROR [SYSTEM] {}".format(msg))
                def critical(self, msg): print("CRITICAL [SYSTEM] {}".format(msg))
            
            self.logger = FallbackLogger()
    
    def _init_core_services(self):
        """Inicializar servicios principales"""
        try:
            # Servicio de movimiento
            motion_service = NAOMotionService(self.nao_adapter, self.logger)
            self.services['motion'] = motion_service
            
            # Servicio de sensores
            sensor_service = NAOSensorReader(self.nao_adapter, self.logger)
            self.services['sensors'] = sensor_service
            
            self.logger.info("Servicios core inicializados")
            
        except Exception as e:
            self.logger.error("Error inicializando servicios core: {}".format(e))
    
    def register_service(self, name, service):
        """Registrar un servicio personalizado"""
        try:
            self.services[name] = service
            self.logger.info("Servicio '{}' registrado".format(name))
            return True
            
        except Exception as e:
            self.logger.error("Error registrando servicio '{}': {}".format(name, e))
            return False
    
    def get_service(self, name):
        """Obtener un servicio por nombre"""
        return self.services.get(name)
    
    def start_services(self):
        """Iniciar todos los servicios configurados"""
        try:
            self.running = True
            started_services = []
            
            for service_name, config in SERVICES_CONFIG.items():
                if config.get('enabled', True) and config.get('auto_start', True):
                    service = self.services.get(service_name)
                    if service and hasattr(service, 'start'):
                        try:
                            if service.start():
                                started_services.append(service_name)
                                self.logger.info("Servicio '{}' iniciado".format(service_name))
                            else:
                                self.logger.warning("Fallo iniciando servicio '{}'".format(service_name))
                        except Exception as e:
                            self.logger.error("Error iniciando '{}': {}".format(service_name, e))
            
            self.logger.info("Sistema iniciado - Servicios activos: {}".format(started_services))
            return len(started_services) > 0
            
        except Exception as e:
            self.logger.error("Error iniciando servicios: {}".format(e))
            return False
    
    def stop_services(self):
        """Detener todos los servicios"""
        try:
            self.running = False
            stopped_services = []
            
            for service_name, service in self.services.items():
                if hasattr(service, 'stop'):
                    try:
                        if service.stop():
                            stopped_services.append(service_name)
                            self.logger.info("Servicio '{}' detenido".format(service_name))
                    except Exception as e:
                        self.logger.error("Error deteniendo '{}': {}".format(service_name, e))
            
            self.logger.info("Sistema detenido - Servicios cerrados: {}".format(stopped_services))
            return True
            
        except Exception as e:
            self.logger.error("Error deteniendo servicios: {}".format(e))
            return False
    
    def get_system_status(self):
        """Obtener estado del sistema"""
        status = {
            'running': self.running,
            'nao_connected': self.nao_adapter.is_connected(),
            'services': {},
            'timestamp': datetime.now().isoformat()
        }
        
        for service_name, service in self.services.items():
            service_status = {
                'available': service is not None,
                'type': type(service).__name__
            }
            
            # Obtener estado específico si está disponible
            if hasattr(service, 'get_status'):
                try:
                    service_status.update(service.get_status())
                except Exception:
                    pass
            
            status['services'][service_name] = service_status
        
        return status
    
    def walk(self, vx, vy, wz, move_config=None):
        """API simplificada para caminar"""
        motion_service = self.get_service('motion')
        if motion_service:
            return motion_service.walk(vx, vy, wz, move_config)
        return False
    
    def stop_walk(self):
        """API simplificada para detener caminata"""
        motion_service = self.get_service('motion')
        if motion_service:
            return motion_service.stop_walk()
        return False
    
    def set_posture(self, posture_name):
        """API simplificada para cambiar postura"""
        motion_service = self.get_service('motion')
        if motion_service:
            return motion_service.set_posture(posture_name)
        return False
    
    def get_sensor_data(self):
        """API simplificada para obtener datos de sensores"""
        sensor_service = self.get_service('sensors')
        if sensor_service:
            return {
                'imu': sensor_service.get_imu_data(),
                'fsr': sensor_service.get_fsr_data(),
                'touch': sensor_service.get_touch_sensors()
            }
        return None
    
    def say(self, text):
        """API simplificada para TTS"""
        return self.nao_adapter.safe_call('tts', 'say', text)
    
    def cleanup(self):
        """Limpiar recursos del sistema"""
        self.logger.info("Iniciando limpieza del sistema...")
        self.stop_services()
        self.logger.info("Sistema limpiado correctamente")

# Instancia global del sistema
_system_manager = None

def get_system_manager():
    """Obtener instancia global del sistema"""
    global _system_manager
    if _system_manager is None:
        _system_manager = SystemManager()
    return _system_manager

def initialize_system():
    """Inicializar y comenzar el sistema"""
    system = get_system_manager()
    return system.start_services()

def shutdown_system():
    """Cerrar el sistema completamente"""
    global _system_manager
    if _system_manager:
        _system_manager.cleanup()
        _system_manager = None
