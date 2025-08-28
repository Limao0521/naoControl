#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
xgboost_replay_eval.py — Replay/Eval offline de XGBoost usando CSVs del logger.

• Carga modelos XGBoost entrenados desde train_xgboost_gait.py
• Lee filas de 1+ CSVs, arma el vector de 20 features y predice gait
• Compara con gait "ground truth" del CSV (si existen esas columnas)
• Opcional: aplica el gait predicho al robot (--apply) vía NAOqi

Ejemplos:
  python2 xgboost_replay_eval.py --csv "/home/nao/datasets/walks/*.csv"
  python2 xgboost_replay_eval.py --csv /home/nao/datasets/walks/walklog_20250827_101234.csv --apply

Requisitos:
  - adaptive_walk_xgboost.py accesible (módulo Python)
  - Para --apply: NAOqi disponible y robot accesible
  - XGBoost instalado
"""

from __future__ import print_function
import os
import sys
import csv
import glob
import math
import argparse

# ---------- Utilidades Py2: mean/median sin statistics ----------
def _mean(seq):
    n = float(len(seq) or 1.0)
    s = 0.0
    for v in seq:
        s += float(v)
    return s / n

def _median(seq):
    n = len(seq)
    if n == 0:
        return 0.0
    s = sorted(float(x) for x in seq)
    mid = n // 2
    if n % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])

# ---------- Intentar cargar el sistema XGBoost ----------
try:
    from adaptive_walk_xgboost import LightweightXGBoost, AdaptiveWalkController
    XGBOOST_SYSTEM_AVAILABLE = True
except Exception as e:
    print("[ERROR] No se pudo importar sistema XGBoost desde adaptive_walk_xgboost.py: %s" % e)
    XGBOOST_SYSTEM_AVAILABLE = False

# Orden de features esperado por el modelo XGBoost (20 entradas)
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_KEYS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def parse_row(header, row):
    """
    Devuelve:
      vec: lista de 20 floats en el orden FEAT_ORDER
      gt:  dict con gait "ground truth" si columnas existen en CSV
      miss: cuántas features faltaron (rellenas con 0.0)
    """
    idx = {}
    for i, h in enumerate(header):
        idx[h] = i

    vec = []
    miss = 0
    for k in FEAT_ORDER:
        if k in idx:
            vec.append(_safe_float(row[idx[k]], 0.0))
        else:
            vec.append(0.0)
            miss += 1

    gt = {}
    for gk in GAIT_KEYS:
        if gk in idx:
            gt[gk] = _safe_float(row[idx[gk]], None)

    return vec, gt, miss

def diff_abs(pred, gt):
    """Diferencias absolutas pred-gt por cada parámetro presente en gt."""
    diffs = {}
    for k in GAIT_KEYS:
        if k in gt and gt[k] is not None:
            diffs[k] = abs(_safe_float(pred.get(k, 0.0)) - _safe_float(gt[k], 0.0))
    return diffs

def calculate_physical_units_error(pred_norm, gt_norm, param_ranges):
    """
    Calcula errores en unidades físicas reales
    pred_norm, gt_norm: valores normalizados [0,1]
    """
    diffs_physical = {}
    for k in GAIT_KEYS:
        if k in gt_norm and gt_norm[k] is not None and k in pred_norm:
            # Convertir a unidades físicas
            lo, hi = param_ranges[k]
            pred_physical = lo + pred_norm[k] * (hi - lo)
            gt_physical = lo + gt_norm[k] * (hi - lo)
            diffs_physical[k] = abs(pred_physical - gt_physical)
    return diffs_physical

def main():
    if not XGBOOST_SYSTEM_AVAILABLE:
        print("[ERROR] Sistema XGBoost no disponible. Revisa imports.")
        sys.exit(1)

    ap = argparse.ArgumentParser(description="Replay/Eval de XGBoost desde CSVs")
    ap.add_argument('--csv', required=True, nargs='+', help='rutas CSV (glob permitido, ej: "/path/*.csv")')
    ap.add_argument('--apply', action='store_true', help='aplica el gait predicho al robot (cuidado)')
    ap.add_argument('--nao-ip', default='127.0.0.1')
    ap.add_argument('--nao-port', type=int, default=9559)
    ap.add_argument('--model-dir', default=None, help='directorio con modelos XGBoost entrenados')
    ap.add_argument('--verbose', action='store_true', help='output detallado')
    args = ap.parse_args()

    # Expandir globs
    csv_paths = []
    for p in args.csv:
        csv_paths.extend(glob.glob(p))
    csv_paths = [p for p in csv_paths if os.path.isfile(p)]
    if not csv_paths:
        print("[ERROR] No se encontraron CSVs con --csv")
        sys.exit(1)

    # Instanciar modelo XGBoost
    if args.model_dir:
        model_path = os.path.join(args.model_dir, 'xgboost_model.json')
        scaler_path = os.path.join(args.model_dir, 'feature_scaler.pkl')
        xgb_model = LightweightXGBoost(model_path, scaler_path)
    else:
        xgb_model = LightweightXGBoost()  # Usa rutas por defecto

    if not xgb_model.ok:
        print("[ERROR] No se pudo cargar modelo XGBoost")
        sys.exit(1)

    print("[INFO] Modelo XGBoost cargado exitosamente")

    # Si se va a aplicar, cargar el controlador (NAOqi)
    walker = None
    if args.apply:
        try:
            walker = AdaptiveWalkController(args.nao_ip, args.nao_port)
            if not walker.robot_io.motion:
                print("[WARN] Walker sin motion proxy. No se aplicará gait.")
                walker = None
        except Exception as e:
            print("[ERROR] No se pudo inicializar AdaptiveWalkController: %s" % e)
            walker = None

    # Rangos físicos para cálculo de errores
    param_ranges = {
        'StepHeight':   (0.01, 0.05),
        'MaxStepX':     (0.02, 0.08),
        'MaxStepY':     (0.08, 0.20),
        'MaxStepTheta': (0.10, 0.50),
        'Frequency':    (0.50, 1.20),
    }

    # Acumuladores de métricas
    total_rows = 0
    missing_feat_rows = 0
    abs_err = {k: [] for k in GAIT_KEYS}
    abs_err_physical = {k: [] for k in GAIT_KEYS}  # Errores en unidades físicas
    predictions_made = 0
    prediction_errors = 0

    for csv_idx, path in enumerate(csv_paths):
        print("[INFO] Procesando CSV %d/%d: %s" % (csv_idx + 1, len(csv_paths), path))
        try:
            with open(path, 'rb') as f:
                rd = csv.reader(f)
                header = next(rd)

                row_count = 0
                for row in rd:
                    vec, gt, miss = parse_row(header, row)
                    if miss > 0:
                        missing_feat_rows += 1
                        if args.verbose and miss > 5:  # Solo reportar si faltan muchas features
                            print("  [WARN] Fila %d: %d features faltantes" % (row_count, miss))

                    try:
                        # Predicción con XGBoost
                        pred = xgb_model.predict_gait_params(vec)
                        predictions_made += 1
                        
                        if args.verbose and row_count % 100 == 0:
                            print("  Fila %d - Predicción: %s" % (row_count, 
                                {k: "%.4f" % v for k, v in pred.items()}))

                        # Métricas contra ground truth si existe en el CSV
                        if gt:
                            # Convertir ground truth a rango normalizado para comparación justa
                            gt_norm = {}
                            for k, v in gt.items():
                                if v is not None and k in param_ranges:
                                    lo, hi = param_ranges[k]
                                    gt_norm[k] = (v - lo) / (hi - lo)  # Normalizar GT también

                            # Normalizar predicción para comparación
                            pred_norm = {}
                            for k, v in pred.items():
                                if k in param_ranges:
                                    lo, hi = param_ranges[k]
                                    pred_norm[k] = (v - lo) / (hi - lo)

                            # Errores normalizados
                            diffs = diff_abs(pred_norm, gt_norm)
                            for k, v in diffs.items():
                                abs_err[k].append(v)

                            # Errores en unidades físicas
                            diffs_phys = calculate_physical_units_error(pred_norm, gt_norm, param_ranges)
                            for k, v in diffs_phys.items():
                                abs_err_physical[k].append(v)

                        # Aplicar opcionalmente al robot (cuidado)
                        if walker is not None:
                            success = walker.apply_gait_params(pred)
                            if args.verbose and not success:
                                print("  [WARN] No se pudo aplicar gait en fila %d" % row_count)

                    except Exception as e:
                        prediction_errors += 1
                        if args.verbose:
                            print("  [ERROR] Error en predicción fila %d: %s" % (row_count, e))

                    total_rows += 1
                    row_count += 1

        except Exception as e:
            print("[WARN] Error leyendo %s: %s" % (path, e))

    # Resumen
    print("\\n=== RESUMEN REPLAY/EVAL XGBoost ===")
    print("CSVs procesados:", len(csv_paths))
    print("Filas totales:", total_rows)
    print("Predicciones exitosas:", predictions_made)
    print("Errores de predicción:", prediction_errors)
    print("Filas con features faltantes (rellenadas con 0.0):", missing_feat_rows)

    if prediction_errors > 0:
        print("Tasa de error de predicción: %.2f%%" % (100.0 * prediction_errors / max(1, total_rows)))

    print("\\n--- Errores Normalizados [0,1] ---")
    any_gt = False
    for k in GAIT_KEYS:
        arr = abs_err[k]
        if arr:
            any_gt = True
            print("  %-13s  MAE=%0.6f  Med=%0.6f  Max=%0.6f  n=%d"
                  % (k, _mean(arr), _median(arr), max(arr), len(arr)))
        else:
            print("  %-13s  (sin ground truth en CSV)" % k)

    print("\\n--- Errores en Unidades Físicas ---")
    for k in GAIT_KEYS:
        arr = abs_err_physical[k]
        if arr:
            unit_map = {
                'StepHeight': 'm',
                'MaxStepX': 'm', 
                'MaxStepY': 'm',
                'MaxStepTheta': 'rad',
                'Frequency': 'Hz'
            }
            unit = unit_map.get(k, '')
            print("  %-13s  MAE=%0.6f%s  Med=%0.6f%s  Max=%0.6f%s  n=%d"
                  % (k, _mean(arr), unit, _median(arr), unit, max(arr), unit, len(arr)))

    if not any_gt:
        print("\\n[NOTA] Tus CSV no incluyen columnas de gait 'ground truth'.")
        print("       El replay sirvió para alimentar XGBoost, pero no se calculó error.")

    if args.apply and walker is None:
        print("\\n[WARN] --apply estaba activo pero no se logró aplicar gait (ver logs).")

    # Evaluación de calidad del modelo
    if any_gt:
        print("\\n--- Evaluación de Calidad ---")
        avg_mae_norm = _mean([_mean(abs_err[k]) for k in GAIT_KEYS if abs_err[k]])
        
        if avg_mae_norm < 0.05:
            quality = "EXCELENTE"
        elif avg_mae_norm < 0.10:
            quality = "BUENA"  
        elif avg_mae_norm < 0.20:
            quality = "REGULAR"
        else:
            quality = "POBRE"
            
        print("MAE promedio normalizado: %.6f" % avg_mae_norm)
        print("Calidad estimada del modelo: %s" % quality)
        
        if quality in ["POBRE", "REGULAR"]:
            print("\\nSugerencias para mejorar:")
            print("- Recolectar más datos de entrenamiento")
            print("- Revisar calidad de las features")
            print("- Ajustar hiperparámetros del modelo")
            print("- Verificar que los rangos de normalización sean correctos")

if __name__ == '__main__':
    main()
