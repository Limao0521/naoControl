#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
automl_gait_optimizer.py - AutoML para optimización de parámetros de caminata NAO

Este script:
1. Combina todos los CSV de logs y datasets
2. Prepara los datos con feature engineering
3. Ejecuta AutoML para cada target de gait
4. Exporta los mejores modelos en formato compatible con NAO

Uso:
    python automl_gait_optimizer.py --time-limit 3600 --mode Compete
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
import shutil

try:
    from supervised.automl import AutoML
    print("[INFO] MLJAR-supervised disponible")
except ImportError:
    print("[ERROR] Instalar MLJAR-supervised: pip install mljar-supervised")
    sys.exit(1)

try:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from sklearn.preprocessing import StandardScaler
except ImportError:
    print("[ERROR] Instalar scikit-learn: pip install scikit-learn")
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
    
    # Combinar
    combined_df = pd.concat(dfs, ignore_index=True)
    print(f"[INFO] Datos combinados: {len(combined_df)} filas totales")
    
    return combined_df

def feature_engineering(df):
    """Aplicar feature engineering adicional"""
    print("[INFO] Aplicando feature engineering...")
    
    # Características derivadas
    if all(col in df.columns for col in ['lfoot_fl', 'lfoot_fr', 'lfoot_rl', 'lfoot_rr']):
        df['lfoot_total'] = df['lfoot_fl'] + df['lfoot_fr'] + df['lfoot_rl'] + df['lfoot_rr']
        df['rfoot_total'] = df['rfoot_fl'] + df['rfoot_fr'] + df['rfoot_rl'] + df['rfoot_rr']
        df['feet_total'] = df['lfoot_total'] + df['rfoot_total']
        df['feet_balance'] = (df['lfoot_total'] - df['rfoot_total']) / (df['feet_total'] + 1e-6)
        
        # Centro de presión aproximado por pie
        df['lfoot_cop_x'] = (df['lfoot_fr'] + df['lfoot_rr'] - df['lfoot_fl'] - df['lfoot_rl']) / (df['lfoot_total'] + 1e-6)
        df['rfoot_cop_x'] = (df['rfoot_fr'] + df['rfoot_rr'] - df['rfoot_fl'] - df['rfoot_rl']) / (df['rfoot_total'] + 1e-6)
    
    # Magnitudes de aceleración y velocidad angular
    if all(col in df.columns for col in ['accel_x', 'accel_y', 'accel_z']):
        df['accel_magnitude'] = np.sqrt(df['accel_x']**2 + df['accel_y']**2 + df['accel_z']**2)
    
    if all(col in df.columns for col in ['gyro_x', 'gyro_y', 'gyro_z']):
        df['gyro_magnitude'] = np.sqrt(df['gyro_x']**2 + df['gyro_y']**2 + df['gyro_z']**2)
    
    # Estabilidad (combinación de ángulos)
    if all(col in df.columns for col in ['angle_x', 'angle_y']):
        df['stability_index'] = np.sqrt(df['angle_x']**2 + df['angle_y']**2)
    
    print(f"[INFO] Feature engineering completado. Nuevas columnas: {df.shape[1] - len(df.columns)}")
    return df

def prepare_data(df):
    """Preparar datos para AutoML"""
    print("[INFO] Preparando datos para AutoML...")
    
    # Filtrar filas válidas
    initial_rows = len(df)
    
    # Filtrar por stable=1 si existe
    if 'stable' in df.columns:
        df = df[df['stable'] == 1]
        print(f"[INFO] Filtrado por estabilidad: {len(df)} de {initial_rows} filas")
    
    # Verificar columnas necesarias
    missing_features = [f for f in FEAT_ORDER if f not in df.columns]
    missing_targets = [t for t in GAIT_TARGETS if t not in df.columns]
    
    if missing_features:
        print(f"[WARN] Features faltantes: {missing_features}")
        # Usar solo las disponibles
        available_features = [f for f in FEAT_ORDER if f in df.columns]
    else:
        available_features = FEAT_ORDER
    
    if missing_targets:
        raise ValueError(f"Targets faltantes: {missing_targets}")
    
    # Agregar features engineered que estén disponibles
    engineered_features = [
        'lfoot_total', 'rfoot_total', 'feet_total', 'feet_balance',
        'lfoot_cop_x', 'rfoot_cop_x', 'accel_magnitude', 'gyro_magnitude', 'stability_index'
    ]
    
    for feat in engineered_features:
        if feat in df.columns:
            available_features.append(feat)
    
    print(f"[INFO] Features disponibles: {len(available_features)}")
    print(f"[INFO] Features: {available_features}")
    
    # Extraer features y targets
    X = df[available_features].copy()
    y_dict = {}
    for target in GAIT_TARGETS:
        y_dict[target] = df[target].copy()
    
    # Limpiar NaN e infinitos
    mask = np.isfinite(X).all(axis=1)
    for target in GAIT_TARGETS:
        mask &= np.isfinite(y_dict[target])
    
    X = X[mask]
    for target in GAIT_TARGETS:
        y_dict[target] = y_dict[target][mask]
    
    print(f"[INFO] Filas válidas después de limpieza: {len(X)} de {initial_rows}")
    print(f"[INFO] Features shape: {X.shape}")
    
    # Agregar información de sesión para split temporal
    if 'session' in df.columns:
        sessions = df['session'][mask]
        return X, y_dict, available_features, sessions
    
    return X, y_dict, available_features, None

