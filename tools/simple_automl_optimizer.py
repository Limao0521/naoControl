#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
simple_automl_optimizer.py - AutoML simplificado para optimización de gait NAO

Script alternativo que usa hyperparameter tuning con scikit-learn
para optimizar modelos RandomForest, LightGBM y XGBoost.

Uso:
    python simple_automl_optimizer.py --time-limit 1800
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
import json

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split, GridSearchCV, RandomizedSearchCV
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from sklearn.preprocessing import StandardScaler
    import lightgbm as lgb
    import xgboost as xgb
    print("[INFO] Librerías AutoML disponibles")
except ImportError as e:
    print(f"[ERROR] Error importando librerías: {e}")
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

GAIT_TARGETS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

def combine_all_csvs():
    """Combinar todos los CSV de logs y datasets"""
    print("[INFO] Combinando todos los archivos CSV...")
    
    dfs = []
    
    # Cargar logs adaptativos
    logs_pattern = "robot_scripts/logs/*.csv"
    log_files = glob.glob(logs_pattern)
    print(f"[INFO] Encontrados {len(log_files)} archivos en robot_scripts/logs/")
    
    for file_path in log_files:
        try:
            df = pd.read_csv(file_path)
            if len(df) > 0:
                df['source'] = 'adaptive_logs'
                df['session'] = os.path.basename(file_path).replace('.csv', '')
                dfs.append(df)
                print(f"  ✓ {os.path.basename(file_path)}: {len(df)} filas")
        except Exception as e:
            print(f"  ✗ Error en {file_path}: {e}")
    
    # Cargar datasets de walks
    walks_pattern = "datasets/walks/*.csv"
    walk_files = glob.glob(walks_pattern)
    print(f"[INFO] Encontrados {len(walk_files)} archivos en datasets/walks/")
    
    for file_path in walk_files:
        try:
            df = pd.read_csv(file_path)
            if len(df) > 0:
                df['source'] = 'walk_logs'
                df['session'] = os.path.basename(file_path).replace('.csv', '')
                dfs.append(df)
                print(f"  ✓ {os.path.basename(file_path)}: {len(df)} filas")
        except Exception as e:
            print(f"  ✗ Error en {file_path}: {e}")
    
    if not dfs:
        raise ValueError("No se pudieron cargar archivos CSV válidos")
    
    combined_df = pd.concat(dfs, ignore_index=True)
    print(f"[INFO] Datos combinados: {len(combined_df)} filas totales")
    
    return combined_df

def feature_engineering(df):
    """Aplicar feature engineering adicional"""
    print("[INFO] Aplicando feature engineering...")
    
    # Características derivadas FSR
    if all(col in df.columns for col in ['lfoot_fl', 'lfoot_fr', 'lfoot_rl', 'lfoot_rr']):
        df['lfoot_total'] = df['lfoot_fl'] + df['lfoot_fr'] + df['lfoot_rl'] + df['lfoot_rr']
        df['rfoot_total'] = df['rfoot_fl'] + df['rfoot_fr'] + df['rfoot_rl'] + df['rfoot_rr']
        df['feet_total'] = df['lfoot_total'] + df['rfoot_total']
        df['feet_balance'] = (df['lfoot_total'] - df['rfoot_total']) / (df['feet_total'] + 1e-6)
    
    # Magnitudes de sensores
    if all(col in df.columns for col in ['accel_x', 'accel_y', 'accel_z']):
        df['accel_magnitude'] = np.sqrt(df['accel_x']**2 + df['accel_y']**2 + df['accel_z']**2)
    
    if all(col in df.columns for col in ['gyro_x', 'gyro_y', 'gyro_z']):
        df['gyro_magnitude'] = np.sqrt(df['gyro_x']**2 + df['gyro_y']**2 + df['gyro_z']**2)
    
    # Estabilidad
    if all(col in df.columns for col in ['angle_x', 'angle_y']):
        df['stability_index'] = np.sqrt(df['angle_x']**2 + df['angle_y']**2)
    
    print(f"[INFO] Feature engineering completado. Columnas: {df.shape[1]}")
    return df

