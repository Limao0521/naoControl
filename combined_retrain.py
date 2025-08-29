#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script temporal para reentrenar usando TODOS los CSV disponibles
"""

import os
import sys
import glob
import pandas as pd
import numpy as np
import joblib
from datetime import datetime

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
except ImportError:
    print("[ERROR] Este script requiere scikit-learn, pandas instalados")
    sys.exit(1)

# Configuración
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_KEYS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

def load_all_csvs():
    """Cargar todos los CSVs de logs y datasets"""
    dfs = []
    
    # Cargar logs adaptativos
    logs_pattern = "robot_scripts/logs/*.csv"
    log_files = glob.glob(logs_pattern)
    print(f"[INFO] Encontrados {len(log_files)} archivos en logs/")
    
    for file_path in log_files:
        try:
            df = pd.read_csv(file_path)
            print(f"  ✓ {os.path.basename(file_path)}: {len(df)} filas")
            if len(df) > 0:
                dfs.append(df)
        except Exception as e:
            print(f"  ✗ Error en {file_path}: {e}")
    
    # Cargar datasets de walks
    walks_pattern = "datasets/walks/*.csv"
    walk_files = glob.glob(walks_pattern)
    print(f"[INFO] Encontrados {len(walk_files)} archivos en datasets/walks/")
    
    for file_path in walk_files:
        try:
            df = pd.read_csv(file_path)
            print(f"  ✓ {os.path.basename(file_path)}: {len(df)} filas")
            if len(df) > 0:
                dfs.append(df)
        except Exception as e:
            print(f"  ✗ Error en {file_path}: {e}")
    
    if not dfs:
        raise ValueError("No se pudieron cargar archivos CSV válidos")
    
    combined_df = pd.concat(dfs, ignore_index=True)
    print(f"[INFO] Datos combinados: {len(combined_df)} filas totales")
    return combined_df

def prepare_data(df):
    """Preparar datos para entrenamiento"""
    # Filtrar filas válidas (stable=1 si existe la columna)
    if 'stable' in df.columns:
        df = df[df['stable'] == 1]
        print(f"[INFO] Filas estables: {len(df)}")
    
    # Verificar que tenemos todas las columnas necesarias
    missing_features = [f for f in FEAT_ORDER if f not in df.columns]
    missing_targets = [t for t in GAIT_KEYS if t not in df.columns]
    
    if missing_features:
        raise ValueError(f"Features faltantes: {missing_features}")
    if missing_targets:
        raise ValueError(f"Targets faltantes: {missing_targets}")
    
    # Extraer features y targets
    X = df[FEAT_ORDER].values
    y = df[GAIT_KEYS].values
    
    # Limpiar NaN e infinitos
    mask = np.isfinite(X).all(axis=1) & np.isfinite(y).all(axis=1)
    X = X[mask]
    y = y[mask]
    
    print(f"[INFO] Filas válidas después de limpieza: {len(X)} de {len(df)}")
    print(f"[INFO] Features shape: {X.shape}")
    print(f"[INFO] Targets: {GAIT_KEYS}")
    
    return X, y

def train_models(X, y, output_dir="models"):
    """Entrenar modelos Random Forest"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Normalizar features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    results = {}
    
    print("[INFO] Entrenando modelos...")
    for i, target_name in enumerate(GAIT_KEYS):
        print(f"[INFO] Entrenando modelo para: {target_name}")
        
        y_target = y[:, i]
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y_target, test_size=0.2, random_state=42
        )
        
        # Entrenar modelo
        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=20,
            random_state=42,
            n_jobs=-1
        )
        rf.fit(X_train, y_train)
        
        # Evaluar
        y_pred = rf.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        print(f"  MSE: {mse:.6f}, MAE: {mae:.6f}, R²: {r2:.4f}")
        
        results[target_name] = {
            'model': rf,
            'mse': mse,
            'mae': mae,
            'r2': r2
        }
    
    # Guardar scaler
    scaler_path = os.path.join(output_dir, "feature_scaler.pkl")
    joblib.dump(scaler, scaler_path)
    print(f"[INFO] Scaler guardado: {scaler_path}")
    
    # Guardar modelos
    for target_name, result in results.items():
        model_path = os.path.join(output_dir, f"randomforest_model_{target_name}.pkl")
        joblib.dump(result['model'], model_path)
        print(f"[INFO] Modelo {target_name} guardado: {model_path}")
    
    # Guardar reporte
    report_path = os.path.join(output_dir, "combined_retrain_report.txt")
    with open(report_path, 'w') as f:
        f.write("Reporte de Reentrenamiento Combinado\n")
        f.write("=" * 50 + "\n")
        f.write(f"Timestamp: {datetime.now()}\n")
        f.write(f"Datos de entrenamiento: {len(X)} filas\n")
        f.write(f"Features: {len(FEAT_ORDER)}\n")
        f.write(f"Targets: {len(GAIT_KEYS)}\n\n")
        
        for target_name, result in results.items():
            f.write(f"{target_name}:\n")
            f.write(f"  MSE: {result['mse']:.6f}\n")
            f.write(f"  MAE: {result['mae']:.6f}\n")
            f.write(f"  R²: {result['r2']:.4f}\n\n")
    
    print(f"[INFO] Reporte guardado: {report_path}")
    
    return results

def main():
    print("[INFO] Iniciando reentrenamiento combinado...")
    
    # Cargar todos los datos
    df = load_all_csvs()
    
    # Preparar datos
    X, y = prepare_data(df)
    
    # Entrenar modelos
    results = train_models(X, y)
    
    print("\n[SUCCESS] Reentrenamiento completado")
    print("Modelos guardados en: models/")
    print("\nResumen de métricas:")
    for target_name, result in results.items():
        print(f"  {target_name}: R² = {result['r2']:.3f}, MAE = {result['mae']:.4f}")

if __name__ == "__main__":
    main()
