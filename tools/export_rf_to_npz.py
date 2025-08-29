"""
export_rf_to_npz.py

Utility to export scikit-learn RandomForestRegressor and StandardScaler
into NPZ files compatible with adaptive_walk_randomforest.py on NAO.

Usage:
  python export_rf_to_npz.py --model model.pkl --scaler scaler.pkl --out-dir models

This script will create:
  - models/randomforest_model_<param>.npz  (if model is a single regressor, it will be exported as-is)
  - models/feature_scaler.npz

It also supports exporting a forest as a list of trees (one npz per tree) if requested.
"""
from __future__ import print_function
import argparse
import os
import sys
import numpy as np

try:
    import joblib
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
except Exception as e:
    print("This script requires scikit-learn and joblib to be installed on the host.")
    raise


def export_forest(rf, out_path_prefix):
    """Export a RandomForestRegressor as NPZ without pickle objects (Python2 compatible).
    Each tree is saved as t{i}_children_left, t{i}_children_right, etc.
    Also saves n_trees for loader to know how many trees to reconstruct.
    """
    save_dict = {}
    
    # Export each tree as separate arrays with prefixed keys
    for i, estimator in enumerate(rf.estimators_):
        tree = estimator.tree_
        prefix = "t{}_".format(i)
        save_dict[prefix + "children_left"] = tree.children_left.astype(np.int32)
        save_dict[prefix + "children_right"] = tree.children_right.astype(np.int32)
        save_dict[prefix + "feature"] = tree.feature.astype(np.int32)
        save_dict[prefix + "threshold"] = tree.threshold.astype(np.float64)
        # Flatten tree.value to 1D if needed
        vals = tree.value
        if vals.ndim > 1:
            vals = np.squeeze(vals)
        save_dict[prefix + "value"] = vals.astype(np.float64)
    
    # Save number of trees for loader
    save_dict["n_trees"] = np.int32(len(rf.estimators_))
    
    # Save without pickle objects (Python2 compatible)
    np.savez_compressed(out_path_prefix + '.npz', **save_dict)
    print("Exported forest to {}.npz (n_trees={}, no pickle)".format(out_path_prefix, len(rf.estimators_)))


def export_scaler(scaler, out_path):
    mean = scaler.mean_.astype(np.float64)
    scale = scaler.scale_.astype(np.float64)
    np.savez_compressed(out_path, mean=mean, scale=scale)
    print("Exported scaler to {}".format(out_path))


def _export_single(model_path, scaler_path, out_dir):
    try:
        rf = joblib.load(model_path)
    except Exception as e:
        print("[ERROR] No se pudo cargar modelo {}: {}".format(model_path, e))
        return False

    base = os.path.splitext(os.path.basename(model_path))[0]
    # normalize base name: randomforest_model_<param>
    out_prefix = os.path.join(out_dir, base)
    try:
        if hasattr(rf, 'estimators_'):
            export_forest(rf, out_prefix)
        elif isinstance(rf, dict):
            # dict of param->model
            for param, model in rf.items():
                p_out = os.path.join(out_dir, 'randomforest_model_{}'.format(param))
                export_forest(model, p_out)
        else:
            # try to export as single regressor
            export_forest(rf, out_prefix)
    except Exception as e:
        print("[ERROR] Falló al exportar {}: {}".format(model_path, e))
        return False
    return True


def main():
    import glob

    parser = argparse.ArgumentParser(description='Export RandomForest .pkl -> .npz for NAO')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--model', help='Single RandomForest .pkl model file')
    group.add_argument('--models-dir', help='Directory containing randomforest_model_*.pkl files')
    parser.add_argument('--scaler', required=True, help='feature_scaler.pkl path')
    parser.add_argument('--out-dir', default='models_npz', help='Output directory for .npz files')
    args = parser.parse_args()

    out_dir = args.out_dir
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    # Load scaler once and export
    try:
        scaler = joblib.load(args.scaler)
        out_scaler = os.path.join(out_dir, 'feature_scaler.npz')
        export_scaler(scaler, out_scaler)
    except Exception as e:
        print("[ERROR] No se pudo cargar/generar scaler {}: {}".format(args.scaler, e))
        return 2

    model_files = []
    if args.models_dir:
        pattern = os.path.join(args.models_dir, 'randomforest_model_*.pkl')
        model_files = sorted(glob.glob(pattern))
        if not model_files:
            print("[ERROR] No se encontraron modelos en {}".format(pattern))
            return 3
    else:
        model_files = [args.model]

    ok = True
    for m in model_files:
        print("[INFO] Exportando modelo: {}".format(m))
        if not _export_single(m, args.scaler, out_dir):
            ok = False

    if not ok:
        print("[WARN] Algunos modelos fallaron al exportar")
        return 4

    print("[OK] Export terminado. Archivos en: {}".format(out_dir))
    return 0


if __name__ == '__main__':
    sys.exit(main())
