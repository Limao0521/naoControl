#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
compare_models_performance.py - Comparar rendimiento RandomForest vs LightGBM AutoML

Script para comparar el rendimiento de los modelos originales RandomForest
vs los nuevos modelos LightGBM optimizados con AutoML.
"""

from __future__ import print_function
import os
import sys
import glob
import pandas as pd
import numpy as np
import joblib
from datetime import datetime

try:
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    print("[INFO] Scikit-learn disponible para evaluación")
except ImportError:
    print("[ERROR] Scikit-learn no disponible")
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

def load_test_data():
    """Cargar datos de prueba combinados"""
    print("[INFO] Cargando datos de prueba...")
    
    # Buscar CSV combinado más reciente
    combined_files = glob.glob("models/combined_data*.csv")
    
    if not combined_files:
        print("[ERROR] No se encontró archivo de datos combinados")
        return None, None, None
    
    # Usar el más reciente
    latest_file = max(combined_files, key=os.path.getmtime)
    print(f"[INFO] Usando: {latest_file}")
    
    df = pd.read_csv(latest_file)
    print(f"[INFO] Datos cargados: {len(df)} filas")
    
    # Filtrar por stable=1
    if 'stable' in df.columns:
        df = df[df['stable'] == 1]
        print(f"[INFO] Datos estables: {len(df)} filas")
    
    # Feature engineering (igual que en AutoML)
    if all(col in df.columns for col in ['lfoot_fl', 'lfoot_fr', 'lfoot_rl', 'lfoot_rr']):
        df['lfoot_total'] = df['lfoot_fl'] + df['lfoot_fr'] + df['lfoot_rl'] + df['lfoot_rr']
        df['rfoot_total'] = df['rfoot_fl'] + df['rfoot_fr'] + df['rfoot_rl'] + df['rfoot_rr']
        df['feet_total'] = df['lfoot_total'] + df['rfoot_total']
        df['feet_balance'] = (df['lfoot_total'] - df['rfoot_total']) / (df['feet_total'] + 1e-6)
    
    if all(col in df.columns for col in ['accel_x', 'accel_y', 'accel_z']):
        df['accel_magnitude'] = np.sqrt(df['accel_x']**2 + df['accel_y']**2 + df['accel_z']**2)
    
    if all(col in df.columns for col in ['gyro_x', 'gyro_y', 'gyro_z']):
        df['gyro_magnitude'] = np.sqrt(df['gyro_x']**2 + df['gyro_y']**2 + df['gyro_z']**2)
    
    if all(col in df.columns for col in ['angle_x', 'angle_y']):
        df['stability_index'] = np.sqrt(df['angle_x']**2 + df['angle_y']**2)
    
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
    
    print(f"[INFO] Datos finales: {len(X)} filas, {X.shape[1]} features")
    
    return X, y_dict, available_features

def evaluate_randomforest_models(X, y_dict):
    """Evaluar modelos RandomForest originales"""
    print("\n[INFO] Evaluando modelos RandomForest originales...")
    
    results = {}
    
    # Usar solo features originales para RF (20 features)
    original_features = [f for f in FEAT_ORDER if f in X.columns]
    print(f"[INFO] Usando {len(original_features)} features originales para RF")
    X_rf = X[original_features]
    
    for target in GAIT_TARGETS:
        if target not in y_dict:
            print(f"[WARN] Target {target} no disponible")
            continue
        
        model_path = f"models/randomforest_model_{target}.pkl"
        
        if not os.path.exists(model_path):
            print(f"[WARN] Modelo RF no encontrado: {model_path}")
            continue
        
        try:
            # Cargar modelo
            model = joblib.load(model_path)
            
            # Predecir con features originales
            y_pred = model.predict(X_rf)
            y_true = y_dict[target]
            
            # Métricas
            mse = mean_squared_error(y_true, y_pred)
            mae = mean_absolute_error(y_true, y_pred)
            r2 = r2_score(y_true, y_pred)
            
            results[target] = {
                'model_type': 'RandomForest',
                'mse': mse,
                'mae': mae,
                'r2': r2,
                'rmse': np.sqrt(mse)
            }
            
            print(f"  {target}: R²={r2:.4f}, RMSE={np.sqrt(mse):.6f}, MAE={mae:.6f}")
            
        except Exception as e:
            print(f"[ERROR] Error evaluando RF {target}: {e}")
    
    return results

def evaluate_lightgbm_models(X, y_dict):
    """Evaluar modelos LightGBM AutoML"""
    print("\n[INFO] Evaluando modelos LightGBM AutoML...")
    
    results = {}
    
    for target in GAIT_TARGETS:
        if target not in y_dict:
            continue
        
        model_path = f"models_automl/automl_model_{target}.pkl"
        
        if not os.path.exists(model_path):
            print(f"[WARN] Modelo LightGBM no encontrado: {model_path}")
            continue
        
        try:
            # Cargar modelo
            model = joblib.load(model_path)
            
            # Predecir
            y_pred = model.predict(X)
            y_true = y_dict[target]
            
            # Métricas
            mse = mean_squared_error(y_true, y_pred)
            mae = mean_absolute_error(y_true, y_pred)
            r2 = r2_score(y_true, y_pred)
            
            results[target] = {
                'model_type': 'LightGBM',
                'mse': mse,
                'mae': mae,
                'r2': r2,
                'rmse': np.sqrt(mse)
            }
            
            print(f"  {target}: R²={r2:.4f}, RMSE={np.sqrt(mse):.6f}, MAE={mae:.6f}")
            
        except Exception as e:
            print(f"[ERROR] Error evaluando LightGBM {target}: {e}")
    
    return results

def compare_and_report(rf_results, lgb_results):
    """Comparar resultados y generar reporte"""
    print("\n" + "="*80)
    print("COMPARACIÓN MODELOS: RandomForest vs LightGBM AutoML")
    print("="*80)
    
    comparison = {}
    
    for target in GAIT_TARGETS:
        if target in rf_results and target in lgb_results:
            rf = rf_results[target]
            lgb = lgb_results[target]
            
            # Calcular mejoras
            r2_improvement = (lgb['r2'] - rf['r2']) / rf['r2'] * 100 if rf['r2'] > 0 else 0
            rmse_improvement = (rf['rmse'] - lgb['rmse']) / rf['rmse'] * 100 if rf['rmse'] > 0 else 0
            mae_improvement = (rf['mae'] - lgb['mae']) / rf['mae'] * 100 if rf['mae'] > 0 else 0
            
            comparison[target] = {
                'rf_r2': rf['r2'],
                'lgb_r2': lgb['r2'],
                'r2_improvement': r2_improvement,
                'rf_rmse': rf['rmse'],
                'lgb_rmse': lgb['rmse'],
                'rmse_improvement': rmse_improvement,
                'rf_mae': rf['mae'],
                'lgb_mae': lgb['mae'],
                'mae_improvement': mae_improvement,
                'winner': 'LightGBM' if lgb['r2'] > rf['r2'] else 'RandomForest'
            }
            
            print(f"\n{target}:")
            print(f"  RandomForest: R²={rf['r2']:.4f}, RMSE={rf['rmse']:.6f}, MAE={rf['mae']:.6f}")
            print(f"  LightGBM:    R²={lgb['r2']:.4f}, RMSE={lgb['rmse']:.6f}, MAE={lgb['mae']:.6f}")
            print(f"  Mejoras:     R²={r2_improvement:+.2f}%, RMSE={rmse_improvement:+.2f}%, MAE={mae_improvement:+.2f}%")
            print(f"  Ganador:     {comparison[target]['winner']}")
    
    # Resumen general
    print(f"\n" + "-"*80)
    print("RESUMEN GENERAL:")
    
    lgb_wins = sum(1 for comp in comparison.values() if comp['winner'] == 'LightGBM')
    rf_wins = len(comparison) - lgb_wins
    
    print(f"  LightGBM gana en: {lgb_wins}/{len(comparison)} targets")
    print(f"  RandomForest gana en: {rf_wins}/{len(comparison)} targets")
    
    if lgb_wins > rf_wins:
        print(f"  🏆 GANADOR GENERAL: LightGBM AutoML")
        recommendation = "LightGBM"
    else:
        print(f"  🏆 GANADOR GENERAL: RandomForest")
        recommendation = "RandomForest"
    
    # Mejoras promedio
    avg_r2_improvement = np.mean([comp['r2_improvement'] for comp in comparison.values()])
    avg_rmse_improvement = np.mean([comp['rmse_improvement'] for comp in comparison.values()])
    avg_mae_improvement = np.mean([comp['mae_improvement'] for comp in comparison.values()])
    
    print(f"  Mejora promedio R²: {avg_r2_improvement:+.2f}%")
    print(f"  Mejora promedio RMSE: {avg_rmse_improvement:+.2f}%")
    print(f"  Mejora promedio MAE: {avg_mae_improvement:+.2f}%")
    
    # Guardar reporte
    report_path = "models/model_comparison_report.txt"
    with open(report_path, 'w') as f:
        f.write("Reporte Comparación: RandomForest vs LightGBM AutoML\\n")
        f.write("="*60 + "\\n")
        f.write(f"Timestamp: {datetime.now()}\\n")
        f.write(f"Datos evaluados: {len(comparison)} targets\\n\\n")
        
        for target, comp in comparison.items():
            f.write(f"{target}:\\n")
            f.write(f"  RandomForest: R²={comp['rf_r2']:.4f}, RMSE={comp['rf_rmse']:.6f}\\n")
            f.write(f"  LightGBM:    R²={comp['lgb_r2']:.4f}, RMSE={comp['lgb_rmse']:.6f}\\n")
            f.write(f"  Mejora R²:   {comp['r2_improvement']:+.2f}%\\n")
            f.write(f"  Ganador:     {comp['winner']}\\n\\n")
        
        f.write(f"RESUMEN:\\n")
        f.write(f"  LightGBM gana: {lgb_wins}/{len(comparison)}\\n")
        f.write(f"  Recomendación: {recommendation}\\n")
        f.write(f"  Mejora promedio R²: {avg_r2_improvement:+.2f}%\\n")
    
    print(f"\\n[INFO] Reporte guardado: {report_path}")
    
    return comparison, recommendation

def main():
    print("[INFO] Iniciando comparación de modelos...")
    
    # Cargar datos de prueba
    X, y_dict, features = load_test_data()
    
    if X is None:
        print("[ERROR] No se pudieron cargar datos de prueba")
        return 1
    
    # Evaluar RandomForest
    rf_results = evaluate_randomforest_models(X, y_dict)
    
    # Evaluar LightGBM
    lgb_results = evaluate_lightgbm_models(X, y_dict)
    
    # Comparar
    if rf_results and lgb_results:
        comparison, recommendation = compare_and_report(rf_results, lgb_results)
        
        print(f"\\n[SUCCESS] Comparación completada")
        print(f"[RECOMMENDATION] Usar modelos: {recommendation}")
        
        if recommendation == "LightGBM":
            print(f"\\nPróximos pasos:")
            print(f"1. Los modelos LightGBM ya están exportados en: models_npz_automl/")
            print(f"2. Copiar models_npz_automl/ al NAO")
            print(f"3. Modificar adaptive_walk_randomforest.py para usar LightGBM")
            print(f"4. Probar en el NAO y validar mejoras reales")
        
    else:
        print("[ERROR] No se pudieron completar las evaluaciones")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
