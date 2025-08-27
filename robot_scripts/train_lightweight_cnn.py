#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_lightweight_cnn.py — Entrenamiento offline del MLP (20→32→16→5)
Compatible con adaptive_walk_cnn.py (NAO, Python 2.7) exportando weights.npz

Requisitos (PC):
  pip install torch pandas numpy

Uso (ejemplos):
  python3 train_lightweight_cnn.py --data "/home/tuuser/datasets/walks/*.csv" --out weights.npz
  python3 train_lightweight_cnn.py --data "/ruta/sesion1.csv" "/ruta/sesion2.csv" --epochs 60 --lr 5e-4

Salida:
  weights.npz con claves: W1,b1,W2,b2,W3,b3
"""

import argparse, glob, os, sys, math
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader, random_split

# Orden exacto de features que usa tu CNN (20)
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_KEYS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

# Rangos físicos (deben coincidir con adaptive_walk_cnn.py)
PARAM_RANGES = {
    'StepHeight':   (0.01, 0.05),
    'MaxStepX':     (0.02, 0.08),
    'MaxStepY':     (0.08, 0.20),
    'MaxStepTheta': (0.10, 0.50),
    'Frequency':    (0.50, 1.20),
}

class WalkDataset(Dataset):
    def __init__(self, csv_paths):
        dfs = []
        for p in csv_paths:
            try:
                dfs.append(pd.read_csv(p))
            except Exception as e:
                print(f"[WARN] No pude leer {p}: {e}")
        if not dfs:
            raise RuntimeError("No hay CSVs válidos para entrenar.")

        df = pd.concat(dfs, ignore_index=True)

        # Filtrar filas que tengan los 20 features
        for col in FEAT_ORDER:
            if col not in df.columns:
                df[col] = 0.0  # relleno por si falta (no ideal, pero robusto)

        # Targets: gait aplicado (si alguna columna no existe, se descarta esa fila)
        mask_y = np.ones(len(df), dtype=bool)
        for g in GAIT_KEYS:
            mask_y &= df[g].notna() if g in df.columns else False

        df = df.loc[mask_y].reset_index(drop=True)
        if len(df) == 0:
            raise RuntimeError("No hay filas con gait 'ground truth' en los CSV.")

        # X: 20 features
        X = df[FEAT_ORDER].astype(np.float32).values

        # Y: normalizar a [0,1] por rango físico
        Y = np.zeros((len(df), len(GAIT_KEYS)), dtype=np.float32)
        for j, g in enumerate(GAIT_KEYS):
            lo, hi = PARAM_RANGES[g]
            y_raw = df[g].astype(np.float32).values
            Y[:, j] = np.clip((y_raw - lo) / (hi - lo), 0.0, 1.0)

        self.X = X
        self.Y = Y

    def __len__(self):
        return self.X.shape[0]

    def __getitem__(self, idx):
        x = self.X[idx].copy()
        y = self.Y[idx].copy()
        # NORMALIZACIÓN POR MUESTRA (igual que en el NAO):
        mu = x.mean()
        sigma = x.std() + 1e-8
        x = (x - mu) / sigma
        return torch.from_numpy(x), torch.from_numpy(y)

class MLP(nn.Module):
    """
    20 → 32 (ReLU) → 16 (ReLU) → 5 (Sigmoid)
    Salida ∈ [0,1] para cada parámetro, consistente con el NAO.
    """
    def __init__(self):
        super(MLP, self).__init__()
        self.fc1 = nn.Linear(20, 32)
        self.fc2 = nn.Linear(32, 16)
        self.fc3 = nn.Linear(16, 5)
        self.act = nn.ReLU()
        self.out_act = nn.Sigmoid()

        # Init similar a tu script (randn * 0.1, biases en 0)
        with torch.no_grad():
            for m in [self.fc1, self.fc2, self.fc3]:
                m.weight.copy_(0.1 * torch.randn_like(m.weight))
                m.bias.zero_()

    def forward(self, x):
        x = self.act(self.fc1(x))
        x = self.act(self.fc2(x))
        x = self.out_act(self.fc3(x))
        return x

def export_to_npz(model, out_path):
    """
    Exporta a shapes esperadas por adaptive_walk_cnn.py:
      W1: (20,32)   b1: (1,32)
      W2: (32,16)   b2: (1,16)
      W3: (16,5)    b3: (1,5)
    """
    with torch.no_grad():
        W1 = model.fc1.weight.t().cpu().numpy().astype(np.float32)
        b1 = model.fc1.bias.view(1, -1).cpu().numpy().astype(np.float32)
        W2 = model.fc2.weight.t().cpu().numpy().astype(np.float32)
        b2 = model.fc2.bias.view(1, -1).cpu().numpy().astype(np.float32)
        W3 = model.fc3.weight.t().cpu().numpy().astype(np.float32)
        b3 = model.fc3.bias.view(1, -1).cpu().numpy().astype(np.float32)
    np.savez(out_path, W1=W1, b1=b1, W2=W2, b2=b2, W3=W3, b3=b3)
    print(f"[OK] Pesos exportados a: {out_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True,
                    help='Rutas CSV (puedes pasar globs: "/path/*.csv")')
    ap.add_argument("--out", default="weights.npz", help="Ruta de salida de pesos .npz")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--val-split", type=float, default=0.2, help="Fracción para validación")
    args = ap.parse_args()

    # Expandir globs
    paths = []
    for p in args.data:
        paths.extend(glob.glob(p))
    paths = [p for p in paths if os.path.isfile(p)]
    if not paths:
        print("[ERROR] No se encontraron CSVs con --data"); sys.exit(1)

    ds = WalkDataset(paths)
    n_total = len(ds)
    n_val = int(round(args.val_split * n_total))
    n_train = n_total - n_val
    train_ds, val_ds = random_split(ds, [n_train, n_val])

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MLP().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.MSELoss()

    print(f"[INFO] Train={n_train}  Val={n_val}  BZ={args.batch_size}  Epochs={args.epochs}  LR={args.lr}")
    best_val = float("inf")
    best_state = None

    for epoch in range(1, args.epochs+1):
        # ---- train
        model.train()
        total = 0.0; n = 0
        for xb, yb in train_loader:
            xb = xb.to(device).float()
            yb = yb.to(device).float()
            opt.zero_grad()
            yhat = model(xb)
            loss = loss_fn(yhat, yb)
            loss.backward()
            opt.step()
            total += loss.item() * xb.size(0)
            n += xb.size(0)
        tr_loss = total / max(1, n)

        # ---- val
        model.eval()
        total = 0.0; n = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device).float(); yb = yb.to(device).float()
                yhat = model(xb)
                total += loss_fn(yhat, yb).item() * xb.size(0)
                n += xb.size(0)
        va_loss = total / max(1, n)

        print(f"Epoch {epoch:03d} | Train MSE: {tr_loss:.6f} | Val MSE: {va_loss:.6f}")

        if va_loss < best_val:
            best_val = va_loss
            best_state = {k: v.cpu().clone() for k,v in model.state_dict().items()}

    # Restaurar mejor estado y exportar
    if best_state is not None:
        model.load_state_dict(best_state)
    export_to_npz(model, args.out)

if __name__ == "__main__":
    main()
