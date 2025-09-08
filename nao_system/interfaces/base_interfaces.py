#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
interfaces.base_interfaces

Definición de interfaces y contratos para los servicios del sistema NAO.
Estas clases son contratos abstractos; el encabezado añadido es informativo
y no modifica la implementación.
Fecha: 2025-09-08
"""

from abc import ABCMeta, abstractmethod

class ILogger(object):
    """Interface para servicios de logging"""
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def debug(self, message):
        pass
    
    @abstractmethod
    def info(self, message):
        pass
    
    @abstractmethod
    def warning(self, message):
        pass
    
    @abstractmethod
    def error(self, message):
        pass
    
    @abstractmethod
    def critical(self, message):
        pass

class IMotionService(object):
    """Interface para servicios de movimiento"""
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def walk(self, vx, vy, wz):
        pass
    
    @abstractmethod
    def stop_walk(self):
        pass
    
    @abstractmethod
    def set_posture(self, posture_name):
        pass
    
    @abstractmethod
    def get_motion_status(self):
        pass

class IAdaptiveWalk(object):
    """Interface para caminata adaptiva"""
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def predict_gait_parameters(self, vx, vy, wz):
        pass
    
    @abstractmethod
    def start_adaptive_walk(self, x, y, theta):
        pass
    
    @abstractmethod
    def stop_adaptive_walk(self):
        pass
    
    @abstractmethod
    def set_mode(self, mode):
        pass

class ISensorReader(object):
    """Interface para lectura de sensores"""
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def get_imu_data(self):
        pass
    
    @abstractmethod
    def get_fsr_data(self):
        pass
    
    @abstractmethod
    def get_touch_sensors(self):
        pass

class IWebSocketServer(object):
    """Interface para servidor WebSocket"""
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def start_server(self, port):
        pass
    
    @abstractmethod
    def stop_server(self):
        pass
    
    @abstractmethod
    def send_message(self, message):
        pass

class IVideoStreamer(object):
    """Interface para streaming de video"""
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def start_stream(self, resolution):
        pass
    
    @abstractmethod
    def stop_stream(self):
        pass
    
    @abstractmethod
    def get_latest_frame(self):
        pass

class ISystemManager(object):
    """Interface para el gestor principal del sistema"""
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def start_services(self):
        pass
    
    @abstractmethod
    def stop_services(self):
        pass
    
    @abstractmethod
    def get_system_status(self):
        pass
    
    @abstractmethod
    def register_service(self, name, service):
        pass
