#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
sensor_reader.py - Lectura de sensores del robot NAO

Proporciona clases para leer sensores FSR, IMU, batería y otros
de forma segura y eficiente.
"""

from __future__ import print_function
import time
import math

try:
    from naoqi import ALProxy
except ImportError:
    ALProxy = None


class SensorReader(object):
    """
    Lector unificado de sensores del robot NAO.
    Maneja FSR, IMU, batería y otros sensores.
    """
    
    def __init__(self, ip="127.0.0.1", port=9559):
        """
        Inicializar lector de sensores.
        
        Args:
            ip: IP del robot
            port: Puerto NAOqi
        """
        self.ip = ip
        self.port = port
        self.memory = None
        self.battery = None
        self._connected = False
        
        self._connect()
    
    def _connect(self):
        """Conectar a los proxies necesarios."""
        if not ALProxy:
            return
            
        try:
            self.memory = ALProxy("ALMemory", self.ip, self.port)
            self.battery = ALProxy("ALBattery", self.ip, self.port)
            self._connected = True
        except Exception as e:
            print("SensorReader: Error conectando: {}".format(e))
            self._connected = False
    
    def is_connected(self):
        """Verificar si está conectado."""
        return self._connected
    
    # === FSR Sensors ===
    def get_fsr_left(self):
        """
        Obtener valores FSR del pie izquierdo.
        
        Returns:
            dict: {front_left, front_right, rear_left, rear_right, total}
        """
        if not self._connected:
            return None
            
        try:
            keys = [
                "Device/SubDeviceList/LFoot/FSR/FrontLeft/Sensor/Value",
                "Device/SubDeviceList/LFoot/FSR/FrontRight/Sensor/Value",
                "Device/SubDeviceList/LFoot/FSR/RearLeft/Sensor/Value",
                "Device/SubDeviceList/LFoot/FSR/RearRight/Sensor/Value",
                "Device/SubDeviceList/LFoot/FSR/TotalWeight/Sensor/Value"
            ]
            values = self.memory.getListData(keys)
            
            return {
                "front_left": values[0],
                "front_right": values[1],
                "rear_left": values[2],
                "rear_right": values[3],
                "total": values[4]
            }
        except Exception as e:
            return None
    
    def get_fsr_right(self):
        """
        Obtener valores FSR del pie derecho.
        
        Returns:
            dict: {front_left, front_right, rear_left, rear_right, total}
        """
        if not self._connected:
            return None
            
        try:
            keys = [
                "Device/SubDeviceList/RFoot/FSR/FrontLeft/Sensor/Value",
                "Device/SubDeviceList/RFoot/FSR/FrontRight/Sensor/Value",
                "Device/SubDeviceList/RFoot/FSR/RearLeft/Sensor/Value",
                "Device/SubDeviceList/RFoot/FSR/RearRight/Sensor/Value",
                "Device/SubDeviceList/RFoot/FSR/TotalWeight/Sensor/Value"
            ]
            values = self.memory.getListData(keys)
            
            return {
                "front_left": values[0],
                "front_right": values[1],
                "rear_left": values[2],
                "rear_right": values[3],
                "total": values[4]
            }
        except Exception as e:
            return None
    
    def get_fsr_all(self):
        """
        Obtener todos los valores FSR.
        
        Returns:
            dict: {left: {...}, right: {...}, total_weight}
        """
        left = self.get_fsr_left()
        right = self.get_fsr_right()
        
        total = 0.0
        if left and right:
            total = left.get("total", 0.0) + right.get("total", 0.0)
        
        return {
            "left": left,
            "right": right,
            "total_weight": total
        }
    
    def get_cop(self):
        """
        Calcular Centro de Presión (CoP) a partir de FSR.
        
        Returns:
            dict: {x, y} posición del CoP o None si no hay datos
        """
        left = self.get_fsr_left()
        right = self.get_fsr_right()
        
        if not left or not right:
            return None
        
        try:
            # Posiciones relativas de los sensores FSR (aproximadas en metros)
            # Pie izquierdo
            l_fl = left["front_left"]
            l_fr = left["front_right"]
            l_rl = left["rear_left"]
            l_rr = left["rear_right"]
            
            # Pie derecho
            r_fl = right["front_left"]
            r_fr = right["front_right"]
            r_rl = right["rear_left"]
            r_rr = right["rear_right"]
            
            # Total weight
            total = l_fl + l_fr + l_rl + l_rr + r_fl + r_fr + r_rl + r_rr
            
            if total < 0.01:  # Sin peso significativo
                return {"x": 0.0, "y": 0.0}
            
            # Coordenadas aproximadas de sensores (simplificado)
            # X: adelante (+) / atrás (-)
            # Y: izquierda (+) / derecha (-)
            
            cop_x = (0.05 * (l_fl + l_fr + r_fl + r_fr) - 
                     0.03 * (l_rl + l_rr + r_rl + r_rr)) / total
            
            cop_y = (0.04 * (l_fl + l_rl) - 0.04 * (r_fl + r_rl)) / total
            
            return {"x": cop_x, "y": cop_y}
            
        except Exception:
            return None
    
    # === IMU Sensors ===
    def get_imu(self):
        """
        Obtener datos de IMU (Inertial Measurement Unit).
        
        Returns:
            dict: {angle_x, angle_y, gyro_x, gyro_y, gyro_z, acc_x, acc_y, acc_z}
        """
        if not self._connected:
            return None
            
        try:
            keys = [
                "Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value",
                "Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value",
                "Device/SubDeviceList/InertialSensor/GyrX/Sensor/Value",
                "Device/SubDeviceList/InertialSensor/GyrY/Sensor/Value",
                "Device/SubDeviceList/InertialSensor/GyrZ/Sensor/Value",
                "Device/SubDeviceList/InertialSensor/AccX/Sensor/Value",
                "Device/SubDeviceList/InertialSensor/AccY/Sensor/Value",
                "Device/SubDeviceList/InertialSensor/AccZ/Sensor/Value"
            ]
            values = self.memory.getListData(keys)
            
            return {
                "angle_x": values[0],
                "angle_y": values[1],
                "gyro_x": values[2],
                "gyro_y": values[3],
                "gyro_z": values[4],
                "acc_x": values[5],
                "acc_y": values[6],
                "acc_z": values[7]
            }
        except Exception as e:
            return None
    
    def get_torso_angles(self):
        """
        Obtener ángulos del torso.
        
        Returns:
            dict: {pitch, roll}
        """
        imu = self.get_imu()
        if not imu:
            return None
        
        return {
            "pitch": imu.get("angle_y", 0.0),
            "roll": imu.get("angle_x", 0.0)
        }
    
    # === Battery ===
    def get_battery_level(self):
        """
        Obtener nivel de batería.
        
        Returns:
            int: Porcentaje de batería (0-100)
        """
        if not self._connected or not self.battery:
            return 100  # Default
            
        try:
            return self.battery.getBatteryCharge()
        except Exception:
            return 100
    
    def get_battery_info(self):
        """
        Obtener información completa de batería.
        
        Returns:
            dict: {level, low, full, charging}
        """
        level = self.get_battery_level()
        
        return {
            "level": level,
            "low": level < 20,
            "full": level >= 95,
            "charging": False  # NAO no tiene sensor de carga fácil
        }
    
    # === Touch Sensors ===
    def get_head_touch(self):
        """
        Obtener estado de sensores táctiles de cabeza.
        
        Returns:
            dict: {front, middle, rear}
        """
        if not self._connected:
            return None
            
        try:
            return {
                "front": self.memory.getData("FrontTactilTouched"),
                "middle": self.memory.getData("MiddleTactilTouched"),
                "rear": self.memory.getData("RearTactilTouched")
            }
        except Exception:
            return None
    
    def get_bumpers(self):
        """
        Obtener estado de bumpers de pies.
        
        Returns:
            dict: {left, right}
        """
        if not self._connected:
            return None
            
        try:
            return {
                "left": self.memory.getData("LeftBumperPressed"),
                "right": self.memory.getData("RightBumperPressed")
            }
        except Exception:
            return None
    
    # === Combined Reading ===
    def get_all_sensors(self):
        """
        Obtener lectura completa de todos los sensores.
        
        Returns:
            dict: Diccionario con todos los datos de sensores
        """
        return {
            "timestamp": time.time(),
            "fsr": self.get_fsr_all(),
            "imu": self.get_imu(),
            "cop": self.get_cop(),
            "battery": self.get_battery_info(),
            "head_touch": self.get_head_touch(),
            "bumpers": self.get_bumpers()
        }


class FSRReader(SensorReader):
    """Lector especializado para sensores FSR."""
    
    def read(self):
        """Leer solo FSR."""
        return self.get_fsr_all()


class IMUReader(SensorReader):
    """Lector especializado para IMU."""
    
    def read(self):
        """Leer solo IMU."""
        return self.get_imu()
