#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
randomforest_replay_eval.py — Evaluación y replay de modelos Random Forest

Script para evaluar modelos Random Forest entrenados sobre datasets de test,
generar predicciones offline y analizar el rendimiento del sistema.

Reemplaza xgboost_replay_eval.py manteniendo la misma funcionalidad.

Funcionalidades:
- Cargar modelos Random Forest pre-entrenados
- Evaluar sobre datasets de test
- Generar predicciones para análisis offline
- Métricas de rendimiento detalladas
- Visualización de resultados (opcional)

Uso:
  python randomforest_replay_eval.py --models models/ --data datasets/walks/test.csv --output results/
  python randomforest_replay_eval.py --models models/ --data "datasets/walks/*.csv" --plot
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
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib

# Intentar importar matplotlib para visualización (opcional)
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Backend sin GUI
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("[WARN] matplotlib no disponible - sin visualizaciones")

# Orden de features (debe coincidir con entrenamiento)
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_KEYS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

# Rangos físicos para desnormalización
PARAM_RANGES = {
    'StepHeight':   (0.01, 0.05),
    'MaxStepX':     (0.02, 0.08),
    'MaxStepY':     (0.08, 0.20),
    'MaxStepTheta': (0.10, 0.50),
    'Frequency':    (0.50, 1.20),
}

