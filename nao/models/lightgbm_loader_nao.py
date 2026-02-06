#!/usr/bin/env python
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
