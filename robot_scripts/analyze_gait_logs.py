#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyze_gait_logs.py - Análisis Consolidado de Logs de Gait NAO
=============================================================

ARCHIVO CONSOLIDADO que combina:
- analyze_logs.py (análisis general de logs CSV)  
- analyze_nao_gait_data.py (análisis específico de gait)

Funcionalidades:
- Análisis de logs CSV desde carpeta logs/ específica
- Estadísticas de parámetros de gait 
- Detección de períodos de caminata estable
- Visualizaciones (si matplotlib disponible)
- Exportación de resultados optimizados

Uso:
    python analyze_gait_logs.py --log-dir logs --output-dir analysis
    python analyze_gait_logs.py --log-dir logs --best-params-only
"""

from __future__ import print_function
import argparse
import os
import sys
import glob
import csv
from datetime import datetime

# Python 2/3 compatibility
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("[WARN] pandas no disponible, análisis básico solamente")

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("[WARN] matplotlib/seaborn no disponibles, sin gráficos")

# Configuración de features esperadas en logs NAO
GAIT_PARAMS = ['MaxStepX', 'MaxStepY', 'MaxStepTheta', 'StepHeight', 'Frequency']
SENSOR_PARAMS = ['FSR_Left', 'FSR_Right', 'FSR_Total', 'AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'AngleX', 'AngleY']
EXPECTED_COLUMNS = ['timestamp', 'Walking'] + GAIT_PARAMS + SENSOR_PARAMS

def load_csv_data_basic(csv_path):
    """Cargar datos CSV básico (compatible Python 2/3)"""
    print("📁 Cargando: {}".format(os.path.basename(csv_path)))
    
    if not os.path.exists(csv_path):
        print("❌ Archivo no encontrado: {}".format(csv_path))
        return None
    
    data = []
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        
        print("✅ {} registros cargados".format(len(data)))
        return data
        
    except Exception as e:
        print("❌ Error leyendo CSV: {}".format(e))
        return None

def load_logs_directory(log_dir):
    """Cargar todos los CSVs del directorio de logs"""
    print("\n🔍 Buscando logs en: {}".format(log_dir))
    
    if not os.path.exists(log_dir):
        raise ValueError("Directorio no existe: {}".format(log_dir))
    
    # Buscar archivos CSV
    csv_files = []
    for ext in ['*.csv', '*.CSV']:
        pattern = os.path.join(log_dir, ext)
        csv_files.extend(glob.glob(pattern))
    
    if not csv_files:
        raise ValueError("No se encontraron archivos CSV en {}".format(log_dir))
    
    print("📊 Encontrados {} archivos CSV".format(len(csv_files)))
    
    # Cargar todos los datos
    all_data = []
    valid_files = 0
    
    for csv_file in sorted(csv_files):
        data = load_csv_data_basic(csv_file)
        if data:
            # Agregar información del archivo fuente
            for row in data:
                row['source_file'] = os.path.basename(csv_file)
            all_data.extend(data)
            valid_files += 1
    
    print("✅ {} archivos válidos, {} registros totales".format(valid_files, len(all_data)))
    return all_data

def filter_walking_data(data):
    """Filtrar solo datos durante caminata activa"""
    print("\n🚶 Filtrando datos de caminata activa...")
    
    walking_data = []
    total_walking = 0
    
    for row in data:
        try:
            walking = row.get('Walking', '0')
            if walking and str(walking).strip() in ['1', 'True', 'true']:
                walking_data.append(row)
                total_walking += 1
        except:
            continue
    
    print("✅ {}/{} registros durante caminata ({:.1f}%)".format(
        len(walking_data), len(data), 
        100.0 * len(walking_data) / len(data) if data else 0
    ))
    
    return walking_data

def analyze_gait_parameters(data):
    """Analizar parámetros de gait (versión básica sin pandas)"""
    print("\n📊 Analizando parámetros de gait...")
    
    if not data:
        print("❌ No hay datos para analizar")
        return {}
    
    # Recopilar valores por parámetro
    param_values = {param: [] for param in GAIT_PARAMS}
    
    for row in data:
        for param in GAIT_PARAMS:
            try:
                value = row.get(param)
                if value and value.strip():
                    param_values[param].append(float(value))
            except (ValueError, AttributeError):
                continue
    
    # Calcular estadísticas básicas
    stats = {}
    for param, values in param_values.items():
        if values:
            stats[param] = {
                'count': len(values),
                'mean': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'unique_values': len(set(values))
            }
            
            # Calcular desviación estándar manualmente
            mean_val = stats[param]['mean']
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            stats[param]['std'] = variance ** 0.5
    
    # Mostrar resultados
    print("\n📈 ESTADÍSTICAS DE PARÁMETROS:")
    print("-" * 50)
    for param, stat in stats.items():
        if stat:
            print("{}:".format(param))
            print("  Registros: {}".format(stat['count']))
            print("  Media: {:.4f} ± {:.4f}".format(stat['mean'], stat['std']))
            print("  Rango: [{:.4f}, {:.4f}]".format(stat['min'], stat['max']))
            print("  Valores únicos: {}".format(stat['unique_values']))
            print()
    
    return stats

def find_stable_periods(data, stability_threshold=0.01):
    """Encontrar períodos de caminata estable"""
    print("\n🎯 Buscando períodos de caminata estable...")
    
    if not data:
        return []
    
    stable_periods = []
    current_period = []
    
    for i, row in enumerate(data):
        try:
            # Verificar si tiene valores válidos de FSR
            fsr_total = row.get('FSR_Total', '')
            if fsr_total and float(fsr_total) > 0.5:  # Umbral mínimo de presión
                current_period.append(row)
            else:
                # Fin del período, evaluar si es estable
                if len(current_period) >= 5:  # Mínimo 5 registros
                    stable_periods.append(current_period)
                current_period = []
        except:
            current_period = []
    
    # Agregar último período si existe
    if len(current_period) >= 5:
        stable_periods.append(current_period)
    
    print("✅ Encontrados {} períodos estables".format(len(stable_periods)))
    return stable_periods

def extract_best_parameters(stable_periods):
    """Extraer mejores parámetros de períodos estables"""
    print("\n⭐ Extrayendo mejores parámetros...")
    
    if not stable_periods:
        print("❌ No hay períodos estables para analizar")
        return {}
    
    best_params = {}
    
    # Analizar cada período y encontrar el más estable
    best_period = None
    best_stability = 0
    
    for period in stable_periods:
        # Calcular estabilidad basada en FSR consistente
        fsr_values = []
        for row in period:
            try:
                fsr_total = float(row.get('FSR_Total', 0))
                fsr_values.append(fsr_total)
            except:
                continue
        
        if fsr_values:
            # Estabilidad = 1 / (desviación estándar + 0.1)
            mean_fsr = sum(fsr_values) / len(fsr_values)
            variance = sum((x - mean_fsr) ** 2 for x in fsr_values) / len(fsr_values)
            std_fsr = variance ** 0.5
            stability = 1.0 / (std_fsr + 0.1)
            
            if stability > best_stability:
                best_stability = stability
                best_period = period
    
    if best_period:
        print("✅ Mejor período: {} registros, estabilidad: {:.3f}".format(
            len(best_period), best_stability))
        
        # Extraer parámetros promedio del mejor período
        for param in GAIT_PARAMS:
            values = []
            for row in best_period:
                try:
                    value = float(row.get(param, 0))
                    values.append(value)
                except:
                    continue
            
            if values:
                best_params[param] = sum(values) / len(values)
        
        print("\n🏆 MEJORES PARÁMETROS IDENTIFICADOS:")
        print("-" * 40)
        for param, value in best_params.items():
            print("{}: {:.4f}".format(param, value))
    
    return best_params

def generate_summary_report(data, stats, best_params, output_dir):
    """Generar reporte resumen"""
    if not output_dir:
        output_dir = "analysis"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(output_dir, "gait_analysis_report_{}.txt".format(timestamp))
    
    try:
        with open(report_file, 'w') as f:
            f.write("REPORTE DE ANÁLISIS DE GAIT NAO\n")
            f.write("=" * 40 + "\n")
            f.write("Generado: {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            f.write("Total registros: {}\n\n".format(len(data)))
            
            f.write("ESTADÍSTICAS DE PARÁMETROS:\n")
            f.write("-" * 30 + "\n")
            for param, stat in stats.items():
                if stat:
                    f.write("{}:\n".format(param))
                    f.write("  Media: {:.4f} ± {:.4f}\n".format(stat['mean'], stat['std']))
                    f.write("  Rango: [{:.4f}, {:.4f}]\n".format(stat['min'], stat['max']))
                    f.write("\n")
            
            if best_params:
                f.write("MEJORES PARÁMETROS:\n")
                f.write("-" * 20 + "\n")
                for param, value in best_params.items():
                    f.write("{}: {:.4f}\n".format(param, value))
        
        print("📄 Reporte guardado: {}".format(report_file))
        
    except Exception as e:
        print("❌ Error generando reporte: {}".format(e))

def main():
    parser = argparse.ArgumentParser(description='Análisis consolidado de logs de gait NAO')
    parser.add_argument('--log-dir', default='logs', help='Directorio con archivos CSV')
    parser.add_argument('--output-dir', default='analysis', help='Directorio de salida')
    parser.add_argument('--best-params-only', action='store_true', 
                        help='Solo mostrar mejores parámetros')
    parser.add_argument('--stability-threshold', type=float, default=0.01,
                        help='Umbral de estabilidad para filtrado')
    
    args = parser.parse_args()
    
    try:
        print("🤖 ANÁLISIS CONSOLIDADO DE LOGS DE GAIT NAO")
        print("=" * 45)
        
        # Cargar datos
        all_data = load_logs_directory(args.log_dir)
        
        # Filtrar datos de caminata
        walking_data = filter_walking_data(all_data)
        
        if not walking_data:
            print("❌ No se encontraron datos de caminata válidos")
            return
        
        # Análisis estadístico
        stats = analyze_gait_parameters(walking_data)
        
        # Encontrar períodos estables
        stable_periods = find_stable_periods(walking_data, args.stability_threshold)
        
        # Extraer mejores parámetros
        best_params = extract_best_parameters(stable_periods)
        
        if args.best_params_only and best_params:
            print("\n🎯 SOLO MEJORES PARÁMETROS:")
            print("-" * 30)
            for param, value in best_params.items():
                print("{}: {:.6f}".format(param, value))
        
        # Generar reporte
        generate_summary_report(walking_data, stats, best_params, args.output_dir)
        
        print("\n✅ Análisis completado exitosamente")
        
    except Exception as e:
        print("❌ Error en análisis: {}".format(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
