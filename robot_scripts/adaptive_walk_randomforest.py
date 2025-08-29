#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
adaptive_walk_randomforest.py — Sistema de marcha adaptativa con Random Forest

Sistema que usa modelos Random Forest pre-entrenados para ajustar parámetros
de marcha en tiempo real basándose en telemetría del robot (sensores + estado).

Este script reemplaza adaptive_walk_xgboost.py, manteniendo la misma interfaz
y funcionalidad pero usando Random Forest en lugar de XGBoost.

Requisitos:
- Modelos Random Forest pre-entrenados en directorio models/
- scikit-learn, numpy, pandas compatibles con Python 2.7
- NAOqi SDK y acceso a proxies ALMotion, ALMemory, etc.

Archivos necesarios:
- models/randomforest_model_<param>.pkl (5 modelos)
- models/feature_scaler.pkl

Uso:
  python adaptive_walk_randomforest.py --enable --log-level debug
"""

import argparse
import os
import sys
import time
import json
import logging
import csv
from datetime import datetime
from threading import Thread, Event
import numpy as np
# Compat shim: use raw_input on Python2, input on Python3
try:
    import builtins as _builtins
except ImportError:
    # Python2
    _builtins = __builtins__

safe_input = getattr(_builtins, 'raw_input', None) or getattr(_builtins, 'input')

# Importes NAOqi
try:
    import qi
    import alproxy
    from naoqi import ALProxy
except ImportError:
    print("[ERROR] NAOqi SDK no disponible - simulando...")
    qi = None
    ALProxy = None

# Importes ML
# Intentamos usar joblib/sklearn si están presentes; si no, caemos a un loader NPZ puro (sin dependencia C)
JOBLIB_AVAILABLE = False
SKLEARN_AVAILABLE = False
try:
    import joblib
    JOBLIB_AVAILABLE = True
except Exception:
    joblib = None

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except Exception:
    RandomForestRegressor = None
    StandardScaler = None

# ========================== CONFIGURACIÓN ===========================

# Features en orden exacto (debe coincidir con entrenamiento)
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

# Valores por defecto (centro del rango)
DEFAULT_GAIT = {
    'StepHeight':   0.030,
    'MaxStepX':     0.050,
    'MaxStepY':     0.140,
    'MaxStepTheta': 0.300,
    'Frequency':    0.850,
}

class AdaptiveWalkRandomForest:
    """
    Sistema de marcha adaptativa usando Random Forest.
    
    Recolecta telemetría del robot, la procesa con modelos Random Forest
    pre-entrenados y ajusta parámetros de marcha en tiempo real.
    """
    
    def __init__(self, robot_ip="localhost", robot_port=9559, models_dir="models", log_dir="logs"):
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.models_dir = models_dir
        self.log_dir = log_dir
        
        # Estado
        self.enabled = False
        self.running = False
        self.stop_event = Event()
        
        # Proxies NAOqi
        self.motion = None
        self.memory = None
        self.sensors = None
        
        # Modelos ML
        self.models = {}
        self.scaler = None
        
        # Filtros y estado
        self.feature_history = []
        self.ema_features = np.zeros(20)
        self.ema_alpha = 0.3
        self.last_update_time = 0
        
        # Configuración
        self.update_interval = 0.5  # 2 Hz
        self.history_size = 10
        
        # Logging
        self.logger = logging.getLogger("AdaptiveWalk")
        
        # CSV Data Logging
        self.csv_enabled = True
        self.csv_file = None
        self.csv_writer = None
        self.setup_csv_logging()
        
    def setup_csv_logging(self):
        """Configurar logging de datos en CSV para reentrenamiento (compatible Python 2/3)"""
        if not self.csv_enabled:
            return
            
        try:
            # Crear directorio de logs si no existe
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir)
            
            # Nombre de archivo con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = "adaptive_data_{}.csv".format(timestamp)
            csv_path = os.path.join(self.log_dir, csv_filename)
            
            # Abrir archivo CSV compatible Python 2/3
            if sys.version_info[0] >= 3:
                # Python 3
                self.csv_file = open(csv_path, 'w', newline='', encoding='utf-8')
            else:
                # Python 2 - no soporta 'newline' parameter
                self.csv_file = open(csv_path, 'wb')
            
            # Headers: timestamp, features (20), predictions (5), applied_params (5), success
            headers = ['timestamp', 'datetime']
            
            # Feature headers
            headers.extend(['feat_{}'.format(name) for name in FEAT_ORDER])
            
            # Prediction headers (normalized 0-1)
            headers.extend(['pred_norm_{}'.format(param) for param in GAIT_KEYS])
            
            # Applied parameter headers (real values)
            headers.extend(['applied_{}'.format(param) for param in GAIT_KEYS])
            
            # Success flag and inference time
            headers.extend(['success', 'inference_time_ms'])
            
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=headers)
            self.csv_writer.writeheader()
            self.csv_file.flush()
            
            self.logger.info("CSV logging iniciado: {}".format(csv_path))
            
        except Exception as e:
            self.logger.warning("No se pudo iniciar CSV logging: {}".format(e))
            self.csv_enabled = False
    
    def log_adaptation_data(self, features, predictions_norm, applied_params, success, inference_time):
        """Registrar datos de adaptación en CSV (compatible Python 2/3)"""
        if not self.csv_enabled or self.csv_writer is None:
            return
            
        try:
            now = time.time()
            dt = datetime.fromtimestamp(now)
            
            # Preparar row data
            row = {
                'timestamp': now,
                'datetime': dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'success': success,
                'inference_time_ms': inference_time * 1000.0
            }
            
            # Features
            for i, feat_name in enumerate(FEAT_ORDER):
                row['feat_{}'.format(feat_name)] = float(features[i]) if i < len(features) else 0.0
            
            # Predictions (normalized)
            for param in GAIT_KEYS:
                row['pred_norm_{}'.format(param)] = float(predictions_norm.get(param, 0.0))
            
            # Applied parameters (real values)
            for param in GAIT_KEYS:
                row['applied_{}'.format(param)] = float(applied_params.get(param, 0.0))
            
            # Escribir row compatible Python 2/3
            if sys.version_info[0] >= 3:
                # Python 3 - escribir directamente
                self.csv_writer.writerow(row)
            else:
                # Python 2 - convertir valores unicode a str/bytes
                safe_row = {}
                for k, v in row.items():
                    # Check for unicode type in Python 2
                    try:
                        if isinstance(v, unicode):  # Python 2 unicode type
                            safe_row[str(k)] = v.encode('utf-8')
                        elif isinstance(v, str):
                            safe_row[str(k)] = v
                        else:
                            safe_row[str(k)] = str(v)
                    except NameError:
                        # unicode not defined (shouldn't happen in Py2 but just in case)
                        safe_row[str(k)] = str(v)
                self.csv_writer.writerow(safe_row)
                
            self.csv_file.flush()
            
        except Exception as e:
            self.logger.warning("Error escribiendo CSV: {}".format(e))
            
        except Exception as e:
            self.logger.warning("Error escribiendo CSV: {}".format(e))
    
    def close_csv_logging(self):
        """Cerrar archivo CSV de logging"""
        if self.csv_file:
            try:
                self.csv_file.close()
                self.logger.info("CSV logging cerrado")
            except:
                pass
            self.csv_file = None
            self.csv_writer = None
        
    def connect_robot(self):
        """Conectar a proxies NAOqi"""
        if ALProxy is None:
            self.logger.warning("NAOqi no disponible - modo simulación")
            return True
            
        try:
            self.motion = ALProxy("ALMotion", self.robot_ip, self.robot_port)
            self.memory = ALProxy("ALMemory", self.robot_ip, self.robot_port)
            self.sensors = ALProxy("ALSensors", self.robot_ip, self.robot_port)
            
            self.logger.info("Conectado a robot en {}:{}".format(self.robot_ip, self.robot_port))
            return True
            
        except Exception as e:
            self.logger.error("Error conectando a robot: {}".format(e))
            return False
    
    def load_models(self):
        """Cargar modelos Random Forest y scaler"""
        self.logger.info("Cargando modelos desde: {}".format(self.models_dir))
        
        # Primero intentar formato joblib/pkl (si está disponible y los archivos existen)
        scaler_pkl = os.path.join(self.models_dir, "feature_scaler.pkl")
        scaler_npz = os.path.join(self.models_dir, "feature_scaler.npz")

        if JOBLIB_AVAILABLE and os.path.exists(scaler_pkl):
            try:
                self.scaler = joblib.load(scaler_pkl)
                self.logger.info("Scaler (pkl) cargado: {}".format(scaler_pkl))
            except Exception as e:
                raise RuntimeError("Error cargando scaler pkl: {}".format(e))
        elif os.path.exists(scaler_npz):
            try:
                arr = np.load(scaler_npz, allow_pickle=False)
                # esperamos keys 'mean' y 'scale'
                self.scaler = {'mean': arr['mean'], 'scale': arr['scale']}
                self.logger.info("Scaler (npz) cargado: {}".format(scaler_npz))
            except Exception as e:
                raise RuntimeError("Error cargando scaler npz: {}".format(e))
        else:
            raise RuntimeError("Scaler no encontrado (esperado feature_scaler.pkl o feature_scaler.npz)")

        # Cargar modelos: preferimos pkl si joblib está presente, si no buscamos archivo NPZ por modelo
        for param in GAIT_KEYS:
            pkl_path = os.path.join(self.models_dir, "randomforest_model_{}.pkl".format(param))
            npz_path = os.path.join(self.models_dir, "randomforest_model_{}.npz".format(param))

            if JOBLIB_AVAILABLE and os.path.exists(pkl_path):
                try:
                    model = joblib.load(pkl_path)
                    self.models[param] = model
                    self.logger.info("Modelo pkl {} cargado: {}".format(param, pkl_path))
                    continue
                except Exception as e:
                    self.logger.warning("Fallo cargando pkl {}, intentando npz: {}".format(pkl_path, e))

            if os.path.exists(npz_path):
                try:
                    # Cargar sin pickle (más seguro, compatible Python2)
                    arr = np.load(npz_path, allow_pickle=False)
                    
                    # Formato nuevo: cada árbol como t{i}_children_left, t{i}_children_right, etc.
                    if 'n_trees' in arr:
                        n_trees = int(arr['n_trees'])
                        trees = []
                        for i in range(n_trees):
                            prefix = "t{}_".format(i)
                            tree = {
                                'children_left': arr[prefix + 'children_left'].astype(np.int32),
                                'children_right': arr[prefix + 'children_right'].astype(np.int32),
                                'feature': arr[prefix + 'feature'].astype(np.int32),
                                'threshold': arr[prefix + 'threshold'].astype(np.float64),
                                'value': arr[prefix + 'value'].astype(np.float64),
                            }
                            trees.append(tree)
                        self.models[param] = trees
                        self.logger.info("Modelo npz {} (n_trees={}) cargado: {}".format(param, n_trees, npz_path))
                        continue
                    
                    # Fallback: formato anterior con 'forest' (object array) - requiere pickle
                    arr = np.load(npz_path, allow_pickle=True)
                    if 'forest' in arr:
                        forest = arr['forest']
                        trees = []
                        for t in forest:
                            tree = {
                                'children_left': np.asarray(t['children_left']).astype(np.int32),
                                'children_right': np.asarray(t['children_right']).astype(np.int32),
                                'feature': np.asarray(t['feature']).astype(np.int32),
                                'threshold': np.asarray(t['threshold']).astype(np.float64),
                                'value': np.asarray(t['value']).astype(np.float64),
                            }
                            trees.append(tree)
                        self.models[param] = trees
                        self.logger.info("Modelo npz (forest) {} cargado: {}".format(param, npz_path))
                        continue
                    
                    # Fallback: árbol único con arrays directos
                    if 'children_left' in arr:
                        tree = {
                            'children_left': arr['children_left'].astype(np.int32),
                            'children_right': arr['children_right'].astype(np.int32),
                            'feature': arr['feature'].astype(np.int32),
                            'threshold': arr['threshold'].astype(np.float64),
                            'value': arr['value'].astype(np.float64),
                        }
                        self.models[param] = tree
                        self.logger.info("Modelo npz único {} cargado: {}".format(param, npz_path))
                        continue
                    
                    raise RuntimeError("Formato NPZ no reconocido: {}".format(npz_path))
                    self.logger.info("Modelo npz {} cargado: {}".format(param, npz_path))
                    continue
                except Exception as e:
                    raise RuntimeError("Error cargando modelo npz {}: {}".format(npz_path, e))

            raise RuntimeError("Modelo no encontrado para {} (esperado .pkl o .npz)".format(param))

        self.logger.info("Todos los modelos Random Forest cargados correctamente (modo: {})".format('joblib' if JOBLIB_AVAILABLE else 'npz'))

    def _predict_tree_np(self, tree, x):
        """Predecir una muestra x (1D array) en un árbol exportado a arrays."""
        node = 0
        while True:
            feat = int(tree['feature'][node])
            if feat < 0:
                # hoja: value may be shape (1,) or (n_outputs,)
                val = tree['value'][node]
                # si value es array, tomar su primera componente
                return float(np.array(val).ravel()[0])
            thr = tree['threshold'][node]
            if x[feat] <= thr:
                node = int(tree['children_left'][node])
            else:
                node = int(tree['children_right'][node])

    
    def get_sensor_data(self):
        """Recolectar datos de sensores del robot"""
        if self.memory is None:
            # Modo simulación - datos sintéticos
            return {
                'accel_x': np.random.normal(0, 0.1),
                'accel_y': np.random.normal(0, 0.1), 
                'accel_z': np.random.normal(9.8, 0.2),
                'gyro_x': np.random.normal(0, 0.01),
                'gyro_y': np.random.normal(0, 0.01),
                'gyro_z': np.random.normal(0, 0.01),
                'angle_x': np.random.normal(0, 0.05),
                'angle_y': np.random.normal(0, 0.05),
                'lfoot_fl': np.random.uniform(0, 1),
                'lfoot_fr': np.random.uniform(0, 1),
                'lfoot_rl': np.random.uniform(0, 1),
                'lfoot_rr': np.random.uniform(0, 1),
                'rfoot_fl': np.random.uniform(0, 1),
                'rfoot_fr': np.random.uniform(0, 1),
                'rfoot_rl': np.random.uniform(0, 1),
                'rfoot_rr': np.random.uniform(0, 1),
                'vx': np.random.normal(0, 0.02),
                'vy': np.random.normal(0, 0.01),
                'wz': np.random.normal(0, 0.05),
                'vtotal': abs(np.random.normal(0.01, 0.02))
            }
        
        try:
            # Datos reales de sensores NAOqi
            data = {}
            
            # Acelerómetro
            accel = self.memory.getData("Device/SubDeviceList/InertialSensor/AccelerometerX/Sensor/Value")
            data['accel_x'] = accel if accel is not None else 0.0
            accel = self.memory.getData("Device/SubDeviceList/InertialSensor/AccelerometerY/Sensor/Value")
            data['accel_y'] = accel if accel is not None else 0.0
            accel = self.memory.getData("Device/SubDeviceList/InertialSensor/AccelerometerZ/Sensor/Value")
            data['accel_z'] = accel if accel is not None else 9.8
            
            # Giroscopio
            gyro = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroscopeX/Sensor/Value")
            data['gyro_x'] = gyro if gyro is not None else 0.0
            gyro = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroscopeY/Sensor/Value")
            data['gyro_y'] = gyro if gyro is not None else 0.0
            gyro = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroscopeZ/Sensor/Value")
            data['gyro_z'] = gyro if gyro is not None else 0.0
            
            # Ángulos corporales
            angle = self.memory.getData("Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value")
            data['angle_x'] = angle if angle is not None else 0.0
            angle = self.memory.getData("Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value")
            data['angle_y'] = angle if angle is not None else 0.0
            
            # Sensores de presión pies
            pressure_sensors = [
                ("lfoot_fl", "Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value"),
                ("lfoot_fr", "Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value"),
                ("rfoot_fl", "Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value"),
                ("rfoot_fr", "Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value"),
            ]
            
            for key, sensor_key in pressure_sensors:
                value = self.memory.getData(sensor_key)
                data[key] = value if value is not None else 0.0
            
            # Sensores traseros (aproximación)
            data['lfoot_rl'] = data['lfoot_fl'] * 0.8
            data['lfoot_rr'] = data['lfoot_fr'] * 0.8
            data['rfoot_rl'] = data['rfoot_fl'] * 0.8
            data['rfoot_rr'] = data['rfoot_fr'] * 0.8
            
            # Velocidades de odometría
            if self.motion:
                try:
                    odom = self.motion.getPosition("Torso", 2, True)  # Robot frame
                    data['vx'] = odom[0] if len(odom) > 0 else 0.0
                    data['vy'] = odom[1] if len(odom) > 1 else 0.0
                    data['wz'] = odom[5] if len(odom) > 5 else 0.0
                    data['vtotal'] = np.sqrt(data['vx']**2 + data['vy']**2)
                except:
                    data.update({'vx': 0.0, 'vy': 0.0, 'wz': 0.0, 'vtotal': 0.0})
            else:
                data.update({'vx': 0.0, 'vy': 0.0, 'wz': 0.0, 'vtotal': 0.0})
            
            return data
            
        except Exception as e:
            self.logger.error("Error leyendo sensores: {}".format(e))
            # Retornar datos por defecto en caso de error
            return {feat: 0.0 for feat in FEAT_ORDER}
    
    def process_features(self, sensor_data):
        """Procesar datos de sensores y aplicar filtros"""
        # Convertir a array de features en orden correcto
        features = np.array([sensor_data.get(feat, 0.0) for feat in FEAT_ORDER], dtype=np.float32)
        
        # Filtro EMA (Exponential Moving Average)
        if len(self.feature_history) == 0:
            self.ema_features = features.copy()
        else:
            self.ema_features = self.ema_alpha * features + (1 - self.ema_alpha) * self.ema_features
        
        # Mantener historial
        self.feature_history.append(features)
        if len(self.feature_history) > self.history_size:
            self.feature_history.pop(0)
        
        return self.ema_features
    
    def predict_gait_params(self, features):
        """Predecir parámetros de marcha usando modelos Random Forest"""
        inference_start = time.time()
        predictions_norm = {}  # Para logging (valores normalizados 0-1)
        
        try:
            # Escalar features: soportar scaler sklearn o dict {'mean','scale'} cargado desde npz
            x = features.reshape(1, -1)
            if hasattr(self.scaler, 'transform'):
                features_scaled = self.scaler.transform(x)
            else:
                # scaler dict
                mean = self.scaler['mean']
                scale = self.scaler['scale']
                features_scaled = (x - mean.reshape(1, -1)) / (scale.reshape(1, -1) + 1e-12)

            predictions = {}
            for param in GAIT_KEYS:
                model = self.models[param]
                # Si el modelo es un objeto sklearn RandomForestRegressor
                if hasattr(model, 'predict'):
                    pred_norm = model.predict(features_scaled)[0]
                else:
                    # modelo exportado en formato npz -> simulamos promedio de árboles
                    # permitimos que model sea dict representando un solo árbol o lista de árboles
                    if isinstance(model, dict):
                        # modelo guardado como arrays de un único árbol
                        pred = self._predict_tree_np(model, features_scaled.ravel())
                        pred_norm = pred
                    elif isinstance(model, list):
                        # lista de árboles (cada uno dict)
                        vals = [self._predict_tree_np(t, features_scaled.ravel()) for t in model]
                        pred_norm = float(np.mean(vals))
                    else:
                        raise RuntimeError("Tipo de modelo desconocido para {}".format(param))

                # Guardar valor normalizado para logging
                predictions_norm[param] = float(pred_norm)
                
                # Desnormalizar usando rangos físicos
                min_val, max_val = PARAM_RANGES[param]
                pred_real = min_val + float(pred_norm) * (max_val - min_val)

                # Clamp a rangos válidos
                pred_real = np.clip(pred_real, min_val, max_val)
                predictions[param] = float(pred_real)

            inference_time = time.time() - inference_start
            
            # Log datos para reentrenamiento
            self.log_adaptation_data(features, predictions_norm, predictions, True, inference_time)
            
            return predictions
            
        except Exception as e:
            inference_time = time.time() - inference_start
            self.logger.error("Error en predicción: {}".format(e))
            
            # Log error para reentrenamiento
            default_predictions = DEFAULT_GAIT.copy()
            default_norm = {}
            for param in GAIT_KEYS:
                min_val, max_val = PARAM_RANGES[param]
                default_norm[param] = (default_predictions[param] - min_val) / (max_val - min_val)
            
            self.log_adaptation_data(features, default_norm, default_predictions, False, inference_time)
            
            return default_predictions
    
    def apply_gait_params(self, gait_params):
        """Aplicar parámetros de marcha al robot"""
        if self.motion is None:
            self.logger.info("Modo simulación - parámetros: {}".format(
                {k: "{:.3f}".format(v) for k, v in gait_params.items()}))
            return True
        
        try:
            # Aplicar cada parámetro usando ALMotion
            for param, value in gait_params.items():
                if param in ['StepHeight', 'MaxStepX', 'MaxStepY', 'MaxStepTheta']:
                    self.motion.setMotionConfig([[param, value]])
                elif param == 'Frequency':
                    # Frequency puede requerir manejo especial
                    self.motion.setMotionConfig([["StepFrequency", value]])
            
            self.logger.debug("Parámetros aplicados: {}".format(
                {k: "{:.3f}".format(v) for k, v in gait_params.items()}))
            return True
            
        except Exception as e:
            self.logger.error("Error aplicando parámetros: {}".format(e))
            return False
    
    def adaptation_loop(self):
        """Loop principal de adaptación"""
        self.logger.info("Iniciando loop de adaptación...")
        
        while not self.stop_event.is_set():
            if not self.enabled:
                time.sleep(0.1)
                continue
            
            try:
                current_time = time.time()
                
                # Control de frecuencia
                if current_time - self.last_update_time < self.update_interval:
                    time.sleep(0.05)
                    continue
                
                # 1. Recolectar datos de sensores
                sensor_data = self.get_sensor_data()
                
                # 2. Procesar features
                features = self.process_features(sensor_data)
                
                # 3. Predecir parámetros con Random Forest
                gait_params = self.predict_gait_params(features)
                
                # 4. Aplicar parámetros al robot
                self.apply_gait_params(gait_params)
                
                self.last_update_time = current_time
                
            except Exception as e:
                self.logger.error("Error en loop de adaptación: {}".format(e))
                time.sleep(0.5)
        
        self.logger.info("Loop de adaptación terminado")
    
    def start(self):
        """Iniciar sistema adaptativo"""
        if self.running:
            self.logger.warning("Sistema ya está ejecutándose")
            return False
        
        try:
            # Conectar al robot
            if not self.connect_robot():
                return False
            
            # Cargar modelos
            self.load_models()
            
            # Iniciar thread de adaptación
            self.running = True
            self.stop_event.clear()
            self.adaptation_thread = Thread(target=self.adaptation_loop)
            self.adaptation_thread.daemon = True
            self.adaptation_thread.start()
            
            self.logger.info("Sistema de marcha adaptativa iniciado")
            return True
            
        except Exception as e:
            self.logger.error("Error iniciando sistema: {}".format(e))
            self.running = False
            return False
    
    def stop(self):
        """Detener sistema adaptativo"""
        if not self.running:
            return
        
        self.logger.info("Deteniendo sistema adaptativo...")
        self.enabled = False
        self.stop_event.set()
        
        if hasattr(self, 'adaptation_thread'):
            self.adaptation_thread.join(timeout=2.0)
        
        # Cerrar CSV logging
        self.close_csv_logging()
        
        self.running = False
        self.logger.info("Sistema adaptativo detenido")
    
    def enable(self):
        """Habilitar adaptación"""
        self.enabled = True
        self.logger.info("Adaptación habilitada")
    
    def disable(self):
        """Deshabilitar adaptación"""
        self.enabled = False
        self.logger.info("Adaptación deshabilitada")
    
    def get_status(self):
        """Obtener estado del sistema"""
        return {
            'running': self.running,
            'enabled': self.enabled,
            'models_loaded': len(self.models) == len(GAIT_KEYS),
            'connected': self.motion is not None,
            'feature_history_size': len(self.feature_history)
        }

def main():
    parser = argparse.ArgumentParser(description='Sistema de marcha adaptativa con Random Forest')
    parser.add_argument('--robot-ip', default='localhost',
                        help='IP del robot NAO (default: localhost)')
    parser.add_argument('--robot-port', type=int, default=9559,
                        help='Puerto del robot NAO (default: 9559)')
    parser.add_argument('--models-dir', default='models',
                        help='Directorio con modelos Random Forest (default: models)')
    parser.add_argument('--log-dir', default='logs',
                        help='Directorio para logs CSV (default: logs)')
    parser.add_argument('--enable', action='store_true',
                        help='Habilitar adaptación al inicio')
    parser.add_argument('--log-level', default='info',
                        choices=['debug', 'info', 'warning', 'error'],
                        help='Nivel de logging (default: info)')
    parser.add_argument('--disable-csv', action='store_true',
                        help='Deshabilitar logging CSV')
    
    args = parser.parse_args()
    
    # Configurar logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Crear sistema adaptativo
    system = AdaptiveWalkRandomForest(
        robot_ip=args.robot_ip,
        robot_port=args.robot_port,
        models_dir=args.models_dir,
        log_dir=args.log_dir
    )
    
    # Deshabilitar CSV si se especifica
    if args.disable_csv:
        system.csv_enabled = False
    
    try:
        # Iniciar sistema
        if not system.start():
            print("[ERROR] No se pudo iniciar el sistema")
            return 1
        
        # Habilitar si se especifica
        if args.enable:
            system.enable()
        
        print("[INFO] Sistema iniciado. Presiona Ctrl+C para detener")
        print("[INFO] Comandos disponibles:")
        print("  - Enviar 'enable' para habilitar adaptación")
        print("  - Enviar 'disable' para deshabilitar adaptación")
        print("  - Enviar 'status' para ver estado")
        print("  - Enviar 'quit' para salir")
        
        # Loop interactivo
        while True:
            try:
                cmd = safe_input("> ").strip().lower()
                
                if cmd == 'enable':
                    system.enable()
                elif cmd == 'disable':
                    system.disable()
                elif cmd == 'status':
                    status = system.get_status()
                    print("Estado: {}".format(json.dumps(status, indent=2)))
                elif cmd in ['quit', 'exit', 'q']:
                    break
                elif cmd == 'help':
                    print("Comandos: enable, disable, status, quit")
                else:
                    print("Comando desconocido: {}".format(cmd))
                    
            except EOFError:
                break
            except KeyboardInterrupt:
                break
    
    except KeyboardInterrupt:
        pass
    finally:
        system.stop()
        print("\n[INFO] Sistema detenido")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
