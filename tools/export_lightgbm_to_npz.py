#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
export_lightgbm_to_npz.py - Exportar modelos LightGBM a formato NPZ para NAO

Este script convierte modelos LightGBM optimizados con AutoML a formato NPZ
que puede ser usado en el NAO sin dependencias de sklearn/lightgbm.

Uso:
    python export_lightgbm_to_npz.py --models-dir models_automl --out-dir models_npz_automl
"""

from __future__ import print_function
import argparse
import os
import sys
import glob
import joblib
import numpy as np
import json
from datetime import datetime

try:
    import lightgbm as lgb
    print("[INFO] LightGBM disponible para exportación")
except ImportError:
    print("[ERROR] LightGBM no disponible")
    sys.exit(1)

# Configuración
GAIT_TARGETS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

class LightGBMToNumpy:
    """Convertir modelo LightGBM a predicción NumPy pura"""
    
    def __init__(self, lgb_model):
        self.lgb_model = lgb_model
        self.n_features = lgb_model.num_feature()
        self.n_trees = lgb_model.num_trees()
        
        # Extraer estructura de árboles
        self.trees = []
        for i in range(self.n_trees):
            tree_dict = lgb_model.dump_model()['tree_info'][i]
            self.trees.append(self._parse_tree(tree_dict['tree_structure']))
    
    def _parse_tree(self, tree_dict):
        """Parsear estructura de árbol LightGBM"""
        if 'leaf_value' in tree_dict:
            # Nodo hoja
            return {
                'is_leaf': True,
                'value': float(tree_dict['leaf_value'])
            }
        else:
            # Nodo interno
            return {
                'is_leaf': False,
                'feature_idx': int(tree_dict['split_feature']),
                'threshold': float(tree_dict['threshold']),
                'left': self._parse_tree(tree_dict['left_child']),
                'right': self._parse_tree(tree_dict['right_child'])
            }
    
    def predict_single(self, x):
        """Predecir un único sample"""
        result = 0.0
        for tree in self.trees:
            result += self._traverse_tree(tree, x)
        return result
    
    def _traverse_tree(self, tree, x):
        """Atravesar un árbol"""
        if tree['is_leaf']:
            return tree['value']
        
        if x[tree['feature_idx']] <= tree['threshold']:
            return self._traverse_tree(tree['left'], x)
        else:
            return self._traverse_tree(tree['right'], x)
    
    def predict(self, X):
        """Predecir múltiples samples"""
        predictions = []
        for i in range(len(X)):
            pred = self.predict_single(X[i])
            predictions.append(pred)
        return np.array(predictions)
    
    def to_npz_format(self):
        """Convertir a formato que pueda guardarse en NPZ"""
        # Serializar árboles a arrays
        tree_data = []
        for tree in self.trees:
            serialized = self._serialize_tree(tree)
            tree_data.append(serialized)
        
        return {
            'n_features': self.n_features,
            'n_trees': self.n_trees,
            'trees': tree_data
        }
    
    def _serialize_tree(self, tree):
        """Serializar árbol a lista de números"""
        if tree['is_leaf']:
            return [1, tree['value']]  # [1, value] para hoja
        else:
            left_serial = self._serialize_tree(tree['left'])
            right_serial = self._serialize_tree(tree['right'])
            
            # [0, feature_idx, threshold, left_size, ...left_data, ...right_data]
            return ([0, tree['feature_idx'], tree['threshold'], len(left_serial)] + 
                   left_serial + right_serial)

def export_lightgbm_model(model_path, target_name, output_dir):
    """Exportar un modelo LightGBM a NPZ"""
    print(f"[INFO] Exportando {target_name}...")
    
    # Cargar modelo
    model = joblib.load(model_path)
    
    if not hasattr(model, 'booster_'):
        print(f"[ERROR] {model_path} no es un modelo LightGBM válido")
        return False
    
    # Convertir a NumPy
    converter = LightGBMToNumpy(model.booster_)
    
    # Preparar datos para NPZ
    npz_data = converter.to_npz_format()
    
    # Guardar como NPZ
    output_path = os.path.join(output_dir, f"lightgbm_model_{target_name}.npz")
    
    # Convertir trees a formato que NPZ pueda manejar
    trees_array = []
    trees_lengths = []
    
    for tree_data in npz_data['trees']:
        trees_array.extend(tree_data)
        trees_lengths.append(len(tree_data))
    
    np.savez_compressed(output_path,
                       n_features=npz_data['n_features'],
                       n_trees=npz_data['n_trees'],
                       trees_data=np.array(trees_array, dtype=np.float64),
                       trees_lengths=np.array(trees_lengths, dtype=np.int32))
    
    print(f"  ✓ Guardado: {output_path}")
    
    # Verificar cargando
    try:
        loaded = np.load(output_path)
        print(f"  ✓ Verificación: {loaded['n_trees']} árboles, {loaded['n_features']} features")
        loaded.close()
        return True
    except Exception as e:
        print(f"  ✗ Error verificando: {e}")
        return False

def export_scaler(scaler_path, output_dir):
    """Exportar scaler a NPZ"""
    print("[INFO] Exportando feature scaler...")
    
    try:
        scaler = joblib.load(scaler_path)
        
        # Determinar tipo de scaler y extraer parámetros
        if hasattr(scaler, 'mean_') and hasattr(scaler, 'scale_'):
            # StandardScaler
            scaler_type = "StandardScaler"
            params = {
                'mean': scaler.mean_,
                'scale': scaler.scale_
            }
        elif hasattr(scaler, 'min_') and hasattr(scaler, 'scale_'):
            # MinMaxScaler
            scaler_type = "MinMaxScaler"
            params = {
                'min': scaler.min_,
                'scale': scaler.scale_
            }
        else:
            # Scaler dummy o desconocido
            print("[WARN] Scaler desconocido, creando scaler identidad")
            scaler_type = "IdentityScaler"
            # Asumir 27 features como en el script anterior
            n_features = 27
            params = {
                'mean': np.zeros(n_features),
                'scale': np.ones(n_features)
            }
        
        # Guardar
        output_path = os.path.join(output_dir, "feature_scaler.npz")
        np.savez_compressed(output_path,
                           scaler_type=scaler_type,
                           **params)
        
        print(f"  ✓ Scaler guardado: {output_path} ({scaler_type})")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error exportando scaler: {e}")
        
        # Crear scaler identidad como fallback
        print("[INFO] Creando scaler identidad como fallback...")
        n_features = 27
        output_path = os.path.join(output_dir, "feature_scaler.npz")
        np.savez_compressed(output_path,
                           scaler_type="IdentityScaler",
                           mean=np.zeros(n_features),
                           scale=np.ones(n_features))
        print(f"  ✓ Scaler identidad guardado: {output_path}")
        return True

def create_nao_loader_script(output_dir):
    """Crear script para cargar modelos LightGBM en NAO"""
    
    script_content = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lightgbm_loader_nao.py - Cargar y usar modelos LightGBM en NAO

Script para cargar modelos LightGBM exportados a NPZ y hacer predicciones
en el NAO sin dependencias externas.
"""