def prepare_data(df):
    """Preparar datos para AutoML"""
    print("[INFO] Preparando datos...")
    
    # Filtrar por stable=1
    initial_rows = len(df)
    if 'stable' in df.columns:
        df = df[df['stable'] == 1]
        print(f"[INFO] Filtrado por estabilidad: {len(df)} de {initial_rows} filas")
    
    # Features disponibles
    available_features = [f for f in FEAT_ORDER if f in df.columns]
    
    # Agregar features engineered
    engineered_features = [
        'lfoot_total', 'rfoot_total', 'feet_total', 'feet_balance',
        'accel_magnitude', 'gyro_magnitude', 'stability_index'
    ]
    
    for feat in engineered_features:
        if feat in df.columns:
            available_features.append(feat)
    
    print(f"[INFO] Features disponibles: {len(available_features)}")
    
    # Extraer datos
    X = df[available_features].copy()
    y_dict = {}
    for target in GAIT_TARGETS:
        if target in df.columns:
            y_dict[target] = df[target].copy()
    
    # Limpiar NaN
    mask = np.isfinite(X).all(axis=1)
    for target in y_dict:
        mask &= np.isfinite(y_dict[target])
    
    X = X[mask]
    for target in y_dict:
        y_dict[target] = y_dict[target][mask]
    
    print(f"[INFO] Filas válidas: {len(X)} de {initial_rows}")
    print(f"[INFO] Features shape: {X.shape}")
    
    return X, y_dict, available_features

