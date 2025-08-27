#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
adaptive_walk_cnn.py - Caminata adaptativa con filtros de confort para NAO/NAOqi

- CNN ligera (numpy) que estima parámetros de marcha estables: MaxStepX, MaxStepY, MaxStepTheta, Frequency, StepHeight.
- Bucle de adaptación con:
    * Filtro EMA (suavizado)
    * Zona muerta (deadband)
    * Limitador de pendiente (rate limiter)
    * Consenso de signo (histeresis temporal)
    * "Comfort lock" (bloqueo cuando camina cómodo; se congela la adaptación un rato)
- Telemetría a last_params.json para depurar desde shell.

Requisitos:
  - Python 2.7 en NAO
  - NAOqi SDK disponible (ALMotion/ALMemory). Si no están, el script arranca en modo "solo CNN".

Archivo de estado/salida:
  /home/nao/.local/share/adaptive_gait/last_params.json

Pesos de la CNN:
  /home/nao/.local/share/adaptive_gait/weights.npz
"""

from __future__ import print_function
import os
import json
import time
import math
from collections import deque

import numpy as np

try:
    from naoqi import ALProxy
    NAOQI_AVAILABLE = True
except Exception:
    NAOQI_AVAILABLE = False

# ------------------------------
# Utilidades de E/S y rutas
# ------------------------------
HOME = os.path.expanduser('~')
DATA_DIR = os.path.join(HOME, '.local', 'share', 'adaptive_gait')
if not os.path.isdir(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except OSError:
        pass

WEIGHTS_PATH = os.path.join(DATA_DIR, 'weights.npz')
LAST_JSON = os.path.join(DATA_DIR, 'last_params.json')

# ------------------------------
# Configuración (tuneable)
# ------------------------------
CFG = {
    # Frecuencia de actualización (más lento = menos cambios bruscos)
    'update_period_s': 0.8,   # 0.7 - 1.0 recomendado

    # Suavizado exponencial de la predicción de la CNN
    'ema_alpha': 0.2,         # 0.1-0.3

    # Zona muerta: ignora micromovimientos
    'deadband': {
        'MaxStepY': 0.0030,       # ~3 mm lateral
        'MaxStepTheta': 0.0002,   # ~0.01°
        'MaxStepX': 0.0020,       # ~2 mm
        'Frequency': 0.0020,
        'StepHeight': 0.0020,
    },

    # Limitador de cambio por actualización
    'rate_limit': {
        'MaxStepY': 0.0010,
        'MaxStepTheta': 0.0002,
        'MaxStepX': 0.0010,
        'Frequency': 0.0050,
        'StepHeight': 0.0010,
    },

    # Consenso de signo: requiere que la mayoría de las últimas N decisiones apunten en la misma dirección
    'consensus': {
        'window': 5,
        'min_same_sign': 4
    },

    # Comfort lock / hold
    'comfort': {
        'enable': True,
        'stable_secs_to_lock': 3.0,   # tiempo con errores pequeños para bloquear
        'hold_secs': 10.0,            # tiempo bloqueado
        'unlock_threshold': {         # si los errores vuelven a subir, desbloquea
            'MaxStepY': 0.008,
            'MaxStepTheta': 0.0006,
        }
    },

    # Límites físicos/seguridad del NAO (recortes hard)
    'limits': {
        'MaxStepX': (0.0, 0.08),
        'MaxStepY': (0.0, 0.20),
        'MaxStepTheta': (0.0, 0.35),
        'Frequency': (0.6, 1.4),
        'StepHeight': (0.015, 0.03),
    },

    # Logging: escribe también prints de depuración
    'verbose': False,
}

PARAMS = ('MaxStepX','MaxStepY','MaxStepTheta','Frequency','StepHeight')

# ------------------------------
# CNN ligera (con numpy)
# ------------------------------
class TinyCNN(object):
    def __init__(self, weights_path):
        self.ok = False
        self.W = {}
        if os.path.isfile(weights_path):
            try:
                data = np.load(weights_path)
                # Se esperan matrices con nombres 'W1','b1','W2','b2','W3','b3'
                for k in data.files:
                    self.W[k] = data[k]
                self.ok = True
            except Exception as e:
                print("[E] No pude cargar pesos: %s" % e)
        else:
            print("[W] No encontré pesos en %s" % weights_path)

    def forward(self, x):
        """
        x: vector numpy 1xF (features sensores)
        Devuelve dict con parámetros de marcha (ya en rangos 0..1 normalizados)
        """
        if not self.ok:
            # fallback: devolver base sin cambios
            base = np.array([0.05, 0.10, 0.30, 0.85, 0.025], dtype=np.float32)
            return dict(zip(PARAMS, base))

        try:
            W1,b1 = self.W['W1'], self.W['b1']
            W2,b2 = self.W['W2'], self.W['b2']
            W3,b3 = self.W['W3'], self.W['b3']
            h1 = np.maximum(0, np.dot(x, W1) + b1)
            h2 = np.maximum(0, np.dot(h1, W2) + b2)
            y  = np.dot(h2, W3) + b3
            # y está ya en unidades reales (no normalizadas) según entrenamiento
            out = dict(zip(PARAMS, np.squeeze(np.array(y, dtype=np.float64))))
            return out
        except Exception as e:
            print("[E] forward(): %s" % e)
            base = np.array([0.05, 0.10, 0.30, 0.85, 0.025], dtype=np.float32)
            return dict(zip(PARAMS, base))

# ------------------------------
# Lectura de sensores NAOqi (minimal)
# ------------------------------
class RobotIO(object):
    def __init__(self):
        self.motion = None
        self.mem = None
        if NAOQI_AVAILABLE:
            try:
                self.motion = ALProxy("ALMotion", "127.0.0.1", 9559)
            except Exception as e:
                print("[W] ALMotion no disponible: %s" % e)
            try:
                self.mem = ALProxy("ALMemory", "127.0.0.1", 9559)
            except Exception as e:
                print("[W] ALMemory no disponible: %s" % e)

    def get_features(self):
        """
        Extrae un vector de características simple desde ALMemory.
        Si no hay NAOqi, devuelve constantes válidas.
        """
        # Campos típicos (puedes ajustar a tus señales reales)
        keys = [
            "Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value",
            "Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value",
            "Device/SubDeviceList/InertialSensor/AccX/Sensor/Value",
            "Device/SubDeviceList/InertialSensor/AccY/Sensor/Value",
            "Device/SubDeviceList/InertialSensor/AccZ/Sensor/Value",
            "Device/SubDeviceList/InertialSensor/GyrX/Sensor/Value",
            "Device/SubDeviceList/InertialSensor/GyrY/Sensor/Value",
        ]
        if self.mem is None:
            return np.array([0,0,9.81,0,0,0,0], dtype=np.float32)

        vals = []
        for k in keys:
            try:
                v = self.mem.getData(k)
            except Exception:
                v = 0.0
            if v is None: v = 0.0
            vals.append(float(v))
        return np.array(vals, dtype=np.float32)

    def apply_walk_params(self, params):
        """
        Envía parámetros a ALMotion.setWalkTargetVelocity a través de Proxy, si existe.
        Aquí no mandamos velocidades (vx,vy,theta), sino que ajustamos los límites internos del paso.
        NAOqi expone setWalkParam (modelo viejo) en algunos releases; si no existe, lo omitimos.
        """
        if self.motion is None:
            return False
        # Intentar setMoveConfig si existe
        mapping = {
            'MaxStepX':       "MaxStepX",
            'MaxStepY':       "MaxStepY",
            'MaxStepTheta':   "MaxStepTheta",
            'Frequency':      "MaxStepFrequency",
            'StepHeight':     "StepHeight"
        }
        to_set = []
        for k,v in params.items():
            if k in mapping:
                to_set.append([mapping[k], float(v)])
        ok = True
        try:
            # NAOqi: motion.setMoveConfig acepta lista de [name, value]
            self.motion.setMoveConfig(to_set)
        except Exception as e:
            # Algunos firmwares usan setWalkArmsConfig / setFootSteps*;
            # si no podemos escribir, consideramos "no fatal".
            if CFG['verbose']:
                print("[W] No pude aplicar moveConfig: %s" % e)
            ok = False
        return ok

# ------------------------------
# Filtro de adaptación
# ------------------------------
class AdaptationLoop(object):
    def __init__(self, cnn, rio):
        self.cnn = cnn
        self.rio = rio

        # estado del filtro
        self.ema = None
        self.last_applied = None
        self.last_update = 0.0
        self.comfort_on = False
        self.lock_until = 0.0
        self.stable_since = None

        self.sign_hist = {p: deque(maxlen=CFG['consensus']['window']) for p in PARAMS}

        # stats
        self.prediction_times = deque(maxlen=100)
        self.predictions = 0
        self.adaptations_enabled = True

    def clamp_limits(self, params):
        out = {}
        for p,v in params.items():
            lo, hi = CFG['limits'][p]
            out[p] = float(min(max(v, lo), hi))
        return out

    def ema_smooth(self, pred):
        if self.ema is None:
            self.ema = dict(pred)
            return dict(pred)
        a = CFG['ema_alpha']
        out = {}
        for p in PARAMS:
            out[p] = (1-a)*self.ema[p] + a*pred[p]
        self.ema = dict(out)
        return out

    def deadband(self, target, current):
        out = {}
        for p in PARAMS:
            eps = CFG['deadband'].get(p, 0.0)
            if abs(target[p] - current[p]) < eps:
                out[p] = current[p]  # no cambiar
            else:
                out[p] = target[p]
        return out

    def rate_limit(self, desired, current):
        out = {}
        rate = CFG['rate_limit']
        for p in PARAMS:
            dv = desired[p] - current[p]
            lim = rate.get(p, 1.0)
            if dv > lim: dv = lim
            if dv < -lim: dv = -lim
            out[p] = current[p] + dv
        return out

    def update_sign_history(self, current, target):
        for p in ('MaxStepY','MaxStepTheta'):  # consenso en los críticos de estabilidad
            dv = target[p] - current[p]
            s = 1 if dv>0 else (-1 if dv<0 else 0)
            self.sign_hist[p].append(s)

    def has_consensus(self, p):
        hist = list(self.sign_hist[p])
        if len(hist) < CFG['consensus']['window']:
            return False
        # cuenta abs(sign) y coincidencias de signo
        nonzero = [s for s in hist if s!=0]
        if len(nonzero) < CFG['consensus']['min_same_sign']:
            return False
        pos = nonzero.count(1)
        neg = nonzero.count(-1)
        return (max(pos,neg) >= CFG['consensus']['min_same_sign'])

    def comfort_update(self, d_errors):
        """
        Decide activar o desactivar el comfort lock.
        d_errors: dict con |pred-applied| para Y y Theta
        """
        now = time.time()
        if not CFG['comfort']['enable']:
            self.comfort_on = False
            self.stable_since = None
            return

        # si estamos en hold, mantener hasta lock_until
        if self.comfort_on and now < self.lock_until:
            return

        # chequeo de desbloqueo por error grande
        if self.comfort_on and now >= self.lock_until:
            # seguimos bloqueados solo si el error sigue pequeño
            uy = CFG['comfort']['unlock_threshold']['MaxStepY']
            uth= CFG['comfort']['unlock_threshold']['MaxStepTheta']
            if d_errors['MaxStepY'] > uy or d_errors['MaxStepTheta'] > uth:
                # desbloquear
                self.comfort_on = False
                self.stable_since = None
            else:
                # ampliar hold un poquito para no parpadear
                self.lock_until = now + 0.5
            return

        # si no está activo, evaluar estabilidad para activarlo
        small = (
            d_errors['MaxStepY'] < CFG['deadband']['MaxStepY'] and
            d_errors['MaxStepTheta'] < CFG['deadband']['MaxStepTheta']
        )
        if small:
            if self.stable_since is None:
                self.stable_since = now
            if (now - self.stable_since) >= CFG['comfort']['stable_secs_to_lock']:
                self.comfort_on = True
                self.lock_until = now + CFG['comfort']['hold_secs']
        else:
            self.stable_since = None
            self.comfort_on = False

    def step(self):
        # 1) leer sensores -> features
        feats = self.rio.get_features()

        # 2) predecir
        t0 = time.time()
        pred = self.cnn.forward(feats)
        t1 = time.time()
        self.prediction_times.append((t1-t0)*1000.0)
        self.predictions += 1

        # 3) inicializar current/applied si es la primera vez
        if self.last_applied is None:
            self.last_applied = dict(pred)  # start from pred recortado luego
            self.last_applied = self.clamp_limits(self.last_applied)

        # 4) suavizado
        pred_s = self.ema_smooth(pred)

        # 5) recortes hard
        pred_s = self.clamp_limits(pred_s)

        # 6) deadband respecto al aplicado actual
        desired = self.deadband(pred_s, self.last_applied)

        # 7) consenso
        self.update_sign_history(self.last_applied, desired)
        for p in ('MaxStepY','MaxStepTheta'):
            if not self.has_consensus(p):
                desired[p] = self.last_applied[p]  # no mueva sin consenso

        # 8) comfort lock
        d_errors = {
            'MaxStepY': abs(pred_s['MaxStepY'] - self.last_applied['MaxStepY']),
            'MaxStepTheta': abs(pred_s['MaxStepTheta'] - self.last_applied['MaxStepTheta'])
        }
        self.comfort_update(d_errors)

        # 9) si comfort_on, congelar
        if self.comfort_on:
            applied = dict(self.last_applied)
            rate_limited = False
        else:
            # 10) rate limiter
            applied = self.rate_limit(desired, self.last_applied)
            rate_limited = any(abs(applied[p]-desired[p])>1e-12 for p in PARAMS)

        # 11) aplicar a NAO (best effort)
        applied_ok = self.rio.apply_walk_params(applied)

        # 12) telemetría JSON
        delta = {p: round(applied[p] - self.last_applied[p], 12) for p in PARAMS}
        delta_norm = math.sqrt(sum(d*d for d in delta.values()))
        meta = {
            'ts': time.time(),
            'pred': {p: float(pred_s[p]) for p in PARAMS},
            'applied': {p: float(applied[p]) for p in PARAMS},
            'delta': delta,
            'delta_norm': float(delta_norm),
            'rate_limited': bool(rate_limited),
            'cnn_ms': float(self.prediction_times[-1]),
            'predictions': self.predictions,
            'comfort_on': bool(self.comfort_on),
            'applied_ok': bool(applied_ok),
        }
        out = dict(applied)
        out['_meta'] = meta

        try:
            with open(LAST_JSON, 'w') as f:
                json.dump(out, f, sort_keys=True)
        except Exception as e:
            if CFG['verbose']:
                print("[W] No pude escribir %s: %s" % (LAST_JSON, e))

        # 13) guardar aplicado y tiempo
        self.last_applied = dict(applied)
        self.last_update = time.time()

        return out

    def get_stats(self):
        avg_ms = sum(self.prediction_times)/len(self.prediction_times) if self.prediction_times else 0.0
        return {
            'avg_time_ms': avg_ms,
            'predictions': self.predictions,
            'cnn_available': bool(self.cnn.ok),
            'adaptations_enabled': bool(self.adaptations_enabled),
        }

# ------------------------------
# Main
# ------------------------------
def main():
    print("=== NAO Adaptive Walk (CNN + Comfort Filters) ===")
    cnn = TinyCNN(WEIGHTS_PATH)
    if cnn.ok:
        print("[OK] Pesos cargados:", WEIGHTS_PATH)
    else:
        print("[W] CNN sin pesos válidos, se usará base fija")

    rio = RobotIO()
    loop = AdaptationLoop(cnn, rio)

    period = CFG['update_period_s']
    print("[INFO] Periodo actualización = %.2fs  EMA=%.2f  deadband(y=%.4f,th=%.4f)  comfort=%s"
          % (period, CFG['ema_alpha'], CFG['deadband']['MaxStepY'], CFG['deadband']['MaxStepTheta'], CFG['comfort']['enable']))

    # Primera escritura para inicializar JSON con algo consistente
    loop.step()

    try:
        while True:
            t0 = time.time()
            loop.step()
            # dormir hasta completar periodo
            dt = time.time() - t0
            to_sleep = max(0.0, period - dt)
            time.sleep(to_sleep)
    except KeyboardInterrupt:
        print("\n[INFO] Salida por Ctrl+C")
        print(json.dumps({'cnnStats': loop.get_stats()}, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
