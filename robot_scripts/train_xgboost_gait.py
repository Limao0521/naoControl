#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_xgboost_gait.py — Entrenamiento de modelos XGBoost para parámetros de marcha

Entrena modelos XGBoost independientes para cada parámetro de salida.
Entrena un modelo separado para cada uno de los 5 parámetros de marcha.

Requisitos:
  pip install xgboost pandas numpy scikit-learn

Uso (ejemplos):
  python3 train_xgboost_gait.py --data "/home/user/datasets/walks/*.csv" --out-dir models/
  python3 train_xgboost_gait.py --data "/ruta/sesion1.csv" "/ruta/sesion2.csv" --test-size 0.2

Salidas:
  - xgboost_model.json: Modelos entrenados (uno por parámetro)
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
import xgboost as xgb
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

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

# Rangos físicos (deben coincidir con adaptive_walk_xgboost.py)
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
        print(f"[INFO] Cargando {len(csv_paths)} archivos CSV...")
    
    for path in csv_paths:
        try:
            df = pd.read_csv(path)
            dfs.append(df)
            if verbose:
                print(f"  ✓ {path}: {len(df)} filas")
        except Exception as e:
            print(f"  ✗ Error en {path}: {e}")
    
    if not dfs:
        raise RuntimeError("No se pudieron cargar archivos CSV válidos")
    
    # Concatenar todos los DataFrames
    df = pd.concat(dfs, ignore_index=True)
    
    if verbose:
        print(f"[INFO] Dataset combinado: {len(df)} filas")
    
    # Verificar y rellenar features faltantes
    for col in FEAT_ORDER:
        if col not in df.columns:
            df[col] = 0.0
            if verbose:
                print(f"  [WARN] Columna '{col}' faltante, rellenada con 0.0")
    
    # Filtrar filas que tengan todos los targets
    mask_valid = np.ones(len(df), dtype=bool)
    for param in GAIT_KEYS:
        if param in df.columns:
            mask_valid &= df[param].notna()
        else:
            mask_valid = np.zeros(len(df), dtype=bool)
            print(f"  [ERROR] Columna target '{param}' no encontrada")
            break
    
    df_clean = df.loc[mask_valid].reset_index(drop=True)
    
    if len(df_clean) == 0:
        raise RuntimeError("No hay filas con todos los targets válidos")
    
    if verbose:
        print(f"[INFO] Filas válidas después de filtrado: {len(df_clean)}")
    
    # Extraer features (X)
    X = df_clean[FEAT_ORDER].astype(np.float32).values
    
    # Extraer y normalizar targets (y)
    y_dict = {}
    for param in GAIT_KEYS:
        y_raw = df_clean[param].astype(np.float32).values
        lo, hi = PARAM_RANGES[param]
        
        # Normalizar a [0,1]
        y_norm = np.clip((y_raw - lo) / (hi - lo), 0.0, 1.0)
        y_dict[param] = y_norm
        
        if verbose:
            print(f"  {param}: min={y_raw.min():.4f}, max={y_raw.max():.4f}, "
                  f"norm_min={y_norm.min():.4f}, norm_max={y_norm.max():.4f}")
    
    return X, y_dict, len(df_clean)

def optimize_hyperparameters(X_train, y_train, param_name, n_jobs=1):
    """
    Optimización de hiperparámetros usando GridSearchCV
    """
    print(f"[INFO] Optimizando hiperparámetros para {param_name}...")
    
    # Espacio de búsqueda más conservador para evitar overfitting
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [3, 4, 6],
        'learning_rate': [0.05, 0.1, 0.2],
        'subsample': [0.8, 0.9, 1.0],
        'colsample_bytree': [0.8, 0.9, 1.0],
        'reg_alpha': [0, 0.1, 0.5],
        'reg_lambda': [1, 1.5, 2]
    }
    
    # Modelo base
    xgb_model = xgb.XGBRegressor(
        objective='reg:squarederror',
        random_state=42,
        n_jobs=1  # Para evitar problemas en algunos sistemas
    )
    
    # GridSearch con validación cruzada
    grid_search = GridSearchCV(
        estimator=xgb_model,
        param_grid=param_grid,
        cv=3,  # 3-fold CV para balance entre tiempo y validación
        scoring='neg_mean_squared_error',
        n_jobs=n_jobs,
        verbose=0
    )
    
    grid_search.fit(X_train, y_train)
    
    print(f"  Mejores parámetros: {grid_search.best_params_}")
    print(f"  Mejor score CV: {-grid_search.best_score_:.6f}")
    
    return grid_search.best_estimator_