def run_automl_for_target(X, y, target_name, feature_names, sessions=None, time_limit=3600, mode="Compete"):
    """Ejecutar AutoML para un target específico"""
    print(f"\n[INFO] ={'='*50}")
    print(f"[INFO] Ejecutando AutoML para: {target_name}")
    print(f"[INFO] ={'='*50}")
    
    # Crear directorio de resultados
    results_path = f"automl_results_{target_name}"
    if os.path.exists(results_path):
        shutil.rmtree(results_path)
    
    # Split temporal si tenemos sesiones
    if sessions is not None:
        unique_sessions = sessions.unique()
        n_sessions = len(unique_sessions)
        train_sessions = unique_sessions[:int(0.8 * n_sessions)]
        test_sessions = unique_sessions[int(0.8 * n_sessions):]
        
        train_mask = sessions.isin(train_sessions)
        test_mask = sessions.isin(test_sessions)
        
        X_train, X_test = X[train_mask], X[test_mask]
        y_train, y_test = y[train_mask], y[test_mask]
        
        print(f"[INFO] Split temporal: {len(train_sessions)} sesiones train, {len(test_sessions)} sesiones test")
        print(f"[INFO] Train: {len(X_train)} filas, Test: {len(X_test)} filas")
    else:
        # Split aleatorio
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        print(f"[INFO] Split aleatorio: Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Configurar AutoML
    automl = AutoML(
        results_path=results_path,
        total_time_limit=time_limit,
        mode=mode,
        ml_task="regression",
        eval_metric="rmse",
        algorithms=["Random Forest", "LightGBM", "Xgboost", "CatBoost"],  # Modelos compatibles
        train_ensemble=True,
        stack_models=False,  # Evitar stacking complejo
        random_state=42,
        verbose=1
    )
    
    # Entrenar
    print(f"[INFO] Iniciando entrenamiento AutoML (límite: {time_limit/60:.1f} min)...")
    automl.fit(X_train, y_train)
    
    # Evaluar
    y_pred = automl.predict(X_test)
    
    # Métricas
    mse = mean_squared_error(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    print(f"[INFO] Resultados AutoML para {target_name}:")
    print(f"  MSE: {mse:.6f}")
    print(f"  MAE: {mae:.6f}")
    print(f"  R²: {r2:.4f}")
    print(f"  RMSE: {np.sqrt(mse):.6f}")
    
    # Guardar resultados
    results = {
        'target': target_name,
        'automl': automl,
        'mse': mse,
        'mae': mae,
        'r2': r2,
        'rmse': np.sqrt(mse),
        'results_path': results_path,
        'feature_names': feature_names,
        'y_test': y_test,
        'y_pred': y_pred
    }
    
    return results

def extract_best_models(automl_results, output_dir="models_automl"):
    """Extraer y guardar los mejores modelos en formato sklearn"""
    print(f"\n[INFO] Extrayendo mejores modelos a {output_dir}/")
    os.makedirs(output_dir, exist_ok=True)
    
    # Guardar scaler común (usando el primer modelo)
    first_result = list(automl_results.values())[0]
    X_sample = first_result['automl']._X  # Datos de entrenamiento
    scaler = StandardScaler()
    scaler.fit(X_sample)
    
    scaler_path = os.path.join(output_dir, "feature_scaler.pkl")
    joblib.dump(scaler, scaler_path)
    print(f"[INFO] Scaler guardado: {scaler_path}")
    
    # Extraer mejor modelo de cada target
    model_info = {}
    
    for target_name, result in automl_results.items():
        automl = result['automl']
        
        # Obtener el mejor modelo
        best_model = automl._models[0]  # El primer modelo es el mejor
        
        # Intentar extraer modelo sklearn si es posible
        try:
            if hasattr(best_model, 'model'):
                sklearn_model = best_model.model
            else:
                sklearn_model = best_model
            
            # Guardar modelo
            model_path = os.path.join(output_dir, f"automl_model_{target_name}.pkl")
            joblib.dump(sklearn_model, model_path)
            print(f"[INFO] Modelo {target_name} guardado: {model_path}")
            
            model_info[target_name] = {
                'path': model_path,
                'model_type': type(sklearn_model).__name__,
                'performance': {
                    'mse': result['mse'],
                    'mae': result['mae'],
                    'r2': result['r2'],
                    'rmse': result['rmse']
                }
            }
            
        except Exception as e:
            print(f"[WARN] No se pudo extraer modelo sklearn para {target_name}: {e}")
            model_info[target_name] = {
                'automl_path': result['results_path'],
                'error': str(e)
            }
    
    # Guardar reporte
    report_path = os.path.join(output_dir, "automl_report.txt")
    with open(report_path, 'w') as f:
        f.write("Reporte AutoML - Optimización de Gait NAO\n")
        f.write("=" * 50 + "\n")
        f.write(f"Timestamp: {datetime.now()}\n")
        f.write(f"Modelos entrenados: {len(automl_results)}\n\n")
        
        for target_name, result in automl_results.items():
            f.write(f"{target_name}:\n")
            f.write(f"  MSE: {result['mse']:.6f}\n")
            f.write(f"  MAE: {result['mae']:.6f}\n")
            f.write(f"  R²: {result['r2']:.4f}\n")
            f.write(f"  RMSE: {result['rmse']:.6f}\n")
            if target_name in model_info and 'model_type' in model_info[target_name]:
                f.write(f"  Modelo: {model_info[target_name]['model_type']}\n")
            f.write("\n")
    
    print(f"[INFO] Reporte guardado: {report_path}")
    return model_info

def main():
    parser = argparse.ArgumentParser(description="AutoML para optimización de gait NAO")
    parser.add_argument("--time-limit", type=int, default=3600, 
                       help="Límite de tiempo por target en segundos (default: 3600)")
    parser.add_argument("--mode", choices=["Explain", "Perform", "Compete"], default="Compete",
                       help="Modo AutoML (default: Compete)")
    parser.add_argument("--output-dir", default="models_automl",
                       help="Directorio de salida para modelos (default: models_automl)")
    parser.add_argument("--save-combined", action="store_true",
                       help="Guardar CSV combinado")
    
    args = parser.parse_args()
    
    print("[INFO] Iniciando optimización AutoML para gait NAO...")
    print(f"[INFO] Límite de tiempo por target: {args.time_limit/60:.1f} minutos")
    print(f"[INFO] Modo AutoML: {args.mode}")
    
    try:
        # 1. Combinar datos
        df = combine_all_csvs()
        
        # 2. Feature engineering
        df = feature_engineering(df)
        
        # 3. Guardar CSV combinado si se solicita
        if args.save_combined:
            combined_path = "models/combined_data_automl.csv"
            df.to_csv(combined_path, index=False)
            print(f"[INFO] CSV combinado guardado: {combined_path}")
        
        # 4. Preparar datos
        X, y_dict, feature_names, sessions = prepare_data(df)
        
        # 5. Ejecutar AutoML para cada target
        automl_results = {}
        
        for target_name in GAIT_TARGETS:
            try:
                result = run_automl_for_target(
                    X, y_dict[target_name], target_name, feature_names, 
                    sessions, args.time_limit, args.mode
                )
                automl_results[target_name] = result
                
            except Exception as e:
                print(f"[ERROR] Fallo AutoML para {target_name}: {e}")
                continue
        
        # 6. Extraer y guardar mejores modelos
        if automl_results:
            model_info = extract_best_models(automl_results, args.output_dir)
            
            print(f"\n[SUCCESS] AutoML completado")
            print(f"[INFO] Modelos guardados en: {args.output_dir}/")
            print(f"[INFO] Targets procesados: {len(automl_results)}")
            
            print("\nResumen de mejores modelos:")
            for target_name, result in automl_results.items():
                print(f"  {target_name}: R² = {result['r2']:.3f}, RMSE = {result['rmse']:.4f}")
            
            # Sugerir próximos pasos
            print(f"\nPróximos pasos:")
            print(f"1. Revisar reportes detallados en: automl_results_<target>/")
            print(f"2. Exportar a NPZ: python tools/export_rf_to_npz.py --models-dir {args.output_dir} --out-dir models_npz_automl")
            print(f"3. Evaluar modelos: python robot_scripts/randomforest_replay_eval.py --models {args.output_dir}/")
            print(f"4. Si satisfactorio, copiar modelos NPZ al NAO y probar")
            
        else:
            print("[ERROR] No se pudo entrenar ningún modelo AutoML")
            return 1
            
    except Exception as e:
        print(f"[ERROR] Error durante ejecución: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
