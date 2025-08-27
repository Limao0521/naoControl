#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
cnn_replay_eval.py — Replay/Eval offline de la CNN usando CSVs del logger.

• Carga LightweightCNN desde adaptive_walk_cnn.py
• Lee filas de 1+ CSVs, arma el vector de 20 features y predice gait
• Compara con gait "ground truth" del CSV (si existen esas columnas)
• Opcional: aplica el gait predicho al robot (--apply) vía NAOqi

Ejemplos:
  python2 cnn_replay_eval.py --csv "/home/nao/datasets/walks/*.csv"
  python2 cnn_replay_eval.py --csv /home/nao/datasets/walks/walklog_20250827_101234.csv --apply

Requisitos:
  - adaptive_walk_cnn.py accesible (módulo Python)
  - Para --apply: NAOqi disponible y robot accesible
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

# ---------- Intentar cargar la CNN ligera ----------
try:
    from adaptive_walk_cnn import LightweightCNN
except Exception as e:
    print("[ERROR] No se pudo importar LightweightCNN desde adaptive_walk_cnn.py: %s" % e)
    sys.exit(1)

# Orden de features esperado por tu CNN (20 entradas)
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

def main():
    ap = argparse.ArgumentParser(description="Replay/Eval de CNN desde CSVs")
    ap.add_argument('--csv', required=True, nargs='+', help='rutas CSV (glob permitido, ej: "/path/*.csv")')
    ap.add_argument('--apply', action='store_true', help='aplica el gait predicho al robot (cuidado)')
    ap.add_argument('--nao-ip', default='127.0.0.1')
    ap.add_argument('--nao-port', type=int, default=9559)
    args = ap.parse_args()

    # Expandir globs
    csv_paths = []
    for p in args.csv:
        csv_paths.extend(glob.glob(p))
    csv_paths = [p for p in csv_paths if os.path.isfile(p)]
    if not csv_paths:
        print("[ERROR] No se encontraron CSVs con --csv")
        sys.exit(1)

    # Instanciar CNN ligera
    cnn = LightweightCNN()

    # Si se va a aplicar, cargar el controlador (NAOqi)
    walker = None
    if args.apply:
        try:
            from adaptive_walk_cnn import AdaptiveWalkController
            walker = AdaptiveWalkController(args.nao_ip, args.nao_port)
            if not walker.motion:
                print("[WARN] Walker sin motion proxy. No se aplicará gait.")
                walker = None
        except Exception as e:
            print("[ERROR] No se pudo inicializar AdaptiveWalkController: %s" % e)
            walker = None

    # Acumuladores de métricas
    total_rows = 0
    missing_feat_rows = 0
    abs_err = {k: [] for k in GAIT_KEYS}

    for path in csv_paths:
        print("[INFO] Procesando CSV: %s" % path)
        try:
            with open(path, 'rb') as f:
                rd = csv.reader(f)
                header = next(rd)

                for row in rd:
                    vec, gt, miss = parse_row(header, row)
                    if miss > 0:
                        missing_feat_rows += 1

                    pred = cnn.predict_gait_params(vec)

                    # Métricas contra ground truth si existe en el CSV
                    if gt:
                        diffs = diff_abs(pred, gt)
                        for k, v in diffs.items():
                            abs_err[k].append(v)

                    # Aplicar opcionalmente al robot (cuidado)
                    if walker is not None:
                        walker.apply_gait_params(pred)

                    total_rows += 1

        except Exception as e:
            print("[WARN] Error leyendo %s: %s" % (path, e))

    # Resumen
    print("\n=== RESUMEN REPLAY/EVAL ===")
    print("CSVs:", len(csv_paths))
    print("Filas totales:", total_rows)
    print("Filas con features faltantes (rellenadas con 0.0):", missing_feat_rows)

    any_gt = False
    for k in GAIT_KEYS:
        arr = abs_err[k]
        if arr:
            any_gt = True
            print("  %-13s  MAE=%0.6f  Med=%0.6f  Max=%0.6f  n=%d"
                  % (k, _mean(arr), _median(arr), max(arr), len(arr)))
        else:
            print("  %-13s  (sin ground truth en CSV)" % k)

    if not any_gt:
        print("\n[NOTA] Tus CSV no incluyen columnas de gait 'ground truth'.")
        print("       El replay sirvió para alimentar la CNN, pero no se calculó error.")

    if args.apply and walker is None:
        print("\n[WARN] --apply estaba activo pero no se logró aplicar gait (ver logs).")

if __name__ == '__main__':
    main()
