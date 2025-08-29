#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
adaptive_walk_lightgbm_nao.py - Adaptive Walk con modelos LightGBM AutoML

Versión actualizada de adaptive_walk_randomforest.py que usa los modelos
LightGBM optimizados con AutoML para mejor rendimiento.

INSTRUCCIONES DE DEPLOYMENT:
1. Copiar models_npz_automl/ al NAO en el mismo directorio que este script
2. Reemplazar adaptive_walk_randomforest.py con este archivo
3. Actualizar control_server.py para usar esta nueva versión
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
FEATURE_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z', 
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_TARGETS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

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
        
        print(f"[INFO] Modelo LightGBM cargado: {self.n_trees} árboles, {self.n_features} features")
    
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
        print(f"[INFO] Scaler cargado: {self.scaler_type}")
    
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
    """Sistema de caminata adaptiva con modelos LightGBM AutoML y modo Golden Parameters"""
    
    def __init__(self, models_dir="models_npz_automl", golden_csv_path="gait_params_log.csv"):
        self.models_dir = models_dir
        self.models = {}
        self.scaler = None
        self.motion = None
        self.memory = None
        self.enabled = False
        
        # 🌟 NUEVO: Configuración de modo híbrido
        self.mode = "training"  # "training" o "golden"
        self.golden_csv_path = golden_csv_path
        self.golden_params = None
        self.last_csv_load = 0
        self.csv_reload_interval = 30  # segundos
        
        # Configuración de caminata
        self.default_params = {
            'StepHeight': 0.02,
            'MaxStepX': 0.04, 
            'MaxStepY': 0.14,
            'MaxStepTheta': 0.3,
            'Frequency': 1.0
        }
        
        self.current_params = self.default_params.copy()
        self.prediction_history = []
        self.stability_threshold = 0.8
        self.adaptation_rate = 0.1
        
        # Inicializar NAO proxies
        self._init_nao_proxies()
        
        # Cargar modelos AutoML
        self._load_automl_models()
        
        # 🌟 NUEVO: Cargar parámetros golden si están disponibles
        self._load_golden_parameters()
    
    def _init_nao_proxies(self):
        """Inicializar proxies NAO"""
        if ALProxy is None:
            print("[WARN] Modo simulación - proxies no disponibles")
            return
        
        try:
            self.motion = ALProxy("ALMotion")
            self.memory = ALProxy("ALMemory")
            print("[INFO] Proxies NAO inicializados")
        except Exception as e:
            print(f"[ERROR] Error inicializando proxies: {e}")
    
    def _load_automl_models(self):
        """Cargar modelos LightGBM AutoML"""
        print(f"[INFO] Cargando modelos desde {self.models_dir}/")
        
        try:
            # Cargar scaler
            scaler_path = os.path.join(self.models_dir, "feature_scaler.npz")
            if os.path.exists(scaler_path):
                self.scaler = FeatureScalerNAO(scaler_path)
            else:
                print(f"[ERROR] Scaler no encontrado: {scaler_path}")
                return False
            
            # Cargar modelos por target
            for target in GAIT_TARGETS:
                model_path = os.path.join(self.models_dir, f"lightgbm_model_{target}.npz")
                
                if os.path.exists(model_path):
                    self.models[target] = LightGBMNAOPredictor(model_path)
                    print(f"[INFO] Modelo {target} cargado exitosamente")
                else:
                    print(f"[ERROR] Modelo no encontrado: {model_path}")
                    return False
            
            print(f"[SUCCESS] {len(self.models)} modelos LightGBM cargados")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error cargando modelos: {e}")
            return False
    
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
                    key = f"{foot}_{sensor}"
                    foot_name = "LFoot" if foot == 'lfoot' else "RFoot"
                    sensor_name = {"fl": "FrontLeft", "fr": "FrontRight", 
                                 "rl": "RearLeft", "rr": "RearRight"}[sensor]
                    
                    fsr_path = f"Device/SubDeviceList/{foot_name}/FSR/{sensor_name}/Sensor/Value"
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
            print(f"[ERROR] Error leyendo sensores: {e}")
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
    
    def predict_gait_parameters(self):
        """Predecir parámetros de caminata usando LightGBM AutoML"""
        if not self.models or not self.scaler:
            print("[WARN] Modelos no disponibles, usando parámetros por defecto")
            return self.default_params.copy()
        
        try:
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
                    print(f"[ERROR] Error prediciendo {target_name}: {e}")
                    predictions[target_name] = self.default_params[target_name]
            
            # Verificar estabilidad basada en ángulos
            stability_score = 1.0 - min(1.0, sensor_data['stability_index'] / 0.5)
            
            if stability_score < self.stability_threshold:
                print(f"[WARN] Baja estabilidad ({stability_score:.2f}), usando parámetros conservadores")
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
            
            print(f"[PREDICT] StepHeight:{predictions['StepHeight']:.3f}, " +
                  f"MaxStepX:{predictions['MaxStepX']:.3f}, " +
                  f"MaxStepY:{predictions['MaxStepY']:.3f}, " +
                  f"MaxStepTheta:{predictions['MaxStepTheta']:.3f}, " +
                  f"Frequency:{predictions['Frequency']:.3f} (stability:{stability_score:.2f})")
            
            return predictions
            
        except Exception as e:
            print(f"[ERROR] Error en predicción: {e}")
            return self.default_params.copy()
    
    def update_gait_parameters(self):
        """Actualizar parámetros de caminata del NAO"""
        if not self.motion or not self.enabled:
            return False
        
        try:
            # Predecir nuevos parámetros
            new_params = self.predict_gait_parameters()
            
            # Aplicar al motion proxy
            self.motion.setWalkArmsConfig(0.06, 0.06, 0.06, 0.06)
            
            # Configurar parámetros de caminata
            self.motion.post.setMoveArmsEnabled(False, False)
            
            # Actualizar parámetros
            self.current_params = new_params
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Error actualizando parámetros: {e}")
            return False
    
    def start_adaptive_walk(self, x=0.02, y=0.0, theta=0.0):
        """Iniciar caminata adaptiva"""
        if not self.motion:
            print("[ERROR] Motion proxy no disponible")
            return False
        
        try:
            print("[INFO] Iniciando caminata adaptiva con LightGBM AutoML...")
            self.enabled = True
            
            # Predecir parámetros iniciales
            initial_params = self.predict_gait_parameters()
            
            # Configurar y iniciar caminata
            self.motion.moveToward(x, y, theta)
            
            print(f"[SUCCESS] Caminata adaptiva iniciada con parámetros LightGBM:")
            for param, value in initial_params.items():
                print(f"  {param}: {value:.4f}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Error iniciando caminata: {e}")
            return False
    
    def stop_adaptive_walk(self):
        """Detener caminata adaptiva"""
        self.enabled = False
        
        if self.motion:
            try:
                self.motion.stopMove()
                print("[INFO] Caminata adaptiva detenida")
                return True
            except:
                pass
        
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
        print("[ERROR] No se pudieron cargar modelos LightGBM")
        sys.exit(1)
    
    try:
        print("\\nComandos disponibles:")
        print("  'start' - Iniciar caminata adaptiva")
        print("  'stop'  - Detener caminata") 
        print("  'predict' - Mostrar predicción actual")
        print("  'quit'  - Salir")
        
        while True:
            try:
                cmd = safe_input("\\n> ").strip().lower()
                
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
                        print(f"  {param}: {value:.4f}")
                        
                elif cmd == 'quit':
                    break
                    
                else:
                    print("Comando no reconocido")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
    
    finally:
        adaptive_walk.cleanup()
        print("\\n[INFO] Programa terminado")
