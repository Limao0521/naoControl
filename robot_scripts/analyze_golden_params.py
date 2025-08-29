#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyze_golden_params.py - Analiza parámetros dorados capturados

Analiza todos los archivos JSON de parámetros dorados encontrados
y genera estadísticas para usar en el sistema de control.
"""

from __future__ import print_function
import os
import json
import pandas as pd
import numpy as np
from collections import defaultdict
import argparse

def analyze_golden_params(golden_dir="golden_params"):
    """Analizar todos los parámetros dorados encontrados"""
    
    if not os.path.exists(golden_dir):
        print("Directorio {} no existe".format(golden_dir))
        return
    
    # Cargar todos los JSONs
    json_files = [f for f in os.listdir(golden_dir) if f.startswith('golden_params_') and f.endswith('.json')]
    
    if not json_files:
        print("No se encontraron parámetros dorados en {}".format(golden_dir))
        return
    
    golden_data = []
    for json_file in sorted(json_files):
        try:
            with open(os.path.join(golden_dir, json_file), 'r') as f:
                data = json.load(f)
                golden_data.append(data)
        except Exception as e:
            print("Error cargando {}: {}".format(json_file, e))
    
    if not golden_data:
        print("No se pudieron cargar datos válidos")
        return
    
    print("🏆 ANÁLISIS DE PARÁMETROS DORADOS")
    print("=" * 40)
    print("Total capturas: {}".format(len(golden_data)))
    
    # Extraer parámetros de gait
    gait_params = defaultdict(list)
    stability_scores = []
    durations = []
    
    for entry in golden_data:
        stability_scores.append(entry.get('stability_score', 0))
        durations.append(entry.get('duration_seconds', 0))
        
        gait_parameters = entry.get('gait_parameters', {})
        for param, value in gait_parameters.items():
            if isinstance(value, (int, float)):
                gait_params[param].append(value)
    
    # Estadísticas por parámetro
    print("\n📊 ESTADÍSTICAS DE PARÁMETROS ÓPTIMOS:")
    print("-" * 40)
    
    optimal_params = {}
    for param, values in gait_params.items():
        if values:  # Solo si hay valores
            mean_val = np.mean(values)
            std_val = np.std(values)
            min_val = np.min(values)
            max_val = np.max(values)
            
            print("{}:".format(param))
            print("  Media: {:.4f} ± {:.4f}".format(mean_val, std_val))
            print("  Rango: [{:.4f}, {:.4f}]".format(min_val, max_val))
            
            # Valor óptimo = media de las mejores capturas
            optimal_params[param] = mean_val
    
    # Encontrar la mejor captura individual
    if stability_scores:
        best_idx = np.argmax(stability_scores)
        best_capture = golden_data[best_idx]
        
        print("\n🥇 MEJOR CAPTURA INDIVIDUAL:")
        print("-" * 30)
        print("Estabilidad: {:.3f}".format(best_capture.get('stability_score', 0)))
        print("Duración: {:.1f}s".format(best_capture.get('duration_seconds', 0)))
        print("Fecha: {}".format(best_capture.get('datetime', 'N/A')))
        print("Parámetros:")
        for param, value in best_capture.get('gait_parameters', {}).items():
            if isinstance(value, (int, float)):
                print("  {}: {:.4f}".format(param, value))
    
    # Parámetros promedio optimizados
    if optimal_params:
        print("\n⭐ PARÁMETROS PROMEDIO OPTIMIZADOS:")
        print("-" * 35)
        for param, value in optimal_params.items():
            print("{}: {:.4f}".format(param, value))
        
        # Generar configuración para usar
        print("\n🔧 CONFIGURACIÓN PARA USAR EN CONTROL SERVER:")
        print("-" * 50)
        print("GRASS_OPTIMAL_PARAMS = {")
        for param, value in optimal_params.items():
            print("    '{}': {:.4f},".format(param, value))
        print("}")
        
        # Generar archivo de configuración
        config_file = os.path.join(golden_dir, "optimal_grass_params.json")
        config_data = {
            'optimal_params': optimal_params,
            'statistics': {
                'total_captures': len(golden_data),
                'avg_stability': np.mean(stability_scores) if stability_scores else 0,
                'avg_duration': np.mean(durations) if durations else 0,
                'best_stability': np.max(stability_scores) if stability_scores else 0
            },
            'generated_at': pd.Timestamp.now().isoformat(),
            'source_files': len(json_files)
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print("\n📄 Configuración guardada en: {}".format(config_file))
        
        return optimal_params, best_capture.get('gait_parameters', {}) if stability_scores else {}
    else:
        print("\n❌ No se encontraron parámetros válidos para analizar")
        return {}, {}

def generate_summary_report(golden_dir="golden_params"):
    """Generar reporte detallado"""
    
    # Cargar CSV resumen si existe
    csv_file = os.path.join(golden_dir, "golden_params_summary.csv")
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            
            print("\n📈 ANÁLISIS TEMPORAL:")
            print("-" * 25)
            print("Total registros CSV: {}".format(len(df)))
            
            if len(df) > 0:
                print("Estabilidad promedio: {:.3f}".format(df['stability_score'].mean()))
                print("Duración promedio: {:.1f}s".format(df['duration'].mean()))
                print("Rango temporal: {:.1f}s".format(df['timestamp'].max() - df['timestamp'].min()))
                
                # Tendencias
                if len(df) > 5:
                    recent_stability = df.tail(5)['stability_score'].mean()
                    early_stability = df.head(5)['stability_score'].mean()
                    
                    if recent_stability > early_stability:
                        print("📈 Tendencia: MEJORANDO ({:.3f} → {:.3f})".format(early_stability, recent_stability))
                    else:
                        print("📉 Tendencia: EMPEORANDO ({:.3f} → {:.3f})".format(early_stability, recent_stability))
                
        except Exception as e:
            print("Error analizando CSV: {}".format(e))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analizar parámetros dorados capturados')
    parser.add_argument('--golden-dir', default='golden_params', help='Directorio con archivos de parámetros dorados')
    parser.add_argument('--verbose', '-v', action='store_true', help='Salida detallada')
    
    args = parser.parse_args()
    
    optimal_params, best_params = analyze_golden_params(args.golden_dir)
    
    if args.verbose:
        generate_summary_report(args.golden_dir)
    
    if optimal_params:
        print("\n✅ Análisis completado exitosamente")
        print("💡 Usa los parámetros GRASS_OPTIMAL_PARAMS en tu control_server.py")
    else:
        print("\n❌ No se encontraron parámetros válidos")
        print("💡 Ejecuta golden_params_detector_with_lock.py primero")
