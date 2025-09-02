#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Analizador de Datos del Monitor NAO
===================================

Script para analizar los datos CSV generados por monitor_live_gait_params_local.py
y extraer los mejores parámetros de caminata.

Uso:
    python analyze_nao_gait_data.py gait_params_log.csv

Compatible con Python 2.7 y 3.x
"""

import sys
import csv
import os
from datetime import datetime

def load_csv_data(csv_path):
    """Cargar datos del CSV (compatible Python 2/3)"""
    print("📁 Cargando datos desde: {}".format(csv_path))
    
    if not os.path.exists(csv_path):
        print("❌ Error: Archivo no encontrado: {}".format(csv_path))
        return None
    
    data = []
    try:
        # Python 2/3 compatible CSV reading
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        
        print("✅ Cargados {} registros".format(len(data)))
        return data
        
    except Exception as e:
        print("❌ Error leyendo CSV: {}".format(e))
        return None

def filter_good_walking_data(data):
    """Filtrar datos de caminata estable"""
    print("\n🔍 Filtrando datos de caminata estable...")
    
    good_data = []
    total_walking = 0
    
    for row in data:
        try:
            # Solo datos donde está caminando
            walking = int(row.get('Walking', 0))
            if walking != 1:
                continue
                
            total_walking += 1
            
            # Verificar que tiene datos de parámetros
            max_step_x = row.get('MaxStepX', 'N/A')
            max_step_y = row.get('MaxStepY', 'N/A')
            if max_step_x == 'N/A' or max_step_y == 'N/A':
                continue
            
            # Convertir a float para validación
            try:
                fsr_total = float(row.get('FSR_Total', 0))
                acc_x = float(row.get('AccX', 0)) if row.get('AccX') else 0
                acc_y = float(row.get('AccY', 0)) if row.get('AccY') else 0
                angle_x = float(row.get('AngleX', 0)) if row.get('AngleX') else 0
                angle_y = float(row.get('AngleY', 0)) if row.get('AngleY') else 0
                
                # Filtros de estabilidad
                if (fsr_total > 2.0 and                    # Peso detectado
                    abs(acc_x) < 3.0 and                  # Aceleración suave
                    abs(acc_y) < 3.0 and
                    abs(angle_x) < 0.15 and               # Ángulos estables (~8°)
                    abs(angle_y) < 0.15):
                    
                    good_data.append(row)
                    
            except (ValueError, TypeError):
                # Skip rows with invalid sensor data
                continue
                
        except Exception:
            continue
    
    print("📊 Registros de caminata: {} / {}".format(total_walking, len(data)))
    print("✅ Registros estables: {} / {}".format(len(good_data), total_walking))
    
    return good_data

def analyze_gait_parameters(data):
    """Analizar parámetros de gait para encontrar valores óptimos"""
    print("\n📈 Analizando parámetros de gait...")
    
    if not data:
        print("❌ No hay datos para analizar")
        return None
    
    # Parámetros a analizar
    param_names = ['MaxStepX', 'MaxStepY', 'MaxStepTheta', 'StepHeight', 'Frequency']
    param_stats = {}
    
    for param in param_names:
        values = []
        
        for row in data:
            try:
                value = row.get(param, 'N/A')
                if value != 'N/A' and value != '':
                    values.append(float(value))
            except (ValueError, TypeError):
                continue
        
        if values:
            param_stats[param] = {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'median': sorted(values)[len(values) // 2]
            }
        else:
            param_stats[param] = None
    
    return param_stats

def analyze_sensor_stability(data):
    """Analizar estabilidad de sensores"""
    print("\n⚖️ Analizando estabilidad de sensores...")
    
    if not data:
        return None
    
    sensor_stats = {}
    sensor_names = ['FSR_Total', 'AccX', 'AccY', 'AngleX', 'AngleY']
    
    for sensor in sensor_names:
        values = []
        
        for row in data:
            try:
                value = row.get(sensor, '')
                if value != '' and value != 'N/A':
                    values.append(float(value))
            except (ValueError, TypeError):
                continue
        
        if values:
            # Calcular varianza (estabilidad)
            avg = sum(values) / len(values)
            variance = sum((x - avg) ** 2 for x in values) / len(values)
            
            sensor_stats[sensor] = {
                'count': len(values),
                'avg': avg,
                'variance': variance,
                'stability': 'HIGH' if variance < 0.1 else 'MEDIUM' if variance < 1.0 else 'LOW'
            }
    
    return sensor_stats

def print_analysis_report(param_stats, sensor_stats, good_data_count):
    """Imprimir reporte de análisis"""
    print("\n" + "=" * 80)
    print("📋 REPORTE DE ANÁLISIS - PARÁMETROS ÓPTIMOS DE GAIT")
    print("=" * 80)
    
    if not param_stats:
        print("❌ No se encontraron parámetros válidos para analizar")
        return
    
    print("\n🎯 PARÁMETROS RECOMENDADOS (basados en {} muestras estables):".format(good_data_count))
    print("-" * 60)
    
    for param, stats in param_stats.items():
        if stats:
            print("📏 {:<15}: {:.4f} (rango: {:.4f} - {:.4f}, {} muestras)".format(
                param, stats['avg'], stats['min'], stats['max'], stats['count']
            ))
        else:
            print("📏 {:<15}: Sin datos válidos".format(param))
    
    print("\n⚖️ ESTABILIDAD DE SENSORES:")
    print("-" * 60)
    
    if sensor_stats:
        for sensor, stats in sensor_stats.items():
            if stats:
                print("🔧 {:<10}: {} (varianza: {:.4f})".format(
                    sensor, stats['stability'], stats['variance']
                ))
    
    print("\n✅ CONFIGURACIÓN RECOMENDADA PARA EL NAO:")
    print("-" * 60)
    
    if param_stats.get('MaxStepX'):
        print("MaxStepX = {:.4f}".format(param_stats['MaxStepX']['avg']))
    if param_stats.get('MaxStepY'):
        print("MaxStepY = {:.4f}".format(param_stats['MaxStepY']['avg']))
    if param_stats.get('MaxStepTheta'):
        print("MaxStepTheta = {:.4f}".format(param_stats['MaxStepTheta']['avg']))
    if param_stats.get('StepHeight'):
        print("StepHeight = {:.4f}".format(param_stats['StepHeight']['avg']))
    if param_stats.get('Frequency'):
        print("Frequency = {:.4f}".format(param_stats['Frequency']['avg']))
    
    print("\n💡 NOTAS:")
    print("- Estos valores son promedios de caminata estable detectada")
    print("- Usar como punto de partida para optimización")
    print("- Ajustar según condiciones específicas del robot/superficie")

def save_optimal_params(param_stats, output_path):
    """Guardar parámetros óptimos en archivo"""
    if not param_stats:
        return
        
    try:
        with open(output_path, 'w') as f:
            f.write("# Parámetros óptimos de gait - generados automáticamente\n")
            f.write("# Fecha: {}\n\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            for param, stats in param_stats.items():
                if stats:
                    f.write("{} = {:.6f}  # avg from {} samples, range: {:.4f}-{:.4f}\n".format(
                        param, stats['avg'], stats['count'], stats['min'], stats['max']
                    ))
        
        print("\n💾 Parámetros guardados en: {}".format(output_path))
        
    except Exception as e:
        print("❌ Error guardando parámetros: {}".format(e))

def main():
    """Función principal"""
    if len(sys.argv) != 2:
        print("❌ Uso: python {} <archivo_csv>".format(sys.argv[0]))
        print("Ejemplo: python {} gait_params_log.csv".format(sys.argv[0]))
        sys.exit(1)
    
    csv_path = sys.argv[1]
    
    print("🤖 ANALIZADOR DE DATOS DEL MONITOR NAO")
    print("=" * 50)
    
    # Cargar datos
    data = load_csv_data(csv_path)
    if not data:
        sys.exit(1)
    
    # Filtrar datos de caminata estable
    good_data = filter_good_walking_data(data)
    
    # Analizar parámetros
    param_stats = analyze_gait_parameters(good_data)
    sensor_stats = analyze_sensor_stability(good_data)
    
    # Mostrar reporte
    print_analysis_report(param_stats, sensor_stats, len(good_data))
    
    # Guardar parámetros óptimos
    output_path = "optimal_gait_params.txt"
    save_optimal_params(param_stats, output_path)
    
    print("\n🎉 Análisis completado!")

if __name__ == "__main__":
    main()
