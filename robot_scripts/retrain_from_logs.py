#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
retrain_from_logs.py - Reentrenamiento de modelos Random Forest usando datos CSV de logs

Este script lee los CSVs generados por adaptive_walk_randomforest.py durante
la operación del robot y reenentrena los modelos con los nuevos datos.

Uso:
    python retrain_from_logs.py --log-dir logs --models-dir models --output-dir models_retrained
"""

from __future__ import print_function
import argparse
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

# Configuración de features y parámetros (debe coincidir con adaptive_walk_randomforest.py)
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_KEYS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

def load_csv_logs(log_dir):
    """Cargar y combinar todos los CSVs de logs"""
    pattern = os.path.join(log_dir, "adaptive_data_*.csv")
    csv_files = glob.glob(pattern)
    
    if not csv_files:
        raise ValueError("No se encontraron archivos CSV en {}".format(log_dir))
    
    print("[INFO] Encontrados {} archivos CSV".format(len(csv_files)))
    
    dfs = []
    for csv_file in sorted(csv_files):
        try:
            df = pd.read_csv(csv_file)
            df['source_file'] = os.path.basename(csv_file)
            dfs.append(df)
            print("[INFO] Cargado: {} ({} filas)".format(csv_file, len(df)))
        except Exception as e:
            print("[WARN] Error cargando {}: {}".format(csv_file, e))
    
    if not dfs:
        raise ValueError("No se pudieron cargar archivos CSV válidos")
    
    # Combinar todos los DataFrames
    combined_df = pd.concat(dfs, ignore_index=True)
    print("[INFO] Datos combinados: {} filas totales".format(len(combined_df)))
    
    return combined_df

def prepare_training_data(df, use_applied=True):
    """Preparar datos para entrenamiento
    
    Args:
        df: DataFrame con logs
        use_applied: Si True, usa applied_params como targets; si False, usa pred_norm_params
    """
    # Filtrar solo filas exitosas
    df_success = df[df['success'] == True].copy()
    print("[INFO] Filas exitosas: {} de {} ({:.1f}%)".format(
        len(df_success), len(df), 100.0 * len(df_success) / len(df)))
    
    if len(df_success) < 10:
        raise ValueError("Muy pocas muestras exitosas para entrenar ({})".format(len(df_success)))
    
    # Extraer features
    feature_cols = ['feat_{}'.format(name) for name in FEAT_ORDER]
    X = df_success[feature_cols].values
    
    # Extraer targets
    if use_applied:
        # Usar parámetros aplicados como target (valores reales)
        target_cols = ['applied_{}'.format(param) for param in GAIT_KEYS]
        y_dict = {}
        for i, param in enumerate(GAIT_KEYS):
            y_dict[param] = df_success[target_cols[i]].values
    else:
        # Usar predicciones normalizadas como target
        target_cols = ['pred_norm_{}'.format(param) for param in GAIT_KEYS]
        y_dict = {}
        for i, param in enumerate(GAIT_KEYS):
            y_dict[param] = df_success[target_cols[i]].values
    
    print("[INFO] Features shape: {}".format(X.shape))
    print("[INFO] Targets: {}".format(list(y_dict.keys())))
    
    return X, y_dict

def train_models(X, y_dict, n_estimators=100, max_depth=10, random_state=42):
    """Entrenar modelos Random Forest para cada parámetro"""
    models = {}
    scores = {}
    
    # Entrenar scaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    print("[INFO] Entrenando modelos...")
    
    for param in GAIT_KEYS:
        print("[INFO] Entrenando modelo para: {}".format(param))
        
        y = y_dict[param]
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=random_state
        )
        
        # Entrenar Random Forest
        rf = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            n_jobs=-1
        )
        rf.fit(X_train, y_train)
        
        # Evaluar
        y_pred = rf.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        models[param] = rf
        scores[param] = {
            'mse': mse,
            'mae': mae,
            'r2': r2,
            'n_train': len(X_train),
            'n_test': len(X_test)
        }
        
        print("  MSE: {:.6f}, MAE: {:.6f}, R²: {:.4f}".format(mse, mae, r2))
    
    return models, scaler, scores

def save_models(models, scaler, scores, output_dir):
    """Guardar modelos entrenados"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Guardar scaler
    scaler_path = os.path.join(output_dir, "feature_scaler.pkl")
    joblib.dump(scaler, scaler_path)
    print("[INFO] Scaler guardado: {}".format(scaler_path))
    
    # Guardar modelos
    for param, model in models.items():
        model_path = os.path.join(output_dir, "randomforest_model_{}.pkl".format(param))
        joblib.dump(model, model_path)
        print("[INFO] Modelo {} guardado: {}".format(param, model_path))
    
    # Guardar reporte de entrenamiento
    report_path = os.path.join(output_dir, "retrain_report.txt")
    with open(report_path, 'w') as f:
        f.write("Reporte de Reentrenamiento\n")
        f.write("=" * 40 + "\n")
        f.write("Fecha: {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        f.write("\n")
        
        for param, score in scores.items():
            f.write("Modelo: {}\n".format(param))
            f.write("  MSE: {:.6f}\n".format(score['mse']))
            f.write("  MAE: {:.6f}\n".format(score['mae']))
            f.write("  R²:  {:.4f}\n".format(score['r2']))
            f.write("  Entrenamiento: {} muestras\n".format(score['n_train']))
            f.write("  Test: {} muestras\n".format(score['n_test']))
            f.write("\n")
    
    print("[INFO] Reporte guardado: {}".format(report_path))

def main():
    parser = argparse.ArgumentParser(description='Reentrenar modelos RF desde logs CSV')
    parser.add_argument('--log-dir', default='logs', help='Directorio con CSVs de logs')
    parser.add_argument('--models-dir', help='Directorio con modelos originales (opcional)')
    parser.add_argument('--output-dir', default='models_retrained', help='Directorio de salida')
    parser.add_argument('--use-applied', action='store_true', 
                        help='Usar applied_params como target (vs pred_norm_params)')
    parser.add_argument('--n-estimators', type=int, default=100, help='Número de árboles')
    parser.add_argument('--max-depth', type=int, default=10, help='Profundidad máxima')
    
    args = parser.parse_args()
    
    try:
        # Cargar datos de logs
        df = load_csv_logs(args.log_dir)
        
        # Preparar datos de entrenamiento
        X, y_dict = prepare_training_data(df, use_applied=args.use_applied)
        
        # Entrenar modelos
        models, scaler, scores = train_models(
            X, y_dict, 
            n_estimators=args.n_estimators,
            max_depth=args.max_depth
        )
        
        # Guardar modelos
        save_models(models, scaler, scores, args.output_dir)
        
        print("\n[OK] Reentrenamiento completado")
        print("Modelos guardados en: {}".format(args.output_dir))
        
        # Mostrar resumen
        print("\nResumen de métricas:")
        for param, score in scores.items():
            print("  {}: R² = {:.3f}, MAE = {:.4f}".format(param, score['r2'], score['mae']))
        
        return 0
        
    except Exception as e:
        print("[ERROR] {}".format(e))
        return 1

if __name__ == '__main__':
    sys.exit(main())