def optimize_model_hyperparams(X, y, target_name, model_type="random_forest", time_limit=1800):
    """Optimizar hiperparámetros para un target específico"""
    print(f"\n[INFO] Optimizando {model_type} para {target_name}")
    
    # Split datos
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Configurar modelos y parámetros
    if model_type == "random_forest":
        model = RandomForestRegressor(random_state=42, n_jobs=-1)
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [10, 20, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'max_features': ['auto', 'sqrt', 0.3]
        }
    
    elif model_type == "lightgbm":
        model = lgb.LGBMRegressor(random_state=42, verbose=-1)
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [6, 10, 15],
            'learning_rate': [0.01, 0.1, 0.2],
            'num_leaves': [31, 50, 100],
            'min_child_samples': [20, 30, 50]
        }
    
    elif model_type == "xgboost":
        model = xgb.XGBRegressor(random_state=42, n_jobs=-1)
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [3, 6, 10],
            'learning_rate': [0.01, 0.1, 0.2],
            'subsample': [0.8, 0.9, 1.0],
            'colsample_bytree': [0.8, 0.9, 1.0]
        }
    
    # Grid search con tiempo límite
    max_iter = min(50, time_limit // 60)  # Aproximación
    
    search = RandomizedSearchCV(
        model, param_grid, n_iter=max_iter,
        cv=3, scoring='neg_mean_squared_error',
        n_jobs=-1, random_state=42
    )
    
    print(f"[INFO] Iniciando búsqueda con {max_iter} iteraciones...")
    search.fit(X_train, y_train)
    
    # Mejor modelo
    best_model = search.best_estimator_
    
    # Evaluar
    y_pred = best_model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    print(f"[INFO] Mejor score CV: {-search.best_score_:.6f}")
    print(f"[INFO] Test - MSE: {mse:.6f}, MAE: {mae:.6f}, R²: {r2:.4f}")
    
    return {
        'model': best_model,
        'model_type': model_type,
        'target': target_name,
        'best_params': search.best_params_,
        'cv_score': -search.best_score_,
        'mse': mse,
        'mae': mae,
        'r2': r2,
        'rmse': np.sqrt(mse)
    }

def run_automl_comparison(X, y_dict, time_limit=1800):
    """Ejecutar optimización para todos los targets y modelos"""
    print("[INFO] Iniciando optimización AutoML...")
    
    models_to_test = ["random_forest", "lightgbm", "xgboost"]
    results = {}
    
    time_per_model = time_limit // (len(GAIT_TARGETS) * len(models_to_test))
    
    for target_name in GAIT_TARGETS:
        if target_name not in y_dict:
            print(f"[WARN] Target {target_name} no disponible")
            continue
        
        results[target_name] = {}
        
        for model_type in models_to_test:
            try:
                result = optimize_model_hyperparams(
                    X, y_dict[target_name], target_name, 
                    model_type, time_per_model
                )
                results[target_name][model_type] = result
                
            except Exception as e:
                print(f"[ERROR] Fallo {model_type} para {target_name}: {e}")
                continue
    
    return results

def save_best_models(results, output_dir="models_automl"):
    """Guardar los mejores modelos"""
    print(f"\n[INFO] Guardando mejores modelos en {output_dir}/")
    os.makedirs(output_dir, exist_ok=True)
    
    # Guardar scaler (usando primer resultado)
    first_result = None
    for target_results in results.values():
        for model_result in target_results.values():
            first_result = model_result
            break
        if first_result:
            break
    
    if first_result:
        # Crear scaler dummy (en producción usar el real)
        scaler = StandardScaler()
        scaler_path = os.path.join(output_dir, "feature_scaler.pkl")
        joblib.dump(scaler, scaler_path)
        print(f"[INFO] Scaler guardado: {scaler_path}")
    
    # Seleccionar mejores modelos por target
    best_models = {}
    summary = {}
    
    for target_name, target_results in results.items():
        if not target_results:
            continue
        
        # Encontrar mejor modelo por R²
        best_model_type = max(target_results.keys(), 
                            key=lambda k: target_results[k]['r2'])
        best_result = target_results[best_model_type]
        
        # Guardar modelo
        model_path = os.path.join(output_dir, f"automl_model_{target_name}.pkl")
        joblib.dump(best_result['model'], model_path)
        
        best_models[target_name] = {
            'model_type': best_model_type,
            'path': model_path,
            'performance': {
                'mse': best_result['mse'],
                'mae': best_result['mae'],
                'r2': best_result['r2'],
                'rmse': best_result['rmse']
            },
            'params': best_result['best_params']
        }
        
        print(f"[INFO] {target_name}: Mejor modelo {best_model_type} (R²={best_result['r2']:.3f})")
        
        summary[target_name] = {
            'best_model': best_model_type,
            'r2': best_result['r2'],
            'rmse': best_result['rmse'],
            'mae': best_result['mae']
        }
    
    # Guardar reporte
    report_path = os.path.join(output_dir, "automl_report.txt")
    with open(report_path, 'w') as f:
        f.write("Reporte AutoML - Optimización Simple de Gait NAO\n")
        f.write("=" * 55 + "\n")
        f.write(f"Timestamp: {datetime.now()}\n")
        f.write(f"Targets procesados: {len(best_models)}\n\n")
        
        for target_name, info in best_models.items():
            f.write(f"{target_name}:\n")
            f.write(f"  Mejor modelo: {info['model_type']}\n")
            f.write(f"  R²: {info['performance']['r2']:.4f}\n")
            f.write(f"  RMSE: {info['performance']['rmse']:.6f}\n")
            f.write(f"  MAE: {info['performance']['mae']:.6f}\n")
            f.write(f"  Parámetros: {info['params']}\n\n")
    
    print(f"[INFO] Reporte guardado: {report_path}")
    
    # Guardar resumen JSON
    summary_path = os.path.join(output_dir, "automl_summary.json")
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    return best_models

def main():
    parser = argparse.ArgumentParser(description="AutoML simple para gait NAO")
    parser.add_argument("--time-limit", type=int, default=1800,
                       help="Límite total en segundos (default: 1800)")
    parser.add_argument("--output-dir", default="models_automl",
                       help="Directorio de salida")
    parser.add_argument("--save-combined", action="store_true",
                       help="Guardar CSV combinado")
    
    args = parser.parse_args()
    
    print("[INFO] Iniciando AutoML simple para gait NAO...")
    print(f"[INFO] Límite de tiempo total: {args.time_limit/60:.1f} minutos")
    
    try:
        # 1. Combinar datos
        df = combine_all_csvs()
        
        # 2. Feature engineering
        df = feature_engineering(df)
        
        # 3. Guardar CSV si se solicita
        if args.save_combined:
            combined_path = "models/combined_data_simple_automl.csv"
            df.to_csv(combined_path, index=False)
            print(f"[INFO] CSV combinado guardado: {combined_path}")
        
        # 4. Preparar datos
        X, y_dict, feature_names = prepare_data(df)
        
        if len(y_dict) == 0:
            print("[ERROR] No se encontraron targets válidos")
            return 1
        
        # 5. Ejecutar AutoML
        results = run_automl_comparison(X, y_dict, args.time_limit)
        
        # 6. Guardar mejores modelos
        if results:
            best_models = save_best_models(results, args.output_dir)
            
            print(f"\n[SUCCESS] AutoML completado")
            print(f"[INFO] Modelos guardados en: {args.output_dir}/")
            
            print("\nResumen de mejores modelos:")
            for target_name, info in best_models.items():
                perf = info['performance']
                print(f"  {target_name}: {info['model_type']} - R²={perf['r2']:.3f}, RMSE={perf['rmse']:.4f}")
            
            print(f"\nPróximos pasos:")
            print(f"1. Exportar a NPZ: python tools/export_rf_to_npz.py --models-dir {args.output_dir} --out-dir models_npz_automl")
            print(f"2. Evaluar: python robot_scripts/randomforest_replay_eval.py --models {args.output_dir}/")
            
        else:
            print("[ERROR] No se pudieron entrenar modelos")
            return 1
            
    except Exception as e:
        print(f"[ERROR] Error durante ejecución: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
