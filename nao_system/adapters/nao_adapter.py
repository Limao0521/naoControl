#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
adapters.nao_adapter

Adaptador que encapsula la comunicación con NAOqi y provee proxies seguros.
Incluye modos de simulación cuando NAOqi no está disponible. El encabezado
añadido es informativo y no altera el comportamiento del módulo.
Fecha: 2025-09-08
"""

try:
    from naoqi import ALProxy
    import almath
    NAOQI_AVAILABLE = True
except ImportError:
    ALProxy = None
    almath = None
    NAOQI_AVAILABLE = False

from ..interfaces.base_interfaces import IMotionService, ISensorReader
from ..core.config import NAO_IP, NAO_PORT, SAFETY_LIMITS

class NAOAdapter(object):
    """Adaptador para comunicación con NAOqi"""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.connected = False
        self.proxies = {}
        
        if NAOQI_AVAILABLE:
            self._connect()
        else:
            if self.logger:
                self.logger.warning("NAOqi no disponible - modo simulación")
    
    def _connect(self):
        """Conectar a NAOqi y crear proxies"""
        try:
            # Crear proxies básicos
            self.proxies = {
                'motion': ALProxy("ALMotion", NAO_IP, NAO_PORT),
                'posture': ALProxy("ALRobotPosture", NAO_IP, NAO_PORT),
                'memory': ALProxy("ALMemory", NAO_IP, NAO_PORT),
                'tts': ALProxy("ALTextToSpeech", NAO_IP, NAO_PORT),
                'leds': ALProxy("ALLeds", NAO_IP, NAO_PORT),
                'battery': ALProxy("ALBattery", NAO_IP, NAO_PORT),
                'behavior': ALProxy("ALBehaviorManager", NAO_IP, NAO_PORT),
                'life': ALProxy("ALAutonomousLife", NAO_IP, NAO_PORT)
            }
            
            self.connected = True
            if self.logger:
                self.logger.info("Conectado a NAOqi exitosamente")
                
        except Exception as e:
            self.connected = False
            if self.logger:
                self.logger.error("Error conectando a NAOqi: {}".format(e))
    
    def get_proxy(self, proxy_name):
        """Obtener un proxy específico"""
        if not self.connected:
            return None
        return self.proxies.get(proxy_name)
    
    def is_connected(self):
        """Verificar si está conectado"""
        return self.connected
    
    def safe_call(self, proxy_name, method_name, *args, **kwargs):
        """Llamada segura a método de proxy"""
        try:
            proxy = self.get_proxy(proxy_name)
            if proxy:
                method = getattr(proxy, method_name)
                return method(*args, **kwargs)
            else:
                if self.logger:
                    self.logger.warning("Proxy {} no disponible".format(proxy_name))
                return None
                
        except Exception as e:
            if self.logger:
                self.logger.error("Error en {}.{}: {}".format(proxy_name, method_name, e))
            return None

class NAOMotionService(IMotionService):
    """Servicio de movimiento para NAO"""
    
    def __init__(self, nao_adapter, logger=None):
        self.nao_adapter = nao_adapter
        self.logger = logger
        self.is_walking = False
        
        # Configurar movimiento de brazos si está conectado
        if self.nao_adapter.is_connected():
            self.nao_adapter.safe_call('motion', 'setMoveArmsEnabled', True, True)
    
    def _apply_safety_limits(self, vx, vy, wz):
        """Aplicar límites de seguridad a las velocidades"""
        limits = SAFETY_LIMITS['max_velocity']
        
        vx = max(-limits['vx'], min(limits['vx'], vx))
        vy = max(-limits['vy'], min(limits['vy'], vy))
        wz = max(-limits['wz'], min(limits['wz'], wz))
        
        return vx, vy, wz
    
    def walk(self, vx, vy, wz, move_config=None):
        """Caminar con velocidades especificadas"""
        if not self.nao_adapter.is_connected():
            if self.logger:
                self.logger.debug("Simulando caminata: vx={}, vy={}, wz={}".format(vx, vy, wz))
            return True
        
        try:
            # Aplicar límites de seguridad
            vx, vy, wz = self._apply_safety_limits(vx, vy, wz)
            
            if move_config:
                # Caminar con configuración específica
                result = self.nao_adapter.safe_call('motion', 'moveToward', vx, vy, wz, move_config)
            else:
                # Caminar básico
                result = self.nao_adapter.safe_call('motion', 'moveToward', vx, vy, wz)
            
            if result is not None:
                self.is_walking = any([vx, vy, wz])
                if self.logger:
                    self.logger.debug("Caminata actualizada: vx={}, vy={}, wz={}".format(vx, vy, wz))
                return True
            
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error en walk: {}".format(e))
            return False
    
    def stop_walk(self):
        """Detener caminata"""
        if not self.nao_adapter.is_connected():
            if self.logger:
                self.logger.debug("Simulando parada de caminata")
            return True
        
        try:
            result = self.nao_adapter.safe_call('motion', 'stopMove')
            if result is not None:
                self.is_walking = False
                if self.logger:
                    self.logger.info("Caminata detenida")
                return True
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error deteniendo caminata: {}".format(e))
            return False
    
    def set_posture(self, posture_name, speed=0.5):
        """Establecer postura"""
        if not self.nao_adapter.is_connected():
            if self.logger:
                self.logger.debug("Simulando postura: {}".format(posture_name))
            return True
        
        try:
            result = self.nao_adapter.safe_call('posture', 'goToPosture', posture_name, speed)
            if result:
                if self.logger:
                    self.logger.info("Postura cambiada a: {}".format(posture_name))
                return True
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error cambiando postura: {}".format(e))
            return False
    
    def get_motion_status(self):
        """Obtener estado del movimiento"""
        return {
            'is_walking': self.is_walking,
            'connected': self.nao_adapter.is_connected()
        }

class NAOSensorReader(ISensorReader):
    """Lector de sensores para NAO"""
    
    def __init__(self, nao_adapter, logger=None):
        self.nao_adapter = nao_adapter
        self.logger = logger
    
    def get_imu_data(self):
        """Obtener datos del IMU"""
        if not self.nao_adapter.is_connected():
            # Datos simulados
            return {
                'accel_x': 0.0, 'accel_y': 0.0, 'accel_z': 9.81,
                'gyro_x': 0.0, 'gyro_y': 0.0, 'gyro_z': 0.0,
                'angle_x': 0.0, 'angle_y': 0.0
            }
        
        try:
            # Leer acelerómetro
            accel = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/InertialSensor/AccelerometerX/Sensor/Value")
            accel_y = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/InertialSensor/AccelerometerY/Sensor/Value")
            accel_z = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/InertialSensor/AccelerometerZ/Sensor/Value")
            
            # Leer giroscopio
            gyro_x = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/InertialSensor/GyroscopeX/Sensor/Value")
            gyro_y = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/InertialSensor/GyroscopeY/Sensor/Value")
            gyro_z = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/InertialSensor/GyroscopeZ/Sensor/Value")
            
            # Leer ángulos
            angle_x = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value")
            angle_y = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value")
            
            return {
                'accel_x': accel or 0.0,
                'accel_y': accel_y or 0.0,
                'accel_z': accel_z or 9.81,
                'gyro_x': gyro_x or 0.0,
                'gyro_y': gyro_y or 0.0,
                'gyro_z': gyro_z or 0.0,
                'angle_x': angle_x or 0.0,
                'angle_y': angle_y or 0.0
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error leyendo IMU: {}".format(e))
            return None
    
    def get_fsr_data(self):
        """Obtener datos de sensores de presión en pies"""
        if not self.nao_adapter.is_connected():
            # Datos simulados
            return {
                'lfoot_fl': 0.5, 'lfoot_fr': 0.5, 'lfoot_rl': 0.5, 'lfoot_rr': 0.5,
                'rfoot_fl': 0.5, 'rfoot_fr': 0.5, 'rfoot_rl': 0.5, 'rfoot_rr': 0.5
            }
        
        try:
            fsr_data = {}
            fsr_keys = [
                ('lfoot_fl', 'Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value'),
                ('lfoot_fr', 'Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value'),
                ('lfoot_rl', 'Device/SubDeviceList/LFoot/FSR/RearLeft/Sensor/Value'),
                ('lfoot_rr', 'Device/SubDeviceList/LFoot/FSR/RearRight/Sensor/Value'),
                ('rfoot_fl', 'Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value'),
                ('rfoot_fr', 'Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value'),
                ('rfoot_rl', 'Device/SubDeviceList/RFoot/FSR/RearLeft/Sensor/Value'),
                ('rfoot_rr', 'Device/SubDeviceList/RFoot/FSR/RearRight/Sensor/Value')
            ]
            
            for key, memory_key in fsr_keys:
                value = self.nao_adapter.safe_call('memory', 'getData', memory_key)
                fsr_data[key] = value or 0.0
            
            return fsr_data
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error leyendo FSR: {}".format(e))
            return None
    
    def get_touch_sensors(self):
        """Obtener estado de sensores táctiles"""
        if not self.nao_adapter.is_connected():
            return {'middle': False, 'front': False, 'rear': False}
        
        try:
            middle = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/Head/Touch/Middle/Sensor/Value")
            front = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/Head/Touch/Front/Sensor/Value")
            rear = self.nao_adapter.safe_call('memory', 'getData', "Device/SubDeviceList/Head/Touch/Rear/Sensor/Value")
            
            return {
                'middle': bool(middle),
                'front': bool(front),
                'rear': bool(rear)
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error leyendo sensores táctiles: {}".format(e))
            return None
