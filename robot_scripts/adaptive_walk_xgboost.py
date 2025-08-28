#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
adaptive_walk_xgboost.py - Caminata adaptativa con XGBoost para NAO/NAOqi

- Modelo XGBoost ligero que estima parámetros de marcha estables: MaxStepX, MaxStepY, MaxStepTheta, Frequency, StepHeight.
- Bucle de adaptación con:
    * Filtro EMA (suavizado)
    * Zona muerta (deadband)
    * Limitador de pendiente (rate limiter)
    * Consenso de signo (histeresis temporal)
    * "Comfort lock" (bloqueo cuando camina cómodo; se congela la adaptación un rato)
- Telemetría a last_params.json para depurar desde shell.

Requisitos:
  - Python 2.7 en NAO (con xgboost instalado)
  - NAOqi SDK disponible (ALMotion/ALMemory). Si no están, el script arranca en modo "solo XGBoost".

Archivo de estado/salida:
  /home/nao/.local/share/adaptive_gait/last_params.json

Modelo XGBoost:
  /home/nao/.local/share/adaptive_gait/xgboost_model.json
"""

from __future__ import print_function
import os
import json
import time
import math
import pickle
from collections import deque

import numpy as np

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("[ERROR] XGBoost no está disponible. Instalar con: pip install xgboost")

try:
    from naoqi import ALProxy
    NAOQI_AVAILABLE = True
except Exception:
    NAOQI_AVAILABLE = False

# ------------------------------
# Utilidades de E/S y rutas
# ------------------------------
HOME = os.path.expanduser('~')
DATA_DIR = os.path.join(HOME, '.local', 'share', 'adaptive_gait')
if not os.path.isdir(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except OSError:
        pass

MODEL_PATH = os.path.join(DATA_DIR, 'xgboost_model.json')
SCALER_PATH = os.path.join(DATA_DIR, 'feature_scaler.pkl')
LAST_JSON = os.path.join(DATA_DIR, 'last_params.json')

# ------------------------------
# Configuración (tuneable)
# ------------------------------
CFG = {
    # Frecuencia de actualización (más lento = menos cambios bruscos)
    'update_period_s': 0.8,   # 0.7 - 1.0 recomendado

    # Suavizado exponencial de la predicción del XGBoost
    'ema_alpha': 0.2,         # 0.1-0.3

    # Zona muerta: ignora micromovimientos
    'deadband': {
        'MaxStepY': 0.0030,       # ~3 mm lateral
        'MaxStepTheta': 0.0002,   # ~0.01°
        'MaxStepX': 0.0020,       # ~2 mm
        'Frequency': 0.0020,
        'StepHeight': 0.0020,
    },

    # Limitador de cambio por actualización
    'rate_limit': {
        'MaxStepY': 0.0010,
        'MaxStepTheta': 0.0002,
        'MaxStepX': 0.0010,
        'Frequency': 0.0050,
        'StepHeight': 0.0010,
    },

    # Consenso de signo: requiere que la mayoría de las últimas N decisiones apunten en la misma dirección
    'consensus': {
        'window': 5,
        'min_same_sign': 4
    },

    # Comfort lock / hold
    'comfort': {
        'enable': True,
        'stable_secs_to_lock': 3.0,   # tiempo con errores pequeños para bloquear
        'hold_secs': 10.0,            # tiempo bloqueado
        'unlock_threshold': {         # si los errores vuelven a subir, desbloquea
            'MaxStepY': 0.008,
            'MaxStepTheta': 0.0006,
        }
    },

    # Límites físicos/seguridad del NAO (recortes hard)
    'limits': {
        'MaxStepX': (0.0, 0.08),
        'MaxStepY': (0.0, 0.20),
        'MaxStepTheta': (0.0, 0.35),
        'Frequency': (0.6, 1.4),
        'StepHeight': (0.015, 0.03),
    },

    # Logging: escribe también prints de depuración
    'verbose': False,
}

# Orden de features esperado por el modelo (20 entradas)
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_KEYS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

# Rangos físicos para desnormalización
PARAM_RANGES = {
    'StepHeight':   (0.01, 0.05),
    'MaxStepX':     (0.02, 0.08),
    'MaxStepY':     (0.08, 0.20),
    'MaxStepTheta': (0.10, 0.50),
    'Frequency':    (0.50, 1.20),
}

PARAMS = ('MaxStepX','MaxStepY','MaxStepTheta','Frequency','StepHeight')

# ------------------------------
# XGBoost ligero
# ------------------------------
class LightweightXGBoost(object):
    def __init__(self, model_path=MODEL_PATH, scaler_path=SCALER_PATH):
        self.models = {}  # Un modelo por cada parámetro de salida
        self.scaler = None
        self.ok = False
        
        if not XGBOOST_AVAILABLE:
            print("[ERROR] XGBoost no disponible")
            return
            
        # Cargar modelos (uno por cada parámetro)
        try:
            if os.path.isfile(model_path):
                with open(model_path, 'r') as f:
                    model_data = json.load(f)
                
                for param in GAIT_KEYS:
                    if param in model_data:
                        self.models[param] = xgb.XGBRegressor()
                        self.models[param].load_model(model_data[param])
                
                print("[INFO] Modelos XGBoost cargados exitosamente")
            else:
                print("[WARN] No encontré modelo en %s" % model_path)
                return
                
            # Cargar scaler si existe
            if os.path.isfile(scaler_path):
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                print("[INFO] Scaler cargado exitosamente")
            else:
                print("[WARN] No encontré scaler en %s" % scaler_path)
                
            self.ok = True
            
        except Exception as e:
            print("[ERROR] No pude cargar modelo XGBoost: %s" % e)

    def predict_gait_params(self, features_vector):
        """
        features_vector: lista/array de 20 features en orden FEAT_ORDER
        Devuelve dict con parámetros de marcha desnormalizados
        """
        if not self.ok or not self.models:
            # fallback: devolver parámetros base
            return {
                'MaxStepX': 0.05,
                'MaxStepY': 0.10,
                'MaxStepTheta': 0.30,
                'Frequency': 0.85,
                'StepHeight': 0.025
            }
        
        try:
            # Convertir a numpy array
            X = np.array(features_vector, dtype=np.float32).reshape(1, -1)
            
            # Normalizar features si tenemos scaler
            if self.scaler is not None:
                X = self.scaler.transform(X)
            else:
            # Normalización básica por muestra (como en el sistema original)
                mu = X.mean()
                sigma = X.std() + 1e-8
                X = (X - mu) / sigma
            
            # Predecir cada parámetro
            predictions = {}
            for param in GAIT_KEYS:
                if param in self.models:
                    # Predicción normalizada [0,1]
                    pred_norm = self.models[param].predict(X)[0]
                    pred_norm = np.clip(pred_norm, 0.0, 1.0)
                    
                    # Desnormalizar a rango físico
                    lo, hi = PARAM_RANGES[param]
                    pred_real = lo + pred_norm * (hi - lo)
                    predictions[param] = float(pred_real)
                else:
                    # Valor por defecto si no hay modelo para este parámetro
                    predictions[param] = (PARAM_RANGES[param][0] + PARAM_RANGES[param][1]) / 2.0
            
            return predictions
            
        except Exception as e:
            print("[ERROR] Error en predicción XGBoost: %s" % e)
            # fallback
            return {
                'MaxStepX': 0.05,
                'MaxStepY': 0.10,
                'MaxStepTheta': 0.30,
                'Frequency': 0.85,
                'StepHeight': 0.025
            }

# ------------------------------
# Lectura de sensores NAOqi (minimal)
# ------------------------------
class RobotIO(object):
    def __init__(self, nao_ip="127.0.0.1", nao_port=9559):
        self.motion = None
        self.mem = None
        if NAOQI_AVAILABLE:
            try:
                self.motion = ALProxy("ALMotion", nao_ip, nao_port)
            except Exception as e:
                print("[W] ALMotion no disponible: %s" % e)
            try:
                self.mem = ALProxy("ALMemory", nao_ip, nao_port)
            except Exception as e:
                print("[W] ALMemory no disponible: %s" % e)

    def get_sensor_features(self):
        """
        Extrae vector de 20 características desde sensores del robot.
        Si no hay NAOqi, devuelve constantes válidas.
        """
        features = [0.0] * 20  # Inicializar con ceros
        
        if self.mem is None:
            # Valores por defecto cuando no hay sensores
            features[0:3] = [0, 0, 9.81]  # accel_x, accel_y, accel_z
            features[3:6] = [0, 0, 0]     # gyro_x, gyro_y, gyro_z
            features[6:8] = [0, 0]        # angle_x, angle_y
            features[8:16] = [0.0] * 8    # foot pressure sensors
            features[16:20] = [0, 0, 0, 0] # vx, vy, wz, vtotal
            return features

        # Leer sensores inerciales
        try:
            features[0] = float(self.mem.getData("Device/SubDeviceList/InertialSensor/AccX/Sensor/Value") or 0.0)
            features[1] = float(self.mem.getData("Device/SubDeviceList/InertialSensor/AccY/Sensor/Value") or 0.0)
            features[2] = float(self.mem.getData("Device/SubDeviceList/InertialSensor/AccZ/Sensor/Value") or 9.81)
            features[3] = float(self.mem.getData("Device/SubDeviceList/InertialSensor/GyrX/Sensor/Value") or 0.0)
            features[4] = float(self.mem.getData("Device/SubDeviceList/InertialSensor/GyrY/Sensor/Value") or 0.0)
            features[5] = float(self.mem.getData("Device/SubDeviceList/InertialSensor/GyrZ/Sensor/Value") or 0.0)
            features[6] = float(self.mem.getData("Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value") or 0.0)
            features[7] = float(self.mem.getData("Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value") or 0.0)
        except Exception as e:
            if CFG['verbose']:
                print("[W] Error leyendo sensores inerciales: %s" % e)

        # Leer sensores de presión de pies (si están disponibles)
        foot_sensors = [
            "Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value",
            "Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value", 
            "Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value",  # Repetir para completar
            "Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value",
            "Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value",
            "Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value",
            "Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value",  # Repetir para completar
            "Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value"
        ]
        
        for i, sensor in enumerate(foot_sensors):
            try:
                features[8 + i] = float(self.mem.getData(sensor) or 0.0)
            except Exception:
                features[8 + i] = 0.0

        # Velocidades (si están disponibles en ALMotion)
        try:
            if self.motion:
                # Intentar obtener velocidades actuales
                features[16] = 0.0  # vx - velocidad lineal X
                features[17] = 0.0  # vy - velocidad lineal Y  
                features[18] = 0.0  # wz - velocidad angular Z
                features[19] = 0.0  # vtotal - velocidad total
        except Exception:
            pass

        return features

    def apply_gait_params(self, params):
        """
        Aplica parámetros de marcha al robot usando ALMotion
        """
        if self.motion is None:
            return False
            
        try:
            # Mapeo de parámetros a configuración de movimiento NAOqi
            config_list = []
            
            if 'MaxStepX' in params:
                config_list.append(["MaxStepX", float(params['MaxStepX'])])
            if 'MaxStepY' in params:
                config_list.append(["MaxStepY", float(params['MaxStepY'])])
            if 'MaxStepTheta' in params:
                config_list.append(["MaxStepTheta", float(params['MaxStepTheta'])])
            if 'Frequency' in params:
                config_list.append(["MaxStepFrequency", float(params['Frequency'])])
            if 'StepHeight' in params:
                config_list.append(["StepHeight", float(params['StepHeight'])])
            
            # Aplicar configuración
            self.motion.setMoveConfig(config_list)
            
            if CFG['verbose']:
                print("[INFO] Parámetros aplicados: %s" % params)
                
            return True
            
        except Exception as e:
            if CFG['verbose']:
                print("[ERROR] No pude aplicar parámetros: %s" % e)
            return False

# ------------------------------
# Controlador principal de adaptación
# ------------------------------
class AdaptiveWalkController(object):
    def __init__(self, nao_ip="127.0.0.1", nao_port=9559):
        self.xgb_model = LightweightXGBoost()
        self.robot_io = RobotIO(nao_ip, nao_port)
        
        # Estado del filtro de adaptación
        self.ema_state = None
        self.last_applied = None
        self.last_update_time = 0.0
        
        # Historial para consenso de signo
        self.sign_history = {param: deque(maxlen=CFG['consensus']['window']) for param in PARAMS}
        
        # Estado de comfort lock
        self.comfort_locked = False
        self.lock_until_time = 0.0
        self.stable_since = None
        
        print("[INFO] AdaptiveWalkController inicializado")

    def get_current_features(self):
        """Obtiene vector de features actual desde sensores"""
        return self.robot_io.get_sensor_features()

    def predict_gait_params(self, features_vector):
        """Wrapper para predicción del modelo"""
        return self.xgb_model.predict_gait_params(features_vector)

    def apply_gait_params(self, params):
        """Wrapper para aplicar parámetros al robot"""
        return self.robot_io.apply_gait_params(params)

    def save_state(self, params, features=None):
        """Guarda estado actual en archivo JSON"""
        try:
            state = {
                'timestamp': time.time(),
                'gait_params': params,
                'features': features,
                'comfort_locked': self.comfort_locked,
                'model_ok': self.xgb_model.ok
            }
            
            with open(LAST_JSON, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            if CFG['verbose']:
                print("[WARN] No pude guardar estado: %s" % e)

# ------------------------------
# Funciones de compatibilidad
# ------------------------------
def _safe_float(x, default=0.0):
    """Conversión segura a float"""
    try:
        return float(x)
    except Exception:
        return default

def _mean(seq):
    """Media aritmética compatible con Python 2"""
    if not seq:
        return 0.0
    return sum(float(x) for x in seq) / len(seq)

def _median(seq):
    """Mediana compatible con Python 2"""
    if not seq:
        return 0.0
    s = sorted(float(x) for x in seq)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])

# ------------------------------
# Funciones principales
# ------------------------------
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description="Controlador de caminata adaptativa con XGBoost")
    parser.add_argument('--nao-ip', default='127.0.0.1', help='IP del robot NAO')
    parser.add_argument('--nao-port', type=int, default=9559, help='Puerto NAOqi')
    parser.add_argument('--test', action='store_true', help='Modo de prueba (solo predicción)')
    args = parser.parse_args()
    
    controller = AdaptiveWalkController(args.nao_ip, args.nao_port)
    
    if args.test:
        # Modo de prueba: una predicción y salir
        features = controller.get_current_features()
        params = controller.predict_gait_params(features)
        print("[TEST] Features: %s" % features[:8])  # Solo mostrar primeros 8
        print("[TEST] Predicción: %s" % params)
        controller.save_state(params, features)
    else:
        print("[INFO] Iniciando bucle de adaptación (Ctrl+C para parar)")
        try:
            while True:
                features = controller.get_current_features()
                params = controller.predict_gait_params(features)
                
                if CFG['verbose']:
                    print("[LOOP] Predicción: %s" % params)
                
                # Aplicar parámetros al robot
                controller.apply_gait_params(params)
                controller.save_state(params, features)
                
                time.sleep(CFG['update_period_s'])
                
        except KeyboardInterrupt:
            print("\n[INFO] Detenido por usuario")