def train_models(X, y_dict, test_size=0.2, optimize=True, random_state=42, n_jobs=1):
    """
    Entrena modelos XGBoost independientes para cada parámetro
    
    Returns:
        models: dict con modelos entrenados
        scaler: StandardScaler ajustado
        metrics: dict con métricas de evaluación
    """
    print(f"[INFO] Entrenando modelos XGBoost...")
    
    # División train/test
    X_train, X_test, indices_train, indices_test = train_test_split(
        X, np.arange(len(X)), test_size=test_size, random_state=random_state
    )
    
    # Escalado de features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print(f"  Train: {len(X_train)} muestras")
    print(f"  Test:  {len(X_test)} muestras")
    
    models = {}
    metrics = {}
    
    for param in GAIT_KEYS:
        print(f"\n[INFO] Entrenando modelo para {param}...")
        
        y_train = y_dict[param][indices_train]
        y_test = y_dict[param][indices_test]
        
        if optimize:
            # Optimización de hiperparámetros
            model = optimize_hyperparameters(X_train_scaled, y_train, param, n_jobs)
        else:
            # Parámetros por defecto conservadores
            model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                subsample=0.9,
                colsample_bytree=0.9,
                reg_alpha=0.1,
                reg_lambda=1.5,
                objective='reg:squarederror',
                random_state=random_state,
                n_jobs=1
            )
            model.fit(X_train_scaled, y_train)
        
        # Evaluación
        y_pred_train = model.predict(X_train_scaled)
        y_pred_test = model.predict(X_test_scaled)
        
        # Métricas
        train_mse = mean_squared_error(y_train, y_pred_train)
        test_mse = mean_squared_error(y_test, y_pred_test)
        train_mae = mean_absolute_error(y_train, y_pred_train)
        test_mae = mean_absolute_error(y_test, y_pred_test)
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)
        
        metrics[param] = {
            'train_mse': train_mse,
            'test_mse': test_mse,
            'train_mae': train_mae,
            'test_mae': test_mae,
            'train_r2': train_r2,
            'test_r2': test_r2,
            'n_train': len(y_train),
            'n_test': len(y_test)
        }
        
        models[param] = model
        
        print(f"  Train - MSE: {train_mse:.6f}, MAE: {train_mae:.6f}, R²: {train_r2:.4f}")
        print(f"  Test  - MSE: {test_mse:.6f}, MAE: {test_mae:.6f}, R²: {test_r2:.4f}")
    
    return models, scaler, metrics

def save_models(models, scaler, out_dir, model_filename="xgboost_model.json", 
                scaler_filename="feature_scaler.pkl"):
    """
    Guarda modelos y scaler en archivos
    """
    os.makedirs(out_dir, exist_ok=True)
    
    # Guardar modelos como JSON
    model_path = os.path.join(out_dir, model_filename)
    models_data = {}
    
    for param, model in models.items():
        # Guardar modelo individual como string JSON
        temp_path = f"/tmp/temp_model_{param}.json"
        model.save_model(temp_path)
        
        with open(temp_path, 'r') as f:
            models_data[param] = temp_path  # Guardar ruta temporal
        
        # Limpiar archivo temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    # Guardar rutas de modelos (para cargar después)
    model_info = {
        'models': {},
        'param_ranges': PARAM_RANGES,
        'feature_order': FEAT_ORDER,
        'gait_keys': GAIT_KEYS,
        'created_at': datetime.now().isoformat()
    }
    
    # Guardar cada modelo individualmente
    for param, model in models.items():
        param_model_path = os.path.join(out_dir, f"model_{param}.json")
        model.save_model(param_model_path)
        model_info['models'][param] = param_model_path
    
    with open(model_path, 'w') as f:
        json.dump(model_info, f, indent=2)
    
    # Guardar scaler
    scaler_path = os.path.join(out_dir, scaler_filename)
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    
    print(f"[OK] Modelos guardados en: {model_path}")
    print(f"[OK] Scaler guardado en: {scaler_path}")
    
    return model_path, scaler_path

