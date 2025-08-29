#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyze_logs.py - Análisis de logs CSV de adaptive_walk_randomforest.py

Genera estadísticas y visualizaciones de los datos de adaptación recolectados.

Uso:
    python analyze_logs.py --log-dir logs --output-dir analysis
"""

from __future__ import print_function
import argparse
import os
import sys
import glob
import pandas as pd
import numpy as np
from datetime import datetime

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("[WARN] matplotlib/seaborn no disponibles, sin gráficos")

FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_KEYS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

def load_logs(log_dir):
    """Cargar logs CSV"""
    pattern = os.path.join(log_dir, "adaptive_data_*.csv")
    csv_files = glob.glob(pattern)
    
    if not csv_files:
        raise ValueError("No se encontraron CSVs en {}".format(log_dir))
    
    dfs = []
    for csv_file in sorted(csv_files):
        try:
            df = pd.read_csv(csv_file)
            df['source_file'] = os.path.basename(csv_file)
            dfs.append(df)
        except Exception as e:
            print("[WARN] Error cargando {}: {}".format(csv_file, e))
    
    if not dfs:
        raise ValueError("No se pudieron cargar CSVs válidos")
    
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Convertir timestamp a datetime
    combined_df['dt'] = pd.to_datetime(combined_df['timestamp'], unit='s')
    
    return combined_df

def generate_statistics(df, output_dir):
    """Generar estadísticas descriptivas"""
    stats_file = os.path.join(output_dir, "statistics.txt")
    
    with open(stats_file, 'w') as f:
        f.write("Análisis de Logs de Adaptación\n")
        f.write("=" * 40 + "\n")
        f.write("Fecha análisis: {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        f.write("\n")
        
        # Estadísticas generales
        f.write("ESTADÍSTICAS GENERALES\n")
        f.write("-" * 20 + "\n")
        f.write("Total muestras: {}\n".format(len(df)))
        f.write("Muestras exitosas: {} ({:.1f}%)\n".format(
            df['success'].sum(), 100.0 * df['success'].mean()))
        f.write("Período: {} - {}\n".format(df['dt'].min(), df['dt'].max()))
        f.write("Duración: {}\n".format(df['dt'].max() - df['dt'].min()))
        f.write("\n")
        
        # Tiempo de inferencia
        f.write("TIEMPO DE INFERENCIA\n")
        f.write("-" * 20 + "\n")
        f.write("Promedio: {:.2f} ms\n".format(df['inference_time_ms'].mean()))
        f.write("Mediana: {:.2f} ms\n".format(df['inference_time_ms'].median()))
        f.write("P95: {:.2f} ms\n".format(df['inference_time_ms'].quantile(0.95)))
        f.write("Máximo: {:.2f} ms\n".format(df['inference_time_ms'].max()))
        f.write("\n")
        
        # Estadísticas por parámetro aplicado
        df_success = df[df['success'] == True]
        if len(df_success) > 0:
            f.write("PARÁMETROS APLICADOS (solo muestras exitosas)\n")
            f.write("-" * 20 + "\n")
            for param in GAIT_KEYS:
                col = 'applied_{}'.format(param)
                if col in df_success.columns:
                    values = df_success[col]
                    f.write("{}:\n".format(param))
                    f.write("  Min: {:.4f}\n".format(values.min()))
                    f.write("  Max: {:.4f}\n".format(values.max()))
                    f.write("  Media: {:.4f}\n".format(values.mean()))
                    f.write("  Std: {:.4f}\n".format(values.std()))
                    f.write("\n")
        
        # Estadísticas de features
        f.write("FEATURES (muestras exitosas)\n")
        f.write("-" * 20 + "\n")
        for feat in FEAT_ORDER[:10]:  # Solo primeras 10 para no sobrecargar
            col = 'feat_{}'.format(feat)
            if col in df_success.columns:
                values = df_success[col]
                f.write("{}:\n".format(feat))
                f.write("  Min: {:.4f}, Max: {:.4f}, Media: {:.4f}\n".format(
                    values.min(), values.max(), values.mean()))
    
    print("[INFO] Estadísticas guardadas: {}".format(stats_file))

def plot_time_series(df, output_dir):
    """Generar gráficos de series temporales"""
    if not PLOTTING_AVAILABLE:
        return
    
    # Configurar estilo
    plt.style.use('default')
    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    fig.suptitle('Análisis Temporal de Adaptación', fontsize=16)
    
    # 1. Tasa de éxito vs tiempo
    df_resampled = df.set_index('dt').resample('1T')['success'].mean()  # Por minuto
    axes[0, 0].plot(df_resampled.index, df_resampled.values * 100, 'b-', alpha=0.7)
    axes[0, 0].set_title('Tasa de Éxito (%)')
    axes[0, 0].set_ylabel('Éxito (%)')
    axes[0, 0].grid(True, alpha=0.3)
    
    # 2. Tiempo de inferencia vs tiempo
    df_inf = df.set_index('dt').resample('1T')['inference_time_ms'].mean()
    axes[0, 1].plot(df_inf.index, df_inf.values, 'r-', alpha=0.7)
    axes[0, 1].set_title('Tiempo de Inferencia (ms)')
    axes[0, 1].set_ylabel('Tiempo (ms)')
    axes[0, 1].grid(True, alpha=0.3)
    
    # 3-6. Parámetros aplicados vs tiempo (solo exitosos)
    df_success = df[df['success'] == True].copy()
    if len(df_success) > 0:
        plot_idx = [(1, 0), (1, 1), (2, 0), (2, 1)]
        for i, param in enumerate(GAIT_KEYS[:4]):
            if i >= len(plot_idx):
                break
            row, col = plot_idx[i]
            param_col = 'applied_{}'.format(param)
            if param_col in df_success.columns:
                df_param = df_success.set_index('dt')[param_col].resample('1T').mean()
                axes[row, col].plot(df_param.index, df_param.values, 'g-', alpha=0.7)
                axes[row, col].set_title('Parámetro: {}'.format(param))
                axes[row, col].set_ylabel(param)
                axes[row, col].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'time_series.png'), dpi=150, bbox_inches='tight')
    plt.close()
    
    print("[INFO] Gráfico de series temporales: time_series.png")

def plot_distributions(df, output_dir):
    """Generar histogramas de distribuciones"""
    if not PLOTTING_AVAILABLE:
        return
    
    df_success = df[df['success'] == True].copy()
    if len(df_success) == 0:
        return
    
    # Distribuciones de parámetros aplicados
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle('Distribuciones de Parámetros Aplicados', fontsize=16)
    
    for i, param in enumerate(GAIT_KEYS):
        row, col = i // 3, i % 3
        if row >= 2:
            break
        
        param_col = 'applied_{}'.format(param)
        if param_col in df_success.columns:
            values = df_success[param_col].dropna()
            axes[row, col].hist(values, bins=30, alpha=0.7, edgecolor='black')
            axes[row, col].set_title(param)
            axes[row, col].set_xlabel('Valor')
            axes[row, col].set_ylabel('Frecuencia')
            axes[row, col].grid(True, alpha=0.3)
    
    # Remover subplot vacío si hay uno
    if len(GAIT_KEYS) < 6:
        fig.delaxes(axes[1, 2])
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'distributions.png'), dpi=150, bbox_inches='tight')
    plt.close()
    
    print("[INFO] Gráfico de distribuciones: distributions.png")

def plot_correlations(df, output_dir):
    """Generar matriz de correlaciones"""
    if not PLOTTING_AVAILABLE:
        return
    
    df_success = df[df['success'] == True].copy()
    if len(df_success) == 0:
        return
    
    # Seleccionar columnas de interés
    feature_cols = ['feat_{}'.format(name) for name in FEAT_ORDER[:12]]  # Primeras 12 features
    param_cols = ['applied_{}'.format(param) for param in GAIT_KEYS]
    
    cols_to_use = [col for col in feature_cols + param_cols if col in df_success.columns]
    
    if len(cols_to_use) < 2:
        return
    
    # Calcular correlaciones
    corr_matrix = df_success[cols_to_use].corr()
    
    # Plot
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_matrix, annot=False, cmap='coolwarm', center=0, 
                square=True, cbar_kws={'shrink': 0.8})
    plt.title('Matriz de Correlaciones (Features vs Parámetros)', fontsize=14)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'correlations.png'), dpi=150, bbox_inches='tight')
    plt.close()
    
    print("[INFO] Matriz de correlaciones: correlations.png")

def main():
    parser = argparse.ArgumentParser(description='Analizar logs CSV de adaptación')
    parser.add_argument('--log-dir', default='logs', help='Directorio con CSVs')
    parser.add_argument('--output-dir', default='analysis', help='Directorio de salida')
    
    args = parser.parse_args()
    
    try:
        # Crear directorio de salida
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)
        
        # Cargar datos
        print("[INFO] Cargando logs desde: {}".format(args.log_dir))
        df = load_logs(args.log_dir)
        print("[INFO] Cargadas {} muestras".format(len(df)))
        
        # Generar análisis
        generate_statistics(df, args.output_dir)
        
        if PLOTTING_AVAILABLE:
            plot_time_series(df, args.output_dir)
            plot_distributions(df, args.output_dir)
            plot_correlations(df, args.output_dir)
        
        print("\n[OK] Análisis completado")
        print("Resultados en: {}".format(args.output_dir))
        
        return 0
        
    except Exception as e:
        print("[ERROR] {}".format(e))
        return 1

if __name__ == '__main__':
    sys.exit(main())