import numpy as np
import os

class LightGBMNAOPredictor:
    """Predictor LightGBM para NAO usando solo NumPy"""
    
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
    """Scaler de features para NAO"""
    
    def __init__(self, scaler_path):
        self.scaler_data = np.load(scaler_path)
        self.scaler_type = str(self.scaler_data['scaler_type'])
        self.mean = self.scaler_data['mean']
        self.scale = self.scaler_data['scale']
    
    def transform(self, X):
        """Transformar features"""
        if self.scaler_type == "StandardScaler":
            return (X - self.mean) / self.scale
        elif self.scaler_type == "MinMaxScaler":
            return X * self.scale + self.mean  # Formato MinMax puede variar
        else:  # IdentityScaler
            return X
    
    def close(self):
        """Cerrar archivo NPZ"""
        self.scaler_data.close()

# Ejemplo de uso:
if __name__ == "__main__":
    # Cargar modelos
    models_dir = "."  # Directorio con archivos NPZ
    
    scaler = FeatureScalerNAO(os.path.join(models_dir, "feature_scaler.npz"))
    
    models = {}
    targets = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']
    
    for target in targets:
        model_path = os.path.join(models_dir, f"lightgbm_model_{target}.npz")
        if os.path.exists(model_path):
            models[target] = LightGBMNAOPredictor(model_path)
            print(f"Modelo {target} cargado: {models[target].n_trees} arboles")
    
    # Ejemplo de predicción
    import random
    sample_features = [random.random() for _ in range(27)]  # Features dummy
    
    # Escalar
    scaled_features = scaler.transform(np.array(sample_features))
    
    # Predecir
    predictions = {}
    for target, model in models.items():
        pred = model.predict_single(scaled_features)
        predictions[target] = pred
        print(f"{target}: {pred:.6f}")
    
    # Cerrar
    scaler.close()
    for model in models.values():
        model.close()
'''
    
    script_path = os.path.join(output_dir, "lightgbm_loader_nao.py")
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    print(f"[INFO] Script NAO creado: {script_path}")

def main():
    parser = argparse.ArgumentParser(description="Exportar modelos LightGBM a NPZ")
    parser.add_argument("--models-dir", required=True,
                       help="Directorio con modelos AutoML")
    parser.add_argument("--out-dir", required=True,
                       help="Directorio de salida NPZ")
    
    args = parser.parse_args()
    
    print("[INFO] Exportando modelos LightGBM AutoML a formato NPZ...")
    
    # Crear directorio salida
    os.makedirs(args.out_dir, exist_ok=True)
    
    exported_models = 0
    
    # Exportar scaler
    scaler_path = os.path.join(args.models_dir, "feature_scaler.pkl")
    if os.path.exists(scaler_path):
        export_scaler(scaler_path, args.out_dir)
    else:
        print("[WARN] No se encontró feature_scaler.pkl")
    
    # Exportar modelos
    for target in GAIT_TARGETS:
        model_path = os.path.join(args.models_dir, f"automl_model_{target}.pkl")
        
        if os.path.exists(model_path):
            success = export_lightgbm_model(model_path, target, args.out_dir)
            if success:
                exported_models += 1
        else:
            print(f"[WARN] No encontrado: {model_path}")
    
    # Crear script para NAO
    create_nao_loader_script(args.out_dir)
    
    print(f"\\n[SUCCESS] Exportación completada:")
    print(f"  Modelos exportados: {exported_models}/{len(GAIT_TARGETS)}")
    print(f"  Archivos en: {args.out_dir}/")
    print(f"\\nArchivos generados:")
    
    for file in sorted(os.listdir(args.out_dir)):
        file_path = os.path.join(args.out_dir, file)
        size_kb = os.path.getsize(file_path) / 1024
        print(f"  {file} ({size_kb:.1f} KB)")
    
    print(f"\\nPara usar en NAO:")
    print(f"1. Copiar {args.out_dir}/ al NAO")
    print(f"2. Usar lightgbm_loader_nao.py para cargar modelos")
    print(f"3. Integrar en adaptive_walk_randomforest.py")

if __name__ == "__main__":
    main()
