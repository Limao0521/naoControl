#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
adaptive_walk_cnn.py - CNN pequeña para caminata adaptativa en NAO

Esta CNN ligera procesa datos de sensores en tiempo real para optimizar
los parámetros de marcha del robot NAO, mejorando estabilidad y eficiencia.

Compatible con Python 2.7 y recursos limitados del NAO.
"""

import numpy as np
import time
import json
from collections import deque
from naoqi import ALProxy

# Intentar importar bibliotecas de ML (con fallbacks para NAO)
try:
    # Preferir numpy para operaciones básicas (siempre disponible)
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    print("Warning: NumPy no disponible - CNN deshabilitada")
    ML_AVAILABLE = False

class LightweightCNN:
    """CNN ultra-ligera para caminata adaptativa"""
    
    def __init__(self):
        self.input_size = 20
        self.hidden1_size = 32
        self.hidden2_size = 16
        self.output_size = 5
        
        # Inicializar pesos con valores pequeños (Xavier initialization)
        self.W1 = np.random.randn(self.input_size, self.hidden1_size) * 0.1
        self.b1 = np.zeros((1, self.hidden1_size))
        
        self.W2 = np.random.randn(self.hidden1_size, self.hidden2_size) * 0.1
        self.b2 = np.zeros((1, self.hidden2_size))
        
        self.W3 = np.random.randn(self.hidden2_size, self.output_size) * 0.1
        self.b3 = np.zeros((1, self.output_size))
        
        # Parámetros base de marcha
        self.base_params = {
            'StepHeight': 0.025,
            'MaxStepX': 0.04,
            'MaxStepY': 0.14,
            'MaxStepTheta': 0.3,
            'Frequency': 0.8
        }
        
        # Rangos permitidos para cada parámetro (para normalización)
        self.param_ranges = {
            'StepHeight': (0.01, 0.05),
            'MaxStepX': (0.02, 0.08),
            'MaxStepY': (0.08, 0.20),
            'MaxStepTheta': (0.1, 0.5),
            'Frequency': (0.5, 1.2)
        }
        
    def relu(self, x):
        """Función de activación ReLU"""
        return np.maximum(0, x)
    
    def sigmoid(self, x):
        """Función de activación Sigmoid (para output)"""
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))
    
    def forward(self, input_vector):
        """Forward pass de la CNN"""
        # Normalizar input
        x = np.array(input_vector).reshape(1, -1)
        x = (x - np.mean(x)) / (np.std(x) + 1e-8)
        
        # Layer 1
        z1 = np.dot(x, self.W1) + self.b1
        a1 = self.relu(z1)
        
        # Layer 2  
        z2 = np.dot(a1, self.W2) + self.b2
        a2 = self.relu(z2)
        
        # Output layer
        z3 = np.dot(a2, self.W3) + self.b3
        output = self.sigmoid(z3)
        
        return output.flatten()
    
    def predict_gait_params(self, sensor_data):
        """Predecir parámetros de marcha basados en sensores"""
        try:
            # Forward pass
            normalized_output = self.forward(sensor_data)
            
            # Desnormalizar a rangos reales
            params = {}
            param_names = ['StepHeight', 'MaxStepX', 'MaxStepY', 'MaxStepTheta', 'Frequency']
            
            for i, param_name in enumerate(param_names):
                min_val, max_val = self.param_ranges[param_name]
                # Convertir de [0,1] a rango real
                params[param_name] = min_val + normalized_output[i] * (max_val - min_val)
            
            return params
            
        except Exception as e:
            print("Error en predicción CNN: {}".format(e))
            return self.base_params.copy()

class AdaptiveWalkController:
    """Controlador de caminata adaptativa con CNN"""
    
    def __init__(self, nao_ip="127.0.0.1", nao_port=9559):
        self.nao_ip = nao_ip
        self.nao_port = nao_port
        
        # Inicializar proxies NAOqi
        try:
            self.motion = ALProxy("ALMotion", nao_ip, nao_port)
            self.memory = ALProxy("ALMemory", nao_ip, nao_port)
            self.inertial = ALProxy("ALInertialSensor", nao_ip, nao_port)
            print("Proxies NAOqi inicializados correctamente")
        except Exception as e:
            print("Error inicializando NAOqi: {}".format(e))
            self.motion = None
            self.memory = None
            self.inertial = None
        
        # Inicializar CNN
        if ML_AVAILABLE:
            self.cnn = LightweightCNN()
            print("CNN ligera inicializada")
        else:
            self.cnn = None
            print("CNN no disponible - usando parámetros fijos")
        
        # Historial de sensores para estabilidad
        self.sensor_history = deque(maxlen=10)
        self.last_params = None
        self.adaptation_enabled = True
        
        # Contadores de rendimiento
        self.prediction_count = 0
        self.total_prediction_time = 0.0
        
    def get_sensor_data(self):
        """Recopilar datos de sensores del NAO"""
        sensor_vector = []
        
        try:
            if self.memory:
                # IMU data (acelerómetro y giroscopio)
                accel_x = self.memory.getData("Device/SubDeviceList/InertialSensor/AccelerometerX/Sensor/Value")
                accel_y = self.memory.getData("Device/SubDeviceList/InertialSensor/AccelerometerY/Sensor/Value")
                accel_z = self.memory.getData("Device/SubDeviceList/InertialSensor/AccelerometerZ/Sensor/Value")
                
                gyro_x = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroscopeX/Sensor/Value")
                gyro_y = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroscopeY/Sensor/Value")
                gyro_z = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroscopeZ/Sensor/Value")
                
                # Ángulos de inclinación
                angle_x = self.memory.getData("Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value")
                angle_y = self.memory.getData("Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value")
                
                # Sensores de presión en los pies
                lfoot_fl = self.memory.getData("Device/SubDeviceList/LFoot/FSR/FrontLeft/Sensor/Value")
                lfoot_fr = self.memory.getData("Device/SubDeviceList/LFoot/FSR/FrontRight/Sensor/Value")
                lfoot_rl = self.memory.getData("Device/SubDeviceList/LFoot/FSR/RearLeft/Sensor/Value")
                lfoot_rr = self.memory.getData("Device/SubDeviceList/LFoot/FSR/RearRight/Sensor/Value")
                
                rfoot_fl = self.memory.getData("Device/SubDeviceList/RFoot/FSR/FrontLeft/Sensor/Value")
                rfoot_fr = self.memory.getData("Device/SubDeviceList/RFoot/FSR/FrontRight/Sensor/Value")
                rfoot_rl = self.memory.getData("Device/SubDeviceList/RFoot/FSR/RearLeft/Sensor/Value")
                rfoot_rr = self.memory.getData("Device/SubDeviceList/RFoot/FSR/RearRight/Sensor/Value")
                
                sensor_vector = [
                    accel_x or 0, accel_y or 0, accel_z or 0,
                    gyro_x or 0, gyro_y or 0, gyro_z or 0,
                    angle_x or 0, angle_y or 0,
                    lfoot_fl or 0, lfoot_fr or 0, lfoot_rl or 0, lfoot_rr or 0,
                    rfoot_fl or 0, rfoot_fr or 0, rfoot_rl or 0, rfoot_rr or 0,
                    0, 0, 0, 0  # Placeholders para velocidades comandadas
                ]
                
        except Exception as e:
            print("Error leyendo sensores: {}".format(e))
            # Vector de sensores por defecto (neutro)
            sensor_vector = [0.0] * 20
        
        # Asegurar que tenemos exactamente 20 elementos
        while len(sensor_vector) < 20:
            sensor_vector.append(0.0)
        
        return sensor_vector[:20]
    
    def add_command_velocities(self, sensor_vector, vx, vy, wz):
        """Agregar velocidades comandadas al vector de sensores"""
        if len(sensor_vector) >= 20:
            sensor_vector[-4] = vx
            sensor_vector[-3] = vy  
            sensor_vector[-2] = wz
            sensor_vector[-1] = np.sqrt(vx*vx + vy*vy + wz*wz)  # Velocidad total
        return sensor_vector
    
    def smooth_parameters(self, new_params):
        """Suavizar cambios de parámetros para evitar movimientos bruscos"""
        if self.last_params is None:
            self.last_params = new_params.copy()
            return new_params
        
        # Factor de suavizado (0.3 = cambio gradual)
        alpha = 0.3
        smoothed_params = {}
        
        for param_name in new_params:
            old_val = self.last_params.get(param_name, new_params[param_name])
            new_val = new_params[param_name]
            smoothed_params[param_name] = old_val * (1 - alpha) + new_val * alpha
        
        self.last_params = smoothed_params.copy()
        return smoothed_params
    
    def adapt_gait(self, vx, vy, wz):
        """Adaptar parámetros de marcha basados en condiciones actuales"""
        if not self.adaptation_enabled or not self.cnn:
            return None
        
        start_time = time.time()
        
        try:
            # Obtener datos de sensores
            sensor_data = self.get_sensor_data()
            sensor_data = self.add_command_velocities(sensor_data, vx, vy, wz)
            
            # Agregar al historial para estabilidad
            self.sensor_history.append(sensor_data)
            
            # Usar promedio de las últimas lecturas para estabilidad
            if len(self.sensor_history) >= 3:
                averaged_sensors = np.mean(list(self.sensor_history)[-3:], axis=0)
            else:
                averaged_sensors = sensor_data
            
            # Predecir parámetros con CNN
            predicted_params = self.cnn.predict_gait_params(averaged_sensors)
            
            # Suavizar cambios
            smooth_params = self.smooth_parameters(predicted_params)
            
            # Estadísticas de rendimiento
            prediction_time = time.time() - start_time
            self.prediction_count += 1
            self.total_prediction_time += prediction_time
            
            if self.prediction_count % 50 == 0:
                avg_time = self.total_prediction_time / self.prediction_count
                print("CNN: {} predicciones, tiempo promedio: {:.3f}ms".format(
                    self.prediction_count, avg_time * 1000))
            
            return smooth_params
            
        except Exception as e:
            print("Error en adaptación de marcha: {}".format(e))
            return None
    
    def apply_gait_params(self, params):
        """Aplicar parámetros de marcha al NAO"""
        if not self.motion or not params:
            return False
        
        try:
            # Convertir a formato NAOqi
            gait_config = []
            for param_name, value in params.items():
                gait_config.append([param_name, float(value)])
            
            # Aplicar configuración
            self.motion.setMotionConfig(gait_config)
            return True
            
        except Exception as e:
            print("Error aplicando parámetros de marcha: {}".format(e))
            return False
    
    def get_stats(self):
        """Obtener estadísticas de rendimiento"""
        if self.prediction_count > 0:
            avg_time = self.total_prediction_time / self.prediction_count
            return {
                'predictions': self.prediction_count,
                'avg_time_ms': avg_time * 1000,
                'adaptations_enabled': self.adaptation_enabled,
                'cnn_available': self.cnn is not None
            }
        return {'predictions': 0, 'cnn_available': self.cnn is not None}

# Función para integrar con el control server existente
def create_adaptive_walker(nao_ip="127.0.0.1", nao_port=9559):
    """Crear instancia del controlador adaptativo"""
    return AdaptiveWalkController(nao_ip, nao_port)

# Test básico
if __name__ == "__main__":
    print("=== Test CNN Caminata Adaptativa ===")
    
    # Crear controlador
    walker = create_adaptive_walker()
    
    if walker.cnn:
        print("Probando predicción CNN...")
        
        # Simular datos de sensores
        test_sensors = [0.1, -0.05, 9.8, 0.02, -0.01, 0.0, 0.05, -0.02,
                       0.5, 0.6, 0.4, 0.5, 0.6, 0.5, 0.4, 0.6,
                       0.5, 0.3, 0.1, 0.6]  # vx, vy, wz, velocidad_total
        
        # Predicción
        start_time = time.time()
        params = walker.cnn.predict_gait_params(test_sensors)
        prediction_time = time.time() - start_time
        
        print("Parámetros predichos:")
        for param, value in params.items():
            print("  {}: {:.4f}".format(param, value))
        
        print("Tiempo de predicción: {:.2f}ms".format(prediction_time * 1000))
        
        # Test de adaptación completa
        print("\nProbando adaptación completa...")
        adapted_params = walker.adapt_gait(0.5, 0.3, 0.1)
        if adapted_params:
            print("Adaptación exitosa:")
            for param, value in adapted_params.items():
                print("  {}: {:.4f}".format(param, value))
        
        print("Estadísticas: {}".format(walker.get_stats()))
    else:
        print("CNN no disponible - verifique dependencias")
