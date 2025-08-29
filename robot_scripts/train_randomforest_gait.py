#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
train_randomforest_gait.py — Entrenamiento de modelos Random Forest para parámetros de marcha

Entrena modelos Random Forest independientes para cada parámetro de salida.
Entrena un modelo separado para cada uno de los 5 parámetros de marcha.

Requisitos:
  pip install pandas numpy scikit-learn joblib

Uso (ejemplos):
  python train_randomforest_gait.py --data "datasets/walks/*.csv" --out-dir models/
  python train_randomforest_gait.py --data "sesion1.csv" "sesion2.csv" --test-size 0.2

Salidas:
  - randomforest_model_<param>.pkl: Modelos entrenados (uno por parámetro)
  - feature_scaler.pkl: Escalador de características
  - training_report.txt: Reporte de métricas
"""

import argparse
import glob
import os
import sys
import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

# Orden exacto de features que usa el sistema (20)
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_KEYS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

# Rangos físicos (deben coincidir con adaptive_walk_randomforest.py)
PARAM_RANGES = {
    'StepHeight':   (0.01, 0.05),
    'MaxStepX':     (0.02, 0.08),
    'MaxStepY':     (0.08, 0.20),
    'MaxStepTheta': (0.10, 0.50),
    'Frequency':    (0.50, 1.20),
}

def load_and_prepare_data(csv_paths, verbose=True):
    """
    Carga y prepara datos desde archivos CSV
    
    Returns:
        X: features (20 columnas)
        y_dict: dict con targets normalizados para cada parámetro
        n_samples: número de muestras válidas
    """
    dfs = []
    
    if verbose:
        print("[INFO] Encontrados {} archivos CSV".format(len(csv_paths)))
        print("[INFO] Cargando {} archivos CSV...".format(len(csv_paths)))
    
    for path in csv_paths:
        try:
            df = pd.read_csv(path)
            dfs.append(df)
            if verbose:
                print("  ✓ {}: {} filas".format(path, len(df)))
        except Exception as e:
            print("  ✗ Error en {}: {}".format(path, e))
    
    if not dfs:
        raise RuntimeError("No se pudieron cargar archivos CSV válidos")
    
    # Concatenar todos los DataFrames
    df = pd.concat(dfs, ignore_index=True)
    
    if verbose:
        print("[INFO] Dataset combinado: {} filas".format(len(df)))
    
    # Verificar y rellenar features faltantes
    for col in FEAT_ORDER:
        if col not in df.columns:
            df[col] = 0.0
            if verbose:
                print("  [WARN] Columna '{}' faltante, rellenada con 0.0".format(col))
    
    # Filtrar filas que tengan todos los targets
    mask_valid = np.ones(len(df), dtype=bool)
    for param in GAIT_KEYS:
        if param in df.columns:
            mask_valid &= df[param].notna()
        else:
            print("[ERROR] Parámetro '{}' no encontrado en datos".format(param))
            return None, None, 0
    
    df_clean = df[mask_valid].copy()
    n_valid = len(df_clean)
    
    if verbose:
        print("[INFO] Filas válidas después de filtrado: {}".format(n_valid))
    
    if n_valid == 0:
        raise RuntimeError("No hay filas válidas después del filtrado")
    
    # Normalizar targets (0-1) según rangos físicos
    y_dict = {}
    for param in GAIT_KEYS:
        values = df_clean[param].values
        min_val, max_val = PARAM_RANGES[param]
        
        # Normalizar a [0,1]
        values_norm = (values - min_val) / (max_val - min_val)
        values_norm = np.clip(values_norm, 0.0, 1.0)
        
        y_dict[param] = values_norm
        
        if verbose:
            print("  {}: min={:.4f}, max={:.4f}, norm_min={:.4f}, norm_max={:.4f}".format(
                param, values.min(), values.max(), values_norm.min(), values_norm.max()))
    
    # Extraer features en orden correcto
    X = df_clean[FEAT_ORDER].values.astype(np.float32)
    
    if verbose:
        print("[INFO] Dataset preparado: {} muestras, {} features".format(n_valid, X.shape[1]))
    
    return X, y_dict, n_valid

def train_randomforest_models(X, y_dict, test_size=0.2, optimize=False, n_jobs=-1, random_state=42):
    """
    Entrena modelos Random Forest para cada parámetro
    
    Returns:
        models: dict con modelos entrenados
        metrics: dict con métricas de evaluación
        scaler: StandardScaler ajustado
    """
    print("[INFO] Entrenando modelos Random Forest...")
    
    # Split train/test
    X_train, X_test, indices_train, indices_test = train_test_split(
        X, np.arange(len(X)), test_size=test_size, random_state=random_state
    )
    
    print("  Train: {} muestras".format(len(X_train)))
    print("  Test:  {} muestras".format(len(X_test)))
    print("")
    
    # Escalar features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    models = {}
    metrics = {}
    
    # Parámetros base para Random Forest
    base_params = {
        'n_estimators': 100,
        'max_depth': 15,
        'min_samples_split': 10,
        'min_samples_leaf': 5,
        'random_state': random_state,
        'n_jobs': n_jobs
    }
    
    # Parámetros para optimización
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [10, 15, 20, None],
        'min_samples_split': [5, 10, 20],
        'min_samples_leaf': [2, 5, 10]
    }
    
    for param in GAIT_KEYS:
        print("[INFO] Entrenando modelo para {}...".format(param))
        
        # Preparar targets
        y_train = y_dict[param][indices_train]
        y_test = y_dict[param][indices_test]
        
        if optimize:
            # Búsqueda de hiperparámetros
            rf = RandomForestRegressor(random_state=random_state, n_jobs=n_jobs)
            grid_search = GridSearchCV(
                rf, param_grid, cv=3, scoring='neg_mean_squared_error',
                n_jobs=1, verbose=0  # n_jobs=1 para evitar conflictos con RandomForest n_jobs
            )
            grid_search.fit(X_train_scaled, y_train)
            model = grid_search.best_estimator_
            print("  Mejores parámetros: {}".format(grid_search.best_params_))
        else:
            # Usar parámetros base
            model = RandomForestRegressor(**base_params)
            model.fit(X_train_scaled, y_train)
        
        # Evaluar
        y_train_pred = model.predict(X_train_scaled)
        y_test_pred = model.predict(X_test_scaled)
        
        # Métricas
        train_mse = mean_squared_error(y_train, y_train_pred)
        train_mae = mean_absolute_error(y_train, y_train_pred)
        train_r2 = r2_score(y_train, y_train_pred)
        
        test_mse = mean_squared_error(y_test, y_test_pred)
        test_mae = mean_absolute_error(y_test, y_test_pred)
        test_r2 = r2_score(y_test, y_test_pred)
        
        print("  Train - MSE: {:.6f}, MAE: {:.6f}, R²: {:.4f}".format(train_mse, train_mae, train_r2))
        print("  Test  - MSE: {:.6f}, MAE: {:.6f}, R²: {:.4f}".format(test_mse, test_mae, test_r2))
        print("")
        
        models[param] = model
        metrics[param] = {
            'train_mse': train_mse, 'train_mae': train_mae, 'train_r2': train_r2,
            'test_mse': test_mse, 'test_mae': test_mae, 'test_r2': test_r2
        }
    
    return models, metrics, scaler

def save_models(models, scaler, out_dir):
    """Guardar modelos Random Forest y el scaler en out_dir"""
    import tempfile
    
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    
    saved_paths = {}
    
    # Guardar cada modelo por separado
    for name, model in models.items():
        model_path = os.path.join(out_dir, "randomforest_model_{}.pkl".format(name))
        try:
            joblib.dump(model, model_path)
            saved_paths[name] = model_path
            print("[INFO] Modelo {} guardado en: {}".format(name, model_path))
        except Exception as e:
            print("[ERROR] Error guardando modelo {}: {}".format(name, e))
            raise
    
    # Guardar scaler
    scaler_path = os.path.join(out_dir, "feature_scaler.pkl")
    try:
        joblib.dump(scaler, scaler_path)
        print("[INFO] Scaler guardado en: {}".format(scaler_path))
    except Exception as e:
        print("[ERROR] Error guardando scaler: {}".format(e))
        raise
    
    return saved_paths, scaler_path

def save_report(metrics, models, out_dir):
    """Guardar reporte de entrenamiento"""
    report_path = os.path.join(out_dir, "training_report.txt")
    
    with open(report_path, 'w') as f:
        f.write("Random Forest Gait Training Report\n")
        f.write("==================================\n")
        f.write("Timestamp: {}\n".format(datetime.now().isoformat()))
        f.write("Model Type: Random Forest Regressor\n\n")
        
        for param in GAIT_KEYS:
            f.write("Parameter: {}\n".format(param))
            f.write("-" * 30 + "\n")
            
            m = metrics[param]
            f.write("Train - MSE: {:.6f}, MAE: {:.6f}, R²: {:.4f}\n".format(
                m['train_mse'], m['train_mae'], m['train_r2']))
            f.write("Test  - MSE: {:.6f}, MAE: {:.6f}, R²: {:.4f}\n".format(
                m['test_mse'], m['test_mae'], m['test_r2']))
            
            # Información del modelo
            model = models[param]
            f.write("Model params: n_estimators={}, max_depth={}\n".format(
                model.n_estimators, model.max_depth))
            f.write("\n")
    
    print("[INFO] Reporte guardado en: {}".format(report_path))

def main():
    parser = argparse.ArgumentParser(description='Entrenar modelos Random Forest para marcha adaptativa')
    parser.add_argument('--data', nargs='+', required=True,
                        help='Archivos CSV con datos de entrenamiento (soporta wildcards)')
    parser.add_argument('--out-dir', default='models',
                        help='Directorio de salida para modelos (default: models)')
    parser.add_argument('--test-size', type=float, default=0.2,
                        help='Proporción para test (default: 0.2)')
    parser.add_argument('--optimize', action='store_true',
                        help='Ejecutar búsqueda de hiperparámetros')
    parser.add_argument('--n-jobs', type=int, default=-1,
                        help='Número de trabajos paralelos (default: -1)')
    parser.add_argument('--random-state', type=int, default=42,
                        help='Semilla aleatoria (default: 42)')
    
    args = parser.parse_args()
    
    # Expandir wildcards
    csv_files = []
    for pattern in args.data:
        matches = glob.glob(pattern)
        if matches:
            csv_files.extend(matches)
        else:
            # Si no hay matches, asumir que es un archivo literal
            csv_files.append(pattern)
    
    if not csv_files:
        print("[ERROR] No se encontraron archivos CSV")
        return 1
    
    try:
        # Cargar datos
        X, y_dict, n_samples = load_and_prepare_data(csv_files)
        
        if X is None:
            return 1
        
        # Entrenar modelos
        models, metrics, scaler = train_randomforest_models(
            X, y_dict,
            test_size=args.test_size,
            optimize=args.optimize,
            n_jobs=args.n_jobs,
            random_state=args.random_state
        )
        
        # Guardar modelos
        model_paths, scaler_path = save_models(models, scaler, args.out_dir)
        
        # Guardar reporte
        save_report(metrics, models, args.out_dir)
        
        print("[SUCCESS] Entrenamiento completado")
        print("Modelos guardados en: {}".format(args.out_dir))
        
        return 0
        
    except Exception as e:
        print("[ERROR] Error durante entrenamiento: {}".format(e))
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
