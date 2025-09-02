#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
adaptive_walk_lightgbm_nao.py - Adaptive Walk con modelos LightGBM AutoML

Versión actualizada de adaptive_walk_r        # 🌟 SISTEMA DE DOS MODOS
        self.mode = mode  # "training" o "production"
        
        # Parámetros óptimos para pasto sintético (del análisis de logs)
        self.optimal_grass_params = OPTIMAL_GRASS_PARAMS.copy()
        
        # Parámetros específicos por tipo de movimiento
        self.movement_params = MOVEMENT_SPECIFIC_PARAMS.copy() if MOVEMENT_SPECIFIC_PARAMS else {}
        
        # Estado actual de velocidades para detectar tipo de movimiento
        self.current_velocities = {'vx': 0.0, 'vy': 0.0, 'wz': 0.0}
        
        # Configuración de caminata por defecto (fallback)y que usa los modelos
LightGBM optimizados con AutoML para mejor rendimiento.

CARACTERÍSTICAS:
- Solo maneja predicción de parámetros y control de caminata
- NO inicializa automáticamente postura del robot
- NO configura automáticamente brazos o rigidez  
- Diseñado para integrarse con sistemas de control externos

INSTRUCCIONES DE DEPLOYMENT:
1. Copiar models_npz_automl/ al NAO en el mismo directorio que este script
2. Reemplazar adaptive_walk_randomforest.py con este archivo
3. Integrar con control_server.py o sistema de control externo
"""

from __future__ import print_function
import sys
import time
import math
import numpy as np
import os

# Importaciones NAO
try:
    from naoqi import ALProxy
    import almath
    print("[INFO] NAOqi importado correctamente")
except ImportError:
    print("[ERROR] NAOqi no disponible - simulación modo")
    ALProxy = None
    almath = None

# Configuración de features y targets
try:
    from nao_config import FEATURE_ORDER, GAIT_TARGETS, OPTIMAL_GRASS_PARAMS, MOVEMENT_SPECIFIC_PARAMS
    print("[INFO] Configuración cargada desde nao_config.py")
except ImportError:
    print("[WARN] nao_config.py no disponible, usando configuración embebida")
    FEATURE_ORDER = [
        'accel_x','accel_y','accel_z',
        'gyro_x','gyro_y','gyro_z', 
        'angle_x','angle_y',
        'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
        'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
        'vx','vy','wz','vtotal'
    ]
    GAIT_TARGETS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']
    OPTIMAL_GRASS_PARAMS = {
        'StepHeight': 0.020000,
        'MaxStepX': 0.040000, 
        'MaxStepY': 0.140000,
        'MaxStepTheta': 0.349000,
        'Frequency': 1.000000
    }
    MOVEMENT_SPECIFIC_PARAMS = {}  # Fallback vacío

class LightGBMNAOPredictor:
    """Predictor LightGBM optimizado para NAO usando solo NumPy"""
    
    def __init__(self, model_path):
        self.model_data = np.load(model_path)
        self.n_features = int(self.model_data['n_features'])
        self.n_trees = int(self.model_data['n_trees'])
        
        # Deserializar árboles
        trees_data = self.model_data['trees_data']
        trees_lengths = self.model_data['trees_lengths']
        
        self.trees = []
        offset = 0
        for length in trees_lengths:
            tree_array = trees_data[offset:offset+length]
            tree_dict = self._deserialize_tree(tree_array, 0)[0]
            self.trees.append(tree_dict)
            offset += length
        
        print("[INFO] Modelo LightGBM cargado: {} árboles, {} features".format(self.n_trees, self.n_features))
    
    def _deserialize_tree(self, tree_array, idx):
        """Deserializar árbol desde array"""
        if tree_array[idx] == 1:  # Hoja
            return {'is_leaf': True, 'value': tree_array[idx+1]}, idx+2
        else:  # Nodo interno
            feature_idx = int(tree_array[idx+1])
            threshold = tree_array[idx+2]
            left_size = int(tree_array[idx+3])
            
            left_tree, next_idx = self._deserialize_tree(tree_array, idx+4)
            right_tree, final_idx = self._deserialize_tree(tree_array, next_idx)
            
            return {
                'is_leaf': False,
                'feature_idx': feature_idx,
                'threshold': threshold,
                'left': left_tree,
                'right': right_tree
            }, final_idx
    
    def predict_single(self, x):
        """Predecir un sample"""
        result = 0.0
        for tree in self.trees:
            result += self._traverse_tree(tree, x)
        return result
    
    def _traverse_tree(self, tree, x):
        """Atravesar árbol"""
        if tree['is_leaf']:
            return tree['value']
        
        if x[tree['feature_idx']] <= tree['threshold']:
            return self._traverse_tree(tree['left'], x)
        else:
            return self._traverse_tree(tree['right'], x)
    
    def close(self):
        """Cerrar archivo NPZ"""
        self.model_data.close()

class FeatureScalerNAO:
    """Scaler de features optimizado para NAO"""
    
    def __init__(self, scaler_path):
        self.scaler_data = np.load(scaler_path)
        self.scaler_type = str(self.scaler_data['scaler_type'])
        self.mean = self.scaler_data['mean']
        self.scale = self.scaler_data['scale']
        print("[INFO] Scaler cargado: {}".format(self.scaler_type))
    
    def transform(self, X):
        """Transformar features"""
        if self.scaler_type == "StandardScaler":
            return (X - self.mean) / self.scale
        elif self.scaler_type == "MinMaxScaler":
            return X * self.scale + self.mean
        else:  # IdentityScaler
            return X
    
    def close(self):
        """Cerrar archivo NPZ"""
        self.scaler_data.close()

class AdaptiveWalkLightGBM:
    """
    Sistema de caminata adaptiva con modelos LightGBM AutoML - DOS MODOS:
    
    MODO TRAINING: Usa predicciones ML para explorar y optimizar
    MODO PRODUCTION: Converge hacia parámetros óptimos fijos para pasto sintético
    
    CONFIGURACIÓN:
    - No inicializa automáticamente la postura del robot (manejado por control externo)
    - No configura automáticamente brazos o rigidez (manejado por control externo)
    - Solo proporciona predicciones y control de caminata adaptiva
    """
    
    def __init__(self, models_dir="models_npz_automl", mode="production"):
        self.models_dir = models_dir
        self.models = {}
        self.scaler = None
        self.motion = None
        self.memory = None
        self.enabled = False
        
        # � SISTEMA DE DOS MODOS
        self.mode = mode  # "training" o "production"
        
        # Parámetros óptimos para pasto sintético (del análisis de logs)
        self.optimal_grass_params = {
            'StepHeight': 0.020000,
            'MaxStepX': 0.040000, 
            'MaxStepY': 0.140000,
            'MaxStepTheta': 0.349000,
            'Frequency': 1.000000
        }
        
        # Configuración de caminata por defecto (fallback)
        self.default_params = {
            'StepHeight': 0.02,
            'MaxStepX': 0.04, 
            'MaxStepY': 0.14,
            'MaxStepTheta': 0.35,
            'Frequency': 1.0
        }
        
        # 🎯 PARÁMETROS ESPECÍFICOS POR MOVIMIENTO
        # Actualizar parámetros óptimos desde configuración
        self.optimal_grass_params = OPTIMAL_GRASS_PARAMS.copy()
        
        # Parámetros específicos por tipo de movimiento
        self.movement_params = MOVEMENT_SPECIFIC_PARAMS.copy() if MOVEMENT_SPECIFIC_PARAMS else {}
        
        # Estado actual de velocidades para detectar tipo de movimiento
        self.current_velocities = {'vx': 0.0, 'vy': 0.0, 'wz': 0.0}
        
        self.current_params = self.default_params.copy()
        self.prediction_history = []
        self.stability_threshold = 0.8
        self.adaptation_rate = 0.1
        
        # Inicializar NAO proxies
        self._init_nao_proxies()
        
        # Cargar modelos AutoML
        models_loaded = self._load_automl_models()
        if not models_loaded:
            print("[WARN] Modelos LightGBM no disponibles, usando modo simulación")
        
        # 🌟 NUEVO: Cargar parámetros golden si están disponibles
        self._load_golden_parameters()
    
    def _init_nao_proxies(self):
        """Inicializar proxies NAO"""
        if ALProxy is None:
            print("[WARN] Modo simulación - NAOqi no disponible")
            return
        
        try:
            print("[INFO] Intentando conectar a NAOqi...")
            print("[INFO] IP: 127.0.0.1, Puerto: 9559")
            
            # Intentar crear proxies con timeout
            self.motion = ALProxy("ALMotion", "127.0.0.1", 9559)
            self.memory = ALProxy("ALMemory", "127.0.0.1", 9559)
            
            # Verificar que los proxies funcionan
            robot_awake = self.motion.robotIsWakeUp()
            print("[INFO] Proxies NAO inicializados")
            print("[INFO] Robot despierto: {}".format(robot_awake))
            
            # Nota: No despertamos automáticamente - el control externo maneja esto
            if not robot_awake:
                print("[INFO] Robot en modo sleep - usar control externo para despertar")
                
        except Exception as e:
            print("[ERROR] Error inicializando proxies: {}".format(e))
            print("[INFO] Posibles causas:")
            print("  - NAOqi no está ejecutándose")
            print("  - Robot apagado o en modo sleep")
            print("  - IP/Puerto incorrectos")
            print("  - Problemas de red")
            print("[INFO] Continuando en modo simulación...")
            self.motion = None
            self.memory = None
    
    def _load_automl_models(self):
        """Cargar modelos LightGBM AutoML"""
        print("[INFO] Cargando modelos desde {}/".format(self.models_dir))
        
        # Verificar que el directorio existe
        if not os.path.exists(self.models_dir):
            print("[ERROR] Directorio de modelos no encontrado: {}".format(self.models_dir))
            print("[INFO] Creando directorio de modelos para futuro uso...")
            try:
                os.makedirs(self.models_dir)
            except Exception as e:
                print("[WARN] No se pudo crear directorio: {}".format(e))
            return False
        
        try:
            # Cargar scaler
            scaler_path = os.path.join(self.models_dir, "feature_scaler.npz")
            if os.path.exists(scaler_path):
                self.scaler = FeatureScalerNAO(scaler_path)
            else:
                print("[ERROR] Scaler no encontrado: {}".format(scaler_path))
                print("[INFO] Archivos disponibles en {}:".format(self.models_dir))
                try:
                    files = os.listdir(self.models_dir)
                    for f in files:
                        print("  - {}".format(f))
                except Exception:
                    print("  (No se pudo listar directorio)")
                return False
            
            # Cargar modelos por target
            for target in GAIT_TARGETS:
                model_path = os.path.join(self.models_dir, "lightgbm_model_{}.npz".format(target))
                
                if os.path.exists(model_path):
                    self.models[target] = LightGBMNAOPredictor(model_path)
                    print("[INFO] Modelo {} cargado exitosamente".format(target))
                else:
                    print("[ERROR] Modelo no encontrado: {}".format(model_path))
                    return False
            
            print("[SUCCESS] {} modelos LightGBM cargados".format(len(self.models)))
            return True
            
        except Exception as e:
            print("[ERROR] Error cargando modelos: {}".format(e))
            return False
    
    def _load_golden_parameters(self):
        """Cargar parámetros golden desde CSV si están disponibles"""
        try:
            if not os.path.exists(self.golden_csv_path):
                print("[INFO] No se encontró archivo golden CSV: {}".format(self.golden_csv_path))
                return
            
            # Leer parámetros golden (implementación simplificada)
            print("[INFO] Sistema golden parameters disponible: {}".format(self.golden_csv_path))
            # Por ahora no cargamos automáticamente, solo reportamos disponibilidad
            
        except Exception as e:
            print("[WARN] Error cargando parámetros golden: {}".format(e))
    
    def set_mode(self, mode):
        """
        Cambiar modo de operación del sistema adaptativo
        
        Args:
            mode (str): "training" o "production"
        """
        if mode not in ["training", "production"]:
            print("[ERROR] Modo inválido: {}. Usar 'training' o 'production'".format(mode))
            return False
        
        old_mode = self.mode
        self.mode = mode
        
        print("[INFO] Modo cambiado: {} -> {}".format(old_mode, mode))
        
        if mode == "production":
            print("[INFO] MODO PRODUCTION: Convergiendo hacia parámetros óptimos para pasto sintético")
            print("[INFO] Parámetros objetivo: {}".format(self.optimal_grass_params))
        else:
            print("[INFO] MODO TRAINING: Usando predicciones ML para exploración")
        
        return True
    
    def get_mode(self):
        """Obtener modo actual"""
        return self.mode
    
    def _get_sensor_data(self):
        """Obtener datos de sensores del NAO"""
        if not self.memory:
            # Datos simulados para testing
            return {
                'accel_x': 0.1, 'accel_y': 0.0, 'accel_z': 9.8,
                'gyro_x': 0.0, 'gyro_y': 0.0, 'gyro_z': 0.0,
                'angle_x': 0.0, 'angle_y': 0.0,
                'lfoot_fl': 0.5, 'lfoot_fr': 0.5, 'lfoot_rl': 0.5, 'lfoot_rr': 0.5,
                'rfoot_fl': 0.5, 'rfoot_fr': 0.5, 'rfoot_rl': 0.5, 'rfoot_rr': 0.5,
                'vx': 0.02, 'vy': 0.0, 'wz': 0.0, 'vtotal': 0.02
            }
        
        try:
            # Leer sensores reales
            sensor_data = {}
            
            # IMU data
            accel = self.memory.getData("Device/SubDeviceList/InertialSensor/AccelerometerX/Sensor/Value")
            sensor_data['accel_x'] = accel if accel else 0.0
            accel = self.memory.getData("Device/SubDeviceList/InertialSensor/AccelerometerY/Sensor/Value") 
            sensor_data['accel_y'] = accel if accel else 0.0
            accel = self.memory.getData("Device/SubDeviceList/InertialSensor/AccelerometerZ/Sensor/Value")
            sensor_data['accel_z'] = accel if accel else 9.8
            
            gyro = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroscopeX/Sensor/Value")
            sensor_data['gyro_x'] = gyro if gyro else 0.0
            gyro = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroscopeY/Sensor/Value")
            sensor_data['gyro_y'] = gyro if gyro else 0.0
            gyro = self.memory.getData("Device/SubDeviceList/InertialSensor/GyroscopeZ/Sensor/Value")
            sensor_data['gyro_z'] = gyro if gyro else 0.0
            
            angle = self.memory.getData("Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value")
            sensor_data['angle_x'] = angle if angle else 0.0
            angle = self.memory.getData("Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value")
            sensor_data['angle_y'] = angle if angle else 0.0
            
            # FSR data
            for foot in ['lfoot', 'rfoot']:
                for sensor in ['fl', 'fr', 'rl', 'rr']:
                    key = "{}_{}".format(foot, sensor)
                    foot_name = "LFoot" if foot == 'lfoot' else "RFoot"
                    sensor_name = {"fl": "FrontLeft", "fr": "FrontRight", 
                                 "rl": "RearLeft", "rr": "RearRight"}[sensor]
                    
                    fsr_path = "Device/SubDeviceList/{}/FSR/{}/Sensor/Value".format(foot_name, sensor_name)
                    fsr_value = self.memory.getData(fsr_path)
                    sensor_data[key] = fsr_value if fsr_value else 0.0
            
            # Velocity data (estimado desde motion)
            if self.motion:
                robot_velocity = self.motion.getRobotVelocity()
                sensor_data['vx'] = robot_velocity[0] if len(robot_velocity) > 0 else 0.0
                sensor_data['vy'] = robot_velocity[1] if len(robot_velocity) > 1 else 0.0
                sensor_data['wz'] = robot_velocity[2] if len(robot_velocity) > 2 else 0.0
                sensor_data['vtotal'] = math.sqrt(sensor_data['vx']**2 + sensor_data['vy']**2)
            else:
                sensor_data.update({'vx': 0.0, 'vy': 0.0, 'wz': 0.0, 'vtotal': 0.0})
            
            return sensor_data
            
        except Exception as e:
            print("[ERROR] Error leyendo sensores: {}".format(e))
            return self._get_sensor_data()  # Fallback a datos simulados
    
    def _apply_feature_engineering(self, sensor_data):
        """Aplicar feature engineering como en AutoML"""
        # Características derivadas FSR
        sensor_data['lfoot_total'] = (sensor_data['lfoot_fl'] + sensor_data['lfoot_fr'] + 
                                    sensor_data['lfoot_rl'] + sensor_data['lfoot_rr'])
        sensor_data['rfoot_total'] = (sensor_data['rfoot_fl'] + sensor_data['rfoot_fr'] + 
                                    sensor_data['rfoot_rl'] + sensor_data['rfoot_rr'])
        sensor_data['feet_total'] = sensor_data['lfoot_total'] + sensor_data['rfoot_total']
        
        if sensor_data['feet_total'] > 1e-6:
            sensor_data['feet_balance'] = ((sensor_data['lfoot_total'] - sensor_data['rfoot_total']) / 
                                         sensor_data['feet_total'])
        else:
            sensor_data['feet_balance'] = 0.0
        
        # Magnitudes de sensores
        sensor_data['accel_magnitude'] = math.sqrt(sensor_data['accel_x']**2 + 
                                                 sensor_data['accel_y']**2 + 
                                                 sensor_data['accel_z']**2)
        
        sensor_data['gyro_magnitude'] = math.sqrt(sensor_data['gyro_x']**2 + 
                                                sensor_data['gyro_y']**2 + 
                                                sensor_data['gyro_z']**2)
        
        # Índice de estabilidad
        sensor_data['stability_index'] = math.sqrt(sensor_data['angle_x']**2 + 
                                                 sensor_data['angle_y']**2)
        
        return sensor_data
    
    def _detect_movement_type(self, vx=None, vy=None, wz=None):
        """
        Detectar tipo de movimiento basado en velocidades actuales
        
        Returns:
            str: Tipo de movimiento ('forward', 'backward', 'sideways', 'rotation', 'mixed')
        """
        # Usar velocidades pasadas como parámetro o las almacenadas
        if vx is not None:
            self.current_velocities['vx'] = vx
        if vy is not None:
            self.current_velocities['vy'] = vy
        if wz is not None:
            self.current_velocities['wz'] = wz
            
        vx = abs(self.current_velocities['vx'])
        vy = abs(self.current_velocities['vy'])
        wz = abs(self.current_velocities['wz'])
        
        # Umbrales para detección
        forward_threshold = 0.1
        sideways_threshold = 0.1
        rotation_threshold = 0.2
        
        # Clasificar movimiento
        is_forward = vx > forward_threshold
        is_sideways = vy > sideways_threshold
        is_rotating = wz > rotation_threshold
        
        # Determinar tipo principal
        if is_rotating and not (is_forward or is_sideways):
            return 'rotation'
        elif is_forward and not is_sideways and self.current_velocities['vx'] > 0:
            return 'forward'
        elif is_forward and not is_sideways and self.current_velocities['vx'] < 0:
            return 'backward'
        elif is_sideways and not is_forward:
            return 'sideways'
        elif (is_forward or is_sideways) and is_rotating:
            return 'mixed'
        else:
            return 'forward'  # Default para movimiento mínimo
    
    def _get_movement_specific_params(self, movement_type):
        """
        Obtener parámetros específicos para el tipo de movimiento
        
        Args:
            movement_type (str): Tipo de movimiento detectado
            
        Returns:
            dict: Parámetros optimizados para ese tipo de movimiento
        """
        if movement_type in self.movement_params:
            params = self.movement_params[movement_type].copy()
            print("[INFO] Usando parámetros específicos para movimiento: {}".format(movement_type))
            return params
        else:
            print("[WARN] Tipo de movimiento '{}' no encontrado, usando parámetros generales".format(movement_type))
            return self.optimal_grass_params.copy()
    
    def predict_gait_parameters(self, vx=None, vy=None, wz=None):
        """
        Predecir parámetros de caminata con DOS MODOS:
        - TRAINING: Usa predicciones ML para explorar
        - PRODUCTION: Converge hacia parámetros óptimos específicos por movimiento
        
        Args:
            vx, vy, wz: Velocidades actuales para detectar tipo de movimiento (opcional)
        """
        
        # 🎯 MODO PRODUCTION: Retornar parámetros específicos por tipo de movimiento
        if self.mode == "production":
            # Detectar tipo de movimiento si se proporcionan velocidades
            if any(v is not None for v in [vx, vy, wz]):
                movement_type = self._detect_movement_type(vx, vy, wz)
                params = self._get_movement_specific_params(movement_type)
                print("[INFO] Modo PRODUCTION: movimiento '{}' → parámetros específicos".format(movement_type))
            else:
                params = self.optimal_grass_params.copy()
                print("[INFO] Modo PRODUCTION: usando parámetros generales óptimos")
            
            return params
        
        # 🤖 MODO TRAINING: Usar predicciones ML (comportamiento original)
        if not self.models or not self.scaler:
            print("[WARN] Modelos no disponibles, usando parámetros por defecto")
            return self.default_params.copy()
        
        try:
            print("[INFO] Modo TRAINING: usando predicciones ML")
            
            # Obtener datos de sensores
            sensor_data = self._get_sensor_data()
            
            # Aplicar feature engineering 
            sensor_data = self._apply_feature_engineering(sensor_data)
            
            # Preparar features en orden correcto
            feature_vector = []
            
            # Features originales
            for feature_name in FEATURE_ORDER:
                feature_vector.append(sensor_data.get(feature_name, 0.0))
            
            # Features engineered
            engineered_features = ['lfoot_total', 'rfoot_total', 'feet_total', 'feet_balance',
                                 'accel_magnitude', 'gyro_magnitude', 'stability_index']
            for feature_name in engineered_features:
                feature_vector.append(sensor_data.get(feature_name, 0.0))
            
            # Convertir a numpy array
            X = np.array(feature_vector, dtype=np.float64)
            
            # Escalar features
            X_scaled = self.scaler.transform(X)
            
            # Predecir con cada modelo
            predictions = {}
            for target_name, model in self.models.items():
                try:
                    pred_value = model.predict_single(X_scaled)
                    
                    # Aplicar límites de seguridad
                    if target_name == 'StepHeight':
                        pred_value = max(0.005, min(0.05, pred_value))
                    elif target_name == 'MaxStepX':
                        pred_value = max(0.01, min(0.08, pred_value))
                    elif target_name == 'MaxStepY':
                        pred_value = max(0.05, min(0.20, pred_value))
                    elif target_name == 'MaxStepTheta':
                        pred_value = max(0.1, min(0.5, pred_value))
                    elif target_name == 'Frequency':
                        pred_value = max(0.5, min(2.0, pred_value))
                    
                    predictions[target_name] = float(pred_value)
                    
                except Exception as e:
                    print("[ERROR] Error prediciendo {}: {}".format(target_name, e))
                    predictions[target_name] = self.default_params[target_name]
            
            # Verificar estabilidad basada en ángulos
            stability_score = 1.0 - min(1.0, sensor_data['stability_index'] / 0.5)
            
            if stability_score < self.stability_threshold:
                print("[WARN] Baja estabilidad ({:.2f}), usando parámetros conservadores".format(stability_score))
                # Mezclar con parámetros por defecto
                for target in predictions:
                    predictions[target] = (0.7 * self.default_params[target] + 
                                         0.3 * predictions[target])
            
            # Aplicar suavizado temporal
            if self.prediction_history:
                last_predictions = self.prediction_history[-1]
                for target in predictions:
                    predictions[target] = ((1 - self.adaptation_rate) * last_predictions[target] + 
                                         self.adaptation_rate * predictions[target])
            
            # Guardar en historial
            self.prediction_history.append(predictions.copy())
            if len(self.prediction_history) > 10:
                self.prediction_history.pop(0)
            
            print("[PREDICT] StepHeight:{:.3f}, MaxStepX:{:.3f}, MaxStepY:{:.3f}, MaxStepTheta:{:.3f}, Frequency:{:.3f} (stability:{:.2f})".format(
                predictions['StepHeight'], predictions['MaxStepX'], predictions['MaxStepY'], 
                predictions['MaxStepTheta'], predictions['Frequency'], stability_score))
            
            return predictions
            
        except Exception as e:
            print("[ERROR] Error en predicción: {}".format(e))
            return self.default_params.copy()
    
    def update_gait_parameters(self):
        """Actualizar parámetros de caminata del NAO"""
        if not self.motion or not self.enabled:
            return False
        
        try:
            # Predecir nuevos parámetros
            new_params = self.predict_gait_parameters()
            
            # Nota: Configuración de brazos y parámetros manejada por control externo
            # No aplicamos configuraciones automáticas aquí
            
            # Actualizar parámetros internos
            self.current_params = new_params
            
            return True
            
        except Exception as e:
            print("[ERROR] Error actualizando parámetros: {}".format(e))
            return False
    
    def start_adaptive_walk(self, x=0.02, y=0.0, theta=0.0):
        """Iniciar caminata adaptiva"""
        print("[INFO] Iniciando caminata adaptiva con LightGBM AutoML...")
        
        if not self.motion:
            print("[WARN] Motion proxy no disponible - ejecutando en modo simulación")
            print("[SIMULATION] Simulando caminata con velocidades: x={:.3f}, y={:.3f}, theta={:.3f}".format(x, y, theta))
            
            # Predecir parámetros sin aplicarlos al robot
            initial_params = self.predict_gait_parameters()
            
            print("[SIMULATION] Parámetros de caminata que se aplicarían:")
            for param, value in initial_params.items():
                print("  {}: {:.4f}".format(param, value))
            
            print("[SIMULATION] En un robot real, estos parámetros se aplicarían al ALMotion")
            print("[SIMULATION] Para testing real, conecta a un NAO con NAOqi ejecutándose")
            
            self.enabled = True
            return True
        
        try:
            self.enabled = True
            
            # Predecir parámetros iniciales
            initial_params = self.predict_gait_parameters()
            
            # Configurar y iniciar caminata
            self.motion.moveToward(x, y, theta)
            
            print("[SUCCESS] Caminata adaptiva iniciada con parámetros LightGBM:")
            for param, value in initial_params.items():
                print("  {}: {:.4f}".format(param, value))
            
            return True
            
        except Exception as e:
            print("[ERROR] Error iniciando caminata: {}".format(e))
            return False
    
    def stop_adaptive_walk(self):
        """Detener caminata adaptiva"""
        self.enabled = False
        
        if not self.motion:
            print("[SIMULATION] Simulando parada de caminata")
            print("[INFO] Caminata adaptiva detenida (simulación)")
            return True
        
        try:
            self.motion.stopMove()
            print("[INFO] Caminata adaptiva detenida")
            return True
        except Exception as e:
            print("[ERROR] Error deteniendo caminata: {}".format(e))
            return False
    
    def cleanup(self):
        """Limpiar recursos"""
        print("[INFO] Limpiando recursos AdaptiveWalkLightGBM...")
        
        self.stop_adaptive_walk()
        
        # Cerrar modelos
        if self.scaler:
            self.scaler.close()
        
        for model in self.models.values():
            model.close()
        
        print("[INFO] Recursos liberados")

# Funciones de compatibilidad
def safe_input(prompt):
    """Input compatible con Python 2/3"""
    try:
        return raw_input(prompt)
    except NameError:
        return input(prompt)

# Testing standalone
if __name__ == "__main__":
    print("="*60)
    print("ADAPTIVE WALK LIGHTGBM AUTOML - NAO")
    print("="*60)
    
    # Crear instancia
    adaptive_walk = AdaptiveWalkLightGBM()
    
    if not adaptive_walk.models:
        print("[WARN] No se pudieron cargar modelos LightGBM")
        print("[INFO] El sistema funcionará en modo simulación")
        print("")
        print("Para usar modelos LightGBM:")
        print("1. Copia los archivos *.npz al directorio: models_npz_automl/")
        print("2. Archivos necesarios:")
        print("   - feature_scaler.npz")
        print("   - lightgbm_model_StepHeight.npz")
        print("   - lightgbm_model_MaxStepX.npz") 
        print("   - lightgbm_model_MaxStepY.npz")
        print("   - lightgbm_model_MaxStepTheta.npz")
        print("   - lightgbm_model_Frequency.npz")
        print("3. Reinicia el programa")
        print("")
        
        # Preguntar si continuar sin modelos
        try:
            continuar = safe_input("¿Continuar en modo simulación? (y/n): ").strip().lower()
            if continuar not in ['y', 'yes', 's', 'si']:
                print("[INFO] Programa terminado")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\n[INFO] Programa terminado")
            sys.exit(0)
    
    try:
        print("\nComandos disponibles:")
        print("  'start' - Iniciar caminata adaptiva")
        print("  'stop'  - Detener caminata") 
        print("  'predict' - Mostrar predicción actual")
        print("  'quit'  - Salir")
        
        while True:
            try:
                cmd = safe_input("\n> ").strip().lower()
                
                if cmd == 'start':
                    x = float(safe_input("Velocidad X (default 0.02): ") or "0.02")
                    y = float(safe_input("Velocidad Y (default 0.0): ") or "0.0")  
                    theta = float(safe_input("Velocidad angular (default 0.0): ") or "0.0")
                    adaptive_walk.start_adaptive_walk(x, y, theta)
                    
                elif cmd == 'stop':
                    adaptive_walk.stop_adaptive_walk()
                    
                elif cmd == 'predict':
                    params = adaptive_walk.predict_gait_parameters()
                    print("Predicción actual:")
                    for param, value in params.items():
                        print("  {}: {:.4f}".format(param, value))
                        
                elif cmd == 'quit':
                    break
                    
                else:
                    print("Comando no reconocido")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print("Error: {}".format(e))
    
    finally:
        adaptive_walk.cleanup()
        print("\n[INFO] Programa terminado")
