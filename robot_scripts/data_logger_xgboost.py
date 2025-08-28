#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
data_logger_xgboost.py - Logger de datos para entrenamiento de modelos XGBoost

Recolecta datos de sensores y parámetros de marcha para entrenar los modelos XGBoost.
Guarda datos en formato CSV compatible con train_xgboost_gait.py

Requisitos:
  - Python 2.7 en NAO
  - NAOqi SDK disponible (ALMotion/ALMemory)

Uso:
  python2 data_logger_xgboost.py --output /home/nao/datasets/walk_session.csv --duration 300
"""

from __future__ import print_function
import os
import sys
import csv
import time
import argparse
from datetime import datetime

try:
    from naoqi import ALProxy
    NAOQI_AVAILABLE = True
except ImportError:
    NAOQI_AVAILABLE = False
    print("[WARN] NAOqi no disponible - modo simulación")

# Orden de features para XGBoost (debe coincidir con train_xgboost_gait.py)
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_PARAMS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

class SensorReader:
    """Lector de sensores del robot NAO"""
    
    def __init__(self, nao_ip="127.0.0.1", nao_port=9559):
        self.motion = None
        self.memory = None
        
        if NAOQI_AVAILABLE:
            try:
                self.motion = ALProxy("ALMotion", nao_ip, nao_port)
                self.memory = ALProxy("ALMemory", nao_ip, nao_port)
                print("[INFO] Conectado a NAOqi en %s:%d" % (nao_ip, nao_port))
            except Exception as e:
                print("[ERROR] No se pudo conectar a NAOqi: %s" % e)
                self.motion = None
                self.memory = None
        
        self.last_gait_params = self._get_default_gait_params()
        
    def _get_default_gait_params(self):
        """Parámetros de marcha por defecto"""
        return {
            'StepHeight': 0.025,
            'MaxStepX': 0.04,
            'MaxStepY': 0.14,
            'MaxStepTheta': 0.35,
            'Frequency': 1.0
        }
    
    def _safe_get_sensor(self, key, default=0.0):
        """Lectura segura de sensor con valor por defecto"""
        if self.memory is None:
            return default
        try:
            value = self.memory.getData(key)
            return float(value) if value is not None else default
        except Exception:
            return default
    
    def get_inertial_data(self):
        """Lee datos de sensores inerciales"""
        data = {}
        
        # Acelerómetros
        data['accel_x'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AccX/Sensor/Value", 0.0)
        data['accel_y'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AccY/Sensor/Value", 0.0)
        data['accel_z'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AccZ/Sensor/Value", 9.81)
        
        # Giroscopios
        data['gyro_x'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/GyrX/Sensor/Value", 0.0)
        data['gyro_y'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/GyrY/Sensor/Value", 0.0)
        data['gyro_z'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/GyrZ/Sensor/Value", 0.0)
        
        # Ángulos
        data['angle_x'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value", 0.0)
        data['angle_y'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value", 0.0)
        
        return data
    
    def get_foot_pressure_data(self):
        """Lee datos de sensores de presión de pies"""
        data = {}
        
        # Pie izquierdo
        data['lfoot_fl'] = self._safe_get_sensor("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value", 0.0)
        data['lfoot_fr'] = self._safe_get_sensor("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value", 0.0)
        data['lfoot_rl'] = self._safe_get_sensor("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value", 0.0)  # Repetir por compatibilidad
        data['lfoot_rr'] = self._safe_get_sensor("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value", 0.0)
        
        # Pie derecho
        data['rfoot_fl'] = self._safe_get_sensor("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value", 0.0)
        data['rfoot_fr'] = self._safe_get_sensor("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value", 0.0)
        data['rfoot_rl'] = self._safe_get_sensor("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value", 0.0)   # Repetir por compatibilidad
        data['rfoot_rr'] = self._safe_get_sensor("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value", 0.0)
        
        return data
    
    def get_velocity_data(self):
        """Estima datos de velocidad (simplificado)"""
        # En un sistema real, esto vendría de odometría o estimación de movimiento
        return {
            'vx': 0.0,      # Velocidad lineal X
            'vy': 0.0,      # Velocidad lineal Y  
            'wz': 0.0,      # Velocidad angular Z
            'vtotal': 0.0   # Velocidad total
        }
    
    def get_current_gait_params(self):
        """Obtiene parámetros de marcha actuales"""
        if self.motion is None:
            return self.last_gait_params.copy()
        
        try:
            # Intentar leer configuración actual de ALMotion
            # Nota: Esto puede variar según la versión de NAOqi
            current_params = self.last_gait_params.copy()
            
            # Aquí podrías leer los parámetros reales si NAOqi los expone
            # Por ahora devolvemos los últimos conocidos
            return current_params
            
        except Exception as e:
            print("[WARN] No se pudieron leer parámetros de marcha: %s" % e)
            return self.last_gait_params.copy()
    
    def set_gait_params(self, params):
        """Establece nuevos parámetros de marcha"""
        if self.motion is None:
            print("[WARN] No hay conexión ALMotion - guardando parámetros localmente")
            self.last_gait_params.update(params)
            return False
        
        try:
            # Convertir a formato NAOqi
            config_list = []
            
            if 'StepHeight' in params:
                config_list.append(["StepHeight", float(params['StepHeight'])])
            if 'MaxStepX' in params:
                config_list.append(["MaxStepX", float(params['MaxStepX'])])
            if 'MaxStepY' in params:
                config_list.append(["MaxStepY", float(params['MaxStepY'])])
            if 'MaxStepTheta' in params:
                config_list.append(["MaxStepTheta", float(params['MaxStepTheta'])])
            if 'Frequency' in params:
                config_list.append(["MaxStepFrequency", float(params['Frequency'])])
            
            self.motion.setMoveConfig(config_list)
            self.last_gait_params.update(params)
            return True
            
        except Exception as e:
            print("[ERROR] No se pudieron aplicar parámetros de marcha: %s" % e)
            return False
    
    def get_complete_sample(self):
        """Obtiene una muestra completa con todos los datos"""
        sample = {}
        
        # Agregar sensores inerciales
        sample.update(self.get_inertial_data())
        
        # Agregar sensores de presión
        sample.update(self.get_foot_pressure_data())
        
        # Agregar velocidades
        sample.update(self.get_velocity_data())
        
        # Agregar parámetros de marcha actuales
        sample.update(self.get_current_gait_params())
        
        # Agregar timestamp
        sample['timestamp'] = time.time()
        
        return sample

class DataLogger:
    """Logger de datos para entrenamiento XGBoost"""
    
    def __init__(self, output_file, sensor_reader):
        self.output_file = output_file
        self.sensor_reader = sensor_reader
        self.csv_writer = None
        self.csv_file = None
        self.samples_written = 0
        
        # Crear directorio si no existe
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def start_logging(self):
        """Inicia el logging a archivo CSV"""
        try:
            self.csv_file = open(self.output_file, 'wb')
            
            # Crear header: features + gait params + timestamp
            fieldnames = FEAT_ORDER + GAIT_PARAMS + ['timestamp']
            
            self.csv_writer = csv.DictWriter(
                self.csv_file, 
                fieldnames=fieldnames,
                extrasaction='ignore'  # Ignorar campos extra
            )
            
            self.csv_writer.writeheader()
            print("[INFO] Logging iniciado: %s" % self.output_file)
            return True
            
        except Exception as e:
            print("[ERROR] No se pudo iniciar logging: %s" % e)
            return False
    
    def log_sample(self):
        """Registra una muestra de datos"""
        if self.csv_writer is None:
            return False
        
        try:
            sample = self.sensor_reader.get_complete_sample()
            self.csv_writer.writerow(sample)
            self.csv_file.flush()  # Asegurar escritura inmediata
            self.samples_written += 1
            return True
            
        except Exception as e:
            print("[ERROR] Error escribiendo muestra: %s" % e)
            return False
    
    def stop_logging(self):
        """Detiene el logging"""
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
        
        print("[INFO] Logging detenido. Muestras escritas: %d" % self.samples_written)

def main():
    parser = argparse.ArgumentParser(description="Logger de datos para entrenamiento XGBoost")
    parser.add_argument('--output', required=True, help='Archivo CSV de salida')
    parser.add_argument('--duration', type=float, default=60.0, help='Duración en segundos (0=infinito)')
    parser.add_argument('--frequency', type=float, default=10.0, help='Frecuencia de muestreo (Hz)')
    parser.add_argument('--nao-ip', default='127.0.0.1', help='IP del robot NAO')
    parser.add_argument('--nao-port', type=int, default=9559, help='Puerto NAOqi')
    parser.add_argument('--verbose', action='store_true', help='Output detallado')
    
    args = parser.parse_args()
    
    # Validar parámetros
    if args.frequency <= 0:
        print("[ERROR] Frecuencia debe ser > 0")
        sys.exit(1)
    
    sample_period = 1.0 / args.frequency
    
    print("=== Data Logger XGBoost ===")
    print("Archivo de salida: %s" % args.output)
    print("Duración: %s segundos" % ("infinita" if args.duration <= 0 else str(args.duration)))
    print("Frecuencia: %.1f Hz (periodo: %.3f s)" % (args.frequency, sample_period))
    print("Robot: %s:%d" % (args.nao_ip, args.nao_port))
    
    # Inicializar componentes
    sensor_reader = SensorReader(args.nao_ip, args.nao_port)
    data_logger = DataLogger(args.output, sensor_reader)
    
    if not data_logger.start_logging():
        print("[ERROR] No se pudo iniciar el logging")
        sys.exit(1)
    
    # Loop principal de muestreo
    start_time = time.time()
    last_sample_time = 0
    
    try:
        print("\\n[INFO] Iniciando recolección de datos... (Ctrl+C para parar)")
        
        while True:
            current_time = time.time()
            
            # Verificar si es hora de tomar una muestra
            if current_time - last_sample_time >= sample_period:
                if data_logger.log_sample():
                    last_sample_time = current_time
                    
                    if args.verbose:
                        elapsed = current_time - start_time
                        print("  Muestra %d (t=%.1fs)" % (data_logger.samples_written, elapsed))
                else:
                    print("[WARN] Error en muestra %d" % (data_logger.samples_written + 1))
            
            # Verificar duración
            if args.duration > 0 and (current_time - start_time) >= args.duration:
                print("\\n[INFO] Duración completada")
                break
            
            # Pequeña pausa para no saturar CPU
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\\n[INFO] Detenido por usuario")
    
    except Exception as e:
        print("\\n[ERROR] Error inesperado: %s" % e)
    
    finally:
        data_logger.stop_logging()
        
        # Estadísticas finales
        elapsed_total = time.time() - start_time
        if elapsed_total > 0:
            actual_frequency = data_logger.samples_written / elapsed_total
            print("\\nEstadísticas:")
            print("  Tiempo total: %.1f segundos" % elapsed_total)
            print("  Muestras: %d" % data_logger.samples_written)
            print("  Frecuencia real: %.2f Hz" % actual_frequency)
            print("  Archivo: %s" % args.output)

if __name__ == '__main__':
    main()