class RandomForestEvaluator:
    """
    Evaluador de modelos Random Forest para marcha adaptativa
    """
    
    def __init__(self, models_dir, verbose=True):
        self.models_dir = models_dir
        self.verbose = verbose
        
        # Modelos cargados
        self.models = {}
        self.scaler = None
        
        # Resultados
        self.evaluation_results = {}
        
    def load_models(self):
        """Cargar modelos Random Forest y scaler"""
        if self.verbose:
            print("[INFO] Cargando modelos desde: {}".format(self.models_dir))
        
        # Cargar scaler
        scaler_path = os.path.join(self.models_dir, "feature_scaler.pkl")
        if not os.path.exists(scaler_path):
            raise RuntimeError("Scaler no encontrado: {}".format(scaler_path))
        
        try:
            self.scaler = joblib.load(scaler_path)
            if self.verbose:
                print("  ✓ Scaler cargado")
        except Exception as e:
            raise RuntimeError("Error cargando scaler: {}".format(e))
        
        # Cargar modelos Random Forest
        for param in GAIT_KEYS:
            model_path = os.path.join(self.models_dir, "randomforest_model_{}.pkl".format(param))
            
            if not os.path.exists(model_path):
                raise RuntimeError("Modelo {} no encontrado: {}".format(param, model_path))
            
            try:
                model = joblib.load(model_path)
                self.models[param] = model
                if self.verbose:
                    print("  ✓ Modelo {} cargado".format(param))
            except Exception as e:
                raise RuntimeError("Error cargando modelo {}: {}".format(param, e))
        
        if self.verbose:
            print("[INFO] Todos los modelos cargados correctamente")
    
    def load_test_data(self, data_paths):
        """Cargar datos de test desde archivos CSV"""
        if self.verbose:
            print("[INFO] Cargando datos de test...")
        
        dfs = []
        
        for path in data_paths:
            try:
                df = pd.read_csv(path)
                dfs.append(df)
                if self.verbose:
                    print("  ✓ {}: {} filas".format(os.path.basename(path), len(df)))
            except Exception as e:
                print("  ✗ Error en {}: {}".format(path, e))
        
        if not dfs:
            raise RuntimeError("No se pudieron cargar archivos CSV válidos")
        
        # Concatenar DataFrames
        df = pd.concat(dfs, ignore_index=True)
        
        if self.verbose:
            print("[INFO] Dataset de test: {} filas totales".format(len(df)))
        
        return df
    
    def prepare_data(self, df):
        """Preparar datos para evaluación"""
        if self.verbose:
            print("[INFO] Preparando datos de test...")
        
        # Verificar features
        for col in FEAT_ORDER:
            if col not in df.columns:
                df[col] = 0.0
                if self.verbose:
                    print("  [WARN] Feature '{}' faltante, rellenada con 0.0".format(col))
        
        # Filtrar filas válidas (con todos los targets)
        mask_valid = np.ones(len(df), dtype=bool)
        for param in GAIT_KEYS:
            if param in df.columns:
                mask_valid &= df[param].notna()
            else:
                raise RuntimeError("Target '{}' no encontrado en datos".format(param))
        
        df_clean = df[mask_valid].copy()
        
        if self.verbose:
            print("[INFO] Filas válidas: {} de {}".format(len(df_clean), len(df)))
        
        if len(df_clean) == 0:
            raise RuntimeError("No hay filas válidas en datos de test")
        
        # Extraer features
        X = df_clean[FEAT_ORDER].values.astype(np.float32)
        
        # Extraer y normalizar targets
        y_dict = {}
        y_raw_dict = {}
        
        for param in GAIT_KEYS:
            values = df_clean[param].values
            y_raw_dict[param] = values.copy()
            
            # Normalizar a [0,1]
            min_val, max_val = PARAM_RANGES[param]
            values_norm = (values - min_val) / (max_val - min_val)
            values_norm = np.clip(values_norm, 0.0, 1.0)
            
            y_dict[param] = values_norm
        
        return X, y_dict, y_raw_dict, df_clean
    
    def predict(self, X):
        """Generar predicciones con modelos Random Forest"""
        if self.verbose:
            print("[INFO] Generando predicciones...")
        
        # Escalar features
        X_scaled = self.scaler.transform(X)
        
        predictions = {}
        predictions_raw = {}
        
        for param in GAIT_KEYS:
            model = self.models[param]
            
            # Predicción normalizada
            pred_norm = model.predict(X_scaled)
            predictions[param] = pred_norm
            
            # Desnormalizar
            min_val, max_val = PARAM_RANGES[param]
            pred_raw = min_val + pred_norm * (max_val - min_val)
            pred_raw = np.clip(pred_raw, min_val, max_val)
            predictions_raw[param] = pred_raw
        
        return predictions, predictions_raw
    
    def evaluate_models(self, X, y_dict, y_raw_dict):
        """Evaluar modelos y calcular métricas"""
        if self.verbose:
            print("[INFO] Evaluando modelos...")
        
        # Generar predicciones
        pred_norm, pred_raw = self.predict(X)
        
        # Calcular métricas
        metrics = {}
        
        for param in GAIT_KEYS:
            # Métricas en espacio normalizado
            y_true_norm = y_dict[param]
            y_pred_norm = pred_norm[param]
            
            mse_norm = mean_squared_error(y_true_norm, y_pred_norm)
            mae_norm = mean_absolute_error(y_true_norm, y_pred_norm)
            r2_norm = r2_score(y_true_norm, y_pred_norm)
            
            # Métricas en espacio físico
            y_true_raw = y_raw_dict[param]
            y_pred_raw = pred_raw[param]
            
            mse_raw = mean_squared_error(y_true_raw, y_pred_raw)
            mae_raw = mean_absolute_error(y_true_raw, y_pred_raw)
            r2_raw = r2_score(y_true_raw, y_pred_raw)
            
            # RMSE
            rmse_norm = np.sqrt(mse_norm)
            rmse_raw = np.sqrt(mse_raw)
            
            # Error porcentual medio
            mape_raw = np.mean(np.abs((y_true_raw - y_pred_raw) / y_true_raw)) * 100
            
            metrics[param] = {
                'mse_norm': mse_norm, 'mae_norm': mae_norm, 'r2_norm': r2_norm, 'rmse_norm': rmse_norm,
                'mse_raw': mse_raw, 'mae_raw': mae_raw, 'r2_raw': r2_raw, 'rmse_raw': rmse_raw,
                'mape_raw': mape_raw
            }
            
            if self.verbose:
                print("  {} - R²: {:.4f}, RMSE: {:.6f}, MAPE: {:.2f}%".format(
                    param, r2_raw, rmse_raw, mape_raw))
        
        return metrics, pred_norm, pred_raw
    
    def generate_report(self, metrics, output_dir=None):
        """Generar reporte de evaluación"""
        report_lines = []
        report_lines.append("Random Forest Evaluation Report")
        report_lines.append("=" * 50)
        report_lines.append("Timestamp: {}".format(datetime.now().isoformat()))
        report_lines.append("Models directory: {}".format(self.models_dir))
        report_lines.append("")
        
        # Métricas por parámetro
        for param in GAIT_KEYS:
            m = metrics[param]
            report_lines.append("Parameter: {}".format(param))
            report_lines.append("-" * 30)
            report_lines.append("Physical space metrics:")
            report_lines.append("  R² Score:    {:.4f}".format(m['r2_raw']))
            report_lines.append("  RMSE:        {:.6f}".format(m['rmse_raw']))
            report_lines.append("  MAE:         {:.6f}".format(m['mae_raw']))
            report_lines.append("  MAPE:        {:.2f}%".format(m['mape_raw']))
            report_lines.append("")
            report_lines.append("Normalized space metrics:")
            report_lines.append("  R² Score:    {:.4f}".format(m['r2_norm']))
            report_lines.append("  RMSE:        {:.6f}".format(m['rmse_norm']))
            report_lines.append("  MAE:         {:.6f}".format(m['mae_norm']))
            report_lines.append("")
        
        # Métricas promedio
        avg_r2 = np.mean([metrics[p]['r2_raw'] for p in GAIT_KEYS])
        avg_rmse = np.mean([metrics[p]['rmse_raw'] for p in GAIT_KEYS])
        avg_mape = np.mean([metrics[p]['mape_raw'] for p in GAIT_KEYS])
        
        report_lines.append("Average Performance:")
        report_lines.append("  R² Score:    {:.4f}".format(avg_r2))
        report_lines.append("  RMSE:        {:.6f}".format(avg_rmse))
        report_lines.append("  MAPE:        {:.2f}%".format(avg_mape))
        
        report_text = "\n".join(report_lines)
        
        # Guardar reporte si se especifica directorio
        if output_dir:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            report_path = os.path.join(output_dir, "evaluation_report.txt")
            with open(report_path, 'w') as f:
                f.write(report_text)
            
            if self.verbose:
                print("[INFO] Reporte guardado en: {}".format(report_path))
        
        return report_text
    
    def save_predictions(self, df_original, pred_raw, output_dir):
        """Guardar predicciones en CSV"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Crear DataFrame con predicciones
        df_pred = df_original.copy()
        
        for param in GAIT_KEYS:
            df_pred['{}_predicted'.format(param)] = pred_raw[param]
            df_pred['{}_error'.format(param)] = df_pred[param] - pred_raw[param]
            df_pred['{}_error_abs'.format(param)] = np.abs(df_pred['{}_error'.format(param)])
        
        # Guardar
        pred_path = os.path.join(output_dir, "predictions.csv")
        df_pred.to_csv(pred_path, index=False)
        
        if self.verbose:
            print("[INFO] Predicciones guardadas en: {}".format(pred_path))
        
        return pred_path
    
    def plot_results(self, y_raw_dict, pred_raw, output_dir):
        """Generar gráficos de evaluación"""
        if not HAS_MATPLOTLIB:
            print("[WARN] matplotlib no disponible - omitiendo gráficos")
            return
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Configuración de matplotlib
        plt.style.use('default')
        
        # Gráfico de correlación para cada parámetro
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.flatten()
        
        for i, param in enumerate(GAIT_KEYS):
            ax = axes[i]
            
            y_true = y_raw_dict[param]
            y_pred = pred_raw[param]
            
            # Scatter plot
            ax.scatter(y_true, y_pred, alpha=0.6, s=20)
            
            # Línea ideal
            min_val = min(y_true.min(), y_pred.min())
            max_val = max(y_true.max(), y_pred.max())
            ax.plot([min_val, max_val], [min_val, max_val], 'r--', lw=2, label='Ideal')
            
            # Métricas en el título
            r2 = r2_score(y_true, y_pred)
            rmse = np.sqrt(mean_squared_error(y_true, y_pred))
            
            ax.set_title('{}\nR²={:.3f}, RMSE={:.4f}'.format(param, r2, rmse))
            ax.set_xlabel('True Values')
            ax.set_ylabel('Predicted Values')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        # Ocultar subplot extra
        axes[-1].set_visible(False)
        
        plt.tight_layout()
        correlation_path = os.path.join(output_dir, "correlation_plots.png")
        plt.savefig(correlation_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        if self.verbose:
            print("[INFO] Gráficos de correlación guardados en: {}".format(correlation_path))
        
        # Gráfico de distribución de errores
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.flatten()
        
        for i, param in enumerate(GAIT_KEYS):
            ax = axes[i]
            
            y_true = y_raw_dict[param]
            y_pred = pred_raw[param]
            errors = y_true - y_pred
            
            # Histograma de errores
            ax.hist(errors, bins=30, alpha=0.7, density=True)
            ax.axvline(errors.mean(), color='red', linestyle='--', 
                      label='Mean: {:.4f}'.format(errors.mean()))
            ax.axvline(0, color='black', linestyle='-', alpha=0.8)
            
            ax.set_title('{}\nStd: {:.4f}'.format(param, errors.std()))
            ax.set_xlabel('Prediction Error')
            ax.set_ylabel('Density')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        axes[-1].set_visible(False)
        
        plt.tight_layout()
        error_path = os.path.join(output_dir, "error_distribution.png")
        plt.savefig(error_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        if self.verbose:
            print("[INFO] Gráficos de errores guardados en: {}".format(error_path))

def main():
    parser = argparse.ArgumentParser(description='Evaluación de modelos Random Forest para marcha adaptativa')
    parser.add_argument('--models', required=True,
                        help='Directorio con modelos Random Forest entrenados')
    parser.add_argument('--data', nargs='+', required=True,
                        help='Archivos CSV de test (soporta wildcards)')
    parser.add_argument('--output', default='results',
                        help='Directorio de salida para resultados (default: results)')
    parser.add_argument('--plot', action='store_true',
                        help='Generar gráficos de evaluación')
    parser.add_argument('--no-verbose', action='store_true',
                        help='Ejecutar en modo silencioso')
    
    args = parser.parse_args()
    
    verbose = not args.no_verbose
    
    # Expandir wildcards en archivos de datos
    data_files = []
    for pattern in args.data:
        matches = glob.glob(pattern)
        if matches:
            data_files.extend(matches)
        else:
            data_files.append(pattern)
    
    if not data_files:
        print("[ERROR] No se encontraron archivos de datos")
        return 1
    
    try:
        # Crear evaluador
        evaluator = RandomForestEvaluator(args.models, verbose=verbose)
        
        # Cargar modelos
        evaluator.load_models()
        
        # Cargar datos de test
        df = evaluator.load_test_data(data_files)
        
        # Preparar datos
        X, y_dict, y_raw_dict, df_clean = evaluator.prepare_data(df)
        
        # Evaluar modelos
        metrics, pred_norm, pred_raw = evaluator.evaluate_models(X, y_dict, y_raw_dict)
        
        # Generar reporte
        report = evaluator.generate_report(metrics, args.output)
        
        if verbose:
            print("\n" + "=" * 50)
            print("RESUMEN DE EVALUACIÓN")
            print("=" * 50)
            print(report)
        
        # Guardar predicciones
        evaluator.save_predictions(df_clean, pred_raw, args.output)
        
        # Generar gráficos si se solicita
        if args.plot:
            evaluator.plot_results(y_raw_dict, pred_raw, args.output)
        
        print("\n[SUCCESS] Evaluación completada")
        print("Resultados guardados en: {}".format(args.output))
        
        return 0
        
    except Exception as e:
        print("[ERROR] Error durante evaluación: {}".format(e))
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