def generate_report(metrics, out_dir, report_filename="training_report.txt"):
    """
    Genera reporte de entrenamiento
    """
    report_path = os.path.join(out_dir, report_filename)
    
    with open(report_path, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("REPORTE DE ENTRENAMIENTO XGBOOST\n")
        f.write("=" * 60 + "\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Features: {len(FEAT_ORDER)}\n")
        f.write(f"Parámetros objetivo: {len(GAIT_KEYS)}\n\n")
        
        # Resumen por parámetro
        for param in GAIT_KEYS:
            if param in metrics:
                m = metrics[param]
                f.write(f"Parámetro: {param}\n")
                f.write("-" * 30 + "\n")
                f.write(f"  Muestras entrenamiento: {m['n_train']}\n")
                f.write(f"  Muestras prueba:        {m['n_test']}\n")
                f.write(f"  Train MSE:              {m['train_mse']:.6f}\n")
                f.write(f"  Test MSE:               {m['test_mse']:.6f}\n")
                f.write(f"  Train MAE:              {m['train_mae']:.6f}\n")
                f.write(f"  Test MAE:               {m['test_mae']:.6f}\n")
                f.write(f"  Train R²:               {m['train_r2']:.4f}\n")
                f.write(f"  Test R²:                {m['test_r2']:.4f}\n")
                f.write(f"  Overfitting ratio:      {m['test_mse']/m['train_mse']:.2f}\n")
                f.write("\\n")
        
        # Resumen general
        avg_test_r2 = np.mean([metrics[p]['test_r2'] for p in GAIT_KEYS if p in metrics])
        avg_test_mae = np.mean([metrics[p]['test_mae'] for p in GAIT_KEYS if p in metrics])
        
        f.write("RESUMEN GENERAL\n")
        f.write("-" * 30 + "\n")
        f.write(f"R² promedio (test):     {avg_test_r2:.4f}\n")
        f.write(f"MAE promedio (test):    {avg_test_mae:.6f}\n")
        
        # Calidad del modelo
        if avg_test_r2 > 0.8:
            quality = "EXCELENTE"
        elif avg_test_r2 > 0.6:
            quality = "BUENA"
        elif avg_test_r2 > 0.4:
            quality = "REGULAR"
        else:
            quality = "POBRE"
        
        f.write(f"Calidad estimada:       {quality}\n")
    
    print(f"[OK] Reporte guardado en: {report_path}")
    return report_path

def main():
    parser = argparse.ArgumentParser(description="Entrenamiento de modelos XGBoost para parámetros de marcha")
    parser.add_argument("--data", nargs="+", required=True,
                        help='Rutas CSV (puedes usar globs: "/path/*.csv")')
    parser.add_argument("--out-dir", default="./models", 
                        help="Directorio de salida para modelos")
    parser.add_argument("--test-size", type=float, default=0.2,
                        help="Fracción de datos para prueba")
    parser.add_argument("--optimize", action="store_true",
                        help="Optimizar hiperparámetros (más lento)")
    parser.add_argument("--n-jobs", type=int, default=1,
                        help="Número de procesos paralelos")
    parser.add_argument("--random-state", type=int, default=42,
                        help="Semilla aleatoria para reproducibilidad")
    
    args = parser.parse_args()
    
    # Expandir globs
    csv_paths = []
    for pattern in args.data:
        csv_paths.extend(glob.glob(pattern))
    
    csv_paths = [p for p in csv_paths if os.path.isfile(p)]
    
    if not csv_paths:
        print("[ERROR] No se encontraron archivos CSV válidos")
        sys.exit(1)
    
    print(f"[INFO] Encontrados {len(csv_paths)} archivos CSV")
    
    try:
        # Cargar y preparar datos
        X, y_dict, n_samples = load_and_prepare_data(csv_paths)
        
        print(f"[INFO] Dataset preparado: {n_samples} muestras, {X.shape[1]} features")
        
        # Verificar que hay suficientes datos
        if n_samples < 100:
            print("[WARN] Pocas muestras para entrenamiento robusto (< 100)")
        
        # Entrenar modelos
        models, scaler, metrics = train_models(
            X, y_dict, 
            test_size=args.test_size,
            optimize=args.optimize,
            random_state=args.random_state,
            n_jobs=args.n_jobs
        )
        
        # Guardar modelos
        model_path, scaler_path = save_models(models, scaler, args.out_dir)
        
        # Generar reporte
        report_path = generate_report(metrics, args.out_dir)
        
        print("\\n" + "=" * 50)
        print("ENTRENAMIENTO COMPLETADO")
        print("=" * 50)
        print(f"Modelos:  {model_path}")
        print(f"Scaler:   {scaler_path}")
        print(f"Reporte:  {report_path}")
        
        # Resumen rápido
        avg_r2 = np.mean([metrics[p]['test_r2'] for p in GAIT_KEYS])
        print(f"\\nR² promedio: {avg_r2:.4f}")
        
        if avg_r2 > 0.7:
            print("✓ Modelos entrenados exitosamente")
        else:
            print("⚠ Modelos entrenados pero con baja precisión")
            print("  Considera: más datos, ajuste de hiperparámetros, o revisión de features")
        
    except Exception as e:
        print(f"[ERROR] Error durante entrenamiento: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
