#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
adaptive_walk_cnn.py - CNN ligera para caminata adaptativa en NAO (NAOqi puro)

• Predice 5 parámetros de marcha (StepHeight, MaxStepX, MaxStepY, MaxStepTheta, Frequency)
  a partir de 20 features (IMU, ángulos, FSR, vx/vy/wz/vtotal).
• Aplica la configuración vía ALMotion.setMotionConfig (NO envía comandos de caminar).
• Suaviza cambios.
• Persiste el último gait aplicado en:
    /home/nao/.local/share/adaptive_gait/last_params.json
  para que `data_logger_cnn.py` lo registre junto con sensores.
• NUEVO: Carga automática de pesos entrenados desde:
    /home/nao/.local/share/adaptive_gait/weights.npz
  (si no existe, usa pesos aleatorios → modo demo).

Requisitos:
  - Python 2.7
  - NAOqi (ALProxy)
  - NumPy
"""

from __future__ import print_function
import os, time, json
from collections import deque

try:
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    print("Warning: NumPy no disponible - CNN deshabilitada (usando parámetros fijos).")
    ML_AVAILABLE = False

try:
    from naoqi import ALProxy
except Exception as e:
    ALProxy = None
    print("Warning: NAOqi ALProxy no disponible: %s" % e)

# Rutas de persistencia (gait aplicado y pesos entrenados)
ADAPTIVE_DIR     = "/home/nao/.local/share/adaptive_gait"
GAIT_JSON_PATH   = os.path.join(ADAPTIVE_DIR, "last_params.json")
WEIGHTS_NPZ_PATH = os.path.join(ADAPTIVE_DIR, "weights.npz")


class LightweightCNN(object):
    """
    MLP compacto: 20 → 32 → 16 → 5 (ReLU, ReLU, Sigmoid).
    Carga pesos desde .npz si está disponible; si no, usa inicialización aleatoria.
    """
    def __init__(self):
        self.input_size   = 20
        self.hidden1_size = 32
        self.hidden2_size = 16
        self.output_size  = 5

        # Parámetros base (fallback)
        self.base_params = {
            'StepHeight':   0.025,
            'MaxStepX':     0.04,
            'MaxStepY':     0.14,
            'MaxStepTheta': 0.3,
            'Frequency':    0.8
        }

        self.param_ranges = {
            'StepHeight':   (0.01, 0.05),
            'MaxStepX':     (0.02, 0.08),
            'MaxStepY':     (0.08, 0.20),
            'MaxStepTheta': (0.10, 0.50),
            'Frequency':    (0.50, 1.20)
        }

        if ML_AVAILABLE:
            # Inicialización
            self.W1 = np.random.randn(self.input_size,  self.hidden1_size) * 0.1
            self.b1 = np.zeros((1, self.hidden1_size))
            self.W2 = np.random.randn(self.hidden1_size, self.hidden2_size) * 0.1
            self.b2 = np.zeros((1, self.hidden2_size))
            self.W3 = np.random.randn(self.hidden2_size, self.output_size) * 0.1
            self.b3 = np.zeros((1, self.output_size))

            # Intentar cargar pesos entrenados
            self._try_load_weights(WEIGHTS_NPZ_PATH)

    # ---------- utilidades ----------
    def _relu(self, x):
        return np.maximum(0.0, x)

    def _sigmoid(self, x):
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500.0, 500.0)))

    def _forward(self, input_vector):
        x = np.array(input_vector, dtype='float32').reshape(1, -1)
        x = (x - np.mean(x)) / (np.std(x) + 1e-8)
        z1 = np.dot(x, self.W1) + self.b1
        a1 = self._relu(z1)
        z2 = np.dot(a1, self.W2) + self.b2
        a2 = self._relu(z2)
        z3 = np.dot(a2, self.W3) + self.b3
        y  = self._sigmoid(z3)
        return y.flatten()

    def _try_load_weights(self, path_npz):
        try:
            if os.path.isfile(path_npz):
                data = np.load(path_npz)
                # Se esperan claves: W1,b1,W2,b2,W3,b3
                self.W1 = np.array(data['W1']); self.b1 = np.array(data['b1'])
                self.W2 = np.array(data['W2']); self.b2 = np.array(data['b2'])
                self.W3 = np.array(data['W3']); self.b3 = np.array(data['b3'])
                print("[CNN] Pesos cargados desde %s" % path_npz)
            else:
                print("[CNN] No se encontró %s; usando pesos aleatorios." % path_npz)
        except Exception as e:
            print("[CNN] Error cargando pesos (%s). Se usan pesos aleatorios." % e)

    def predict_gait_params(self, sensor_data):
        if not ML_AVAILABLE:
            return self.base_params.copy()
        try:
            y = self._forward(sensor_data)
            names = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']
            out = {}
            for i, name in enumerate(names):
                lo, hi = self.param_ranges[name]
                out[name] = lo + float(y[i]) * (hi - lo)
            return out
        except Exception as e:
            print("Error en predicción CNN: %s" % e)
            return self.base_params.copy()


class AdaptiveWalkController(object):
    """
    Controlador adaptativo:
      - Lee sensores por ALMemory (IMU, ángulos, FSR)
      - Inserta (vx,vy,wz,vtotal)
      - Predice gait con la CNN y lo suaviza
      - Aplica por ALMotion.setMotionConfig (NO manda caminar)
      - Persiste last_params.json para `data_logger_cnn`
    """
    def __init__(self, nao_ip="127.0.0.1", nao_port=9559):
        self.nao_ip, self.nao_port = nao_ip, nao_port
        self.motion = self.memory = self.inertial = None
        if ALProxy:
            try:
                self.motion   = ALProxy("ALMotion", nao_ip, nao_port)
                self.memory   = ALProxy("ALMemory", nao_ip, nao_port)
                self.inertial = ALProxy("ALInertialSensor", nao_ip, nao_port)
                print("Proxies NAOqi inicializados.")
            except Exception as e:
                print("Error inicializando NAOqi: %s" % e)

        self.cnn = LightweightCNN() if ML_AVAILABLE else None
        print("CNN ligera inicializada." if self.cnn else "CNN deshabilitada (sin NumPy).")

        self.sensor_history = deque(maxlen=10)
        self.last_params = None
        self.adaptation_enabled = True

        self.prediction_count = 0
        self.total_prediction_time = 0.0

    # --- lectura sensores ---
    def _get(self, key):
        try:
            v = self.memory.getData(key)
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def get_sensor_data(self):
        v = [0.0]*20
        try:
            if self.memory:
                v[0] = self._get("Device/SubDeviceList/InertialSensor/AccelerometerX/Sensor/Value")
                v[1] = self._get("Device/SubDeviceList/InertialSensor/AccelerometerY/Sensor/Value")
                v[2] = self._get("Device/SubDeviceList/InertialSensor/AccelerometerZ/Sensor/Value")
                v[3] = self._get("Device/SubDeviceList/InertialSensor/GyroscopeX/Sensor/Value")
                v[4] = self._get("Device/SubDeviceList/InertialSensor/GyroscopeY/Sensor/Value")
                v[5] = self._get("Device/SubDeviceList/InertialSensor/GyroscopeZ/Sensor/Value")
                v[6] = self._get("Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value")
                v[7] = self._get("Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value")
                v[8]  = self._get("Device/SubDeviceList/LFoot/FSR/FrontLeft/Sensor/Value")
                v[9]  = self._get("Device/SubDeviceList/LFoot/FSR/FrontRight/Sensor/Value")
                v[10] = self._get("Device/SubDeviceList/LFoot/FSR/RearLeft/Sensor/Value")
                v[11] = self._get("Device/SubDeviceList/LFoot/FSR/RearRight/Sensor/Value")
                v[12] = self._get("Device/SubDeviceList/RFoot/FSR/FrontLeft/Sensor/Value")
                v[13] = self._get("Device/SubDeviceList/RFoot/FSR/FrontRight/Sensor/Value")
                v[14] = self._get("Device/SubDeviceList/RFoot/FSR/RearLeft/Sensor/Value")
                v[15] = self._get("Device/SubDeviceList/RFoot/FSR/RearRight/Sensor/Value")
        except Exception as e:
            print("Error leyendo sensores: %s" % e)
        return v

    def add_command_velocities(self, vec, vx, vy, wz):
        if vec is None or len(vec) < 20:
            vec = (vec or []) + [0.0]*(20 - len(vec or []))
        try:
            vtot = (vx*vx + vy*vy + wz*wz) ** 0.5
            vec[16], vec[17], vec[18], vec[19] = float(vx), float(vy), float(wz), float(vtot)
        except Exception:
            pass
        return vec[:20]

    # --- suavizado ---
    def _smooth(self, new_p, alpha=0.3):
        if self.last_params is None:
            self.last_params = dict(new_p)
            return dict(new_p)
        out = {}
        for k, nv in new_p.items():
            ov = self.last_params.get(k, nv)
            out[k] = float(ov)*(1.0-alpha) + float(nv)*alpha
        self.last_params = dict(out)
        return out

    # --- persistencia gait aplicado ---
    def _persist_gait_json(self, params):
        try:
            if not os.path.isdir(ADAPTIVE_DIR):
                os.makedirs(ADAPTIVE_DIR)
            with open(GAIT_JSON_PATH, 'wb') as f:
                json.dump(params, f)
        except Exception as e:
            print("Warn persistencia gait: %s" % e)

    # --- adaptación / aplicación ---
    def adapt_gait(self, vx, vy, wz):
        if not self.adaptation_enabled or self.cnn is None:
            return None
        t0 = time.time()
        try:
            s = self.add_command_velocities(self.get_sensor_data(), vx, vy, wz)
            self.sensor_history.append(s)
            if len(self.sensor_history) >= 3:
                s_in = np.mean(list(self.sensor_history)[-3:], axis=0)
            else:
                s_in = s
            pred = self.cnn.predict_gait_params(s_in)
            smooth = self._smooth(pred)
            self.prediction_count += 1
            self.total_prediction_time += (time.time() - t0)
            if (self.prediction_count % 50) == 0:
                avg_ms = (self.total_prediction_time / self.prediction_count) * 1000.0
                print("CNN: {} preds, t_prom={:.3f} ms".format(self.prediction_count, avg_ms))
            return smooth
        except Exception as e:
            print("Error adaptación: %s" % e)
            return None

    def apply_gait_params(self, params):
        """
        Aplica los parámetros (setMotionConfig). NO envía comandos de caminar.
        """
        if not params or self.motion is None:
            return False
        try:
            cfg = [[k, float(v)] for k, v in params.items()]
            self.motion.setMotionConfig(cfg)
            self._persist_gait_json(params)
            return True
        except Exception as e:
            print("Error setMotionConfig: %s" % e)
            return False

    # --- stats ---
    def get_stats(self):
        if self.prediction_count:
            avg_ms = (self.total_prediction_time / float(self.prediction_count)) * 1000.0
            return {'predictions': self.prediction_count, 'avg_time_ms': avg_ms,
                    'adaptations_enabled': bool(self.adaptation_enabled),
                    'cnn_available': self.cnn is not None}
        return {'predictions': 0, 'cnn_available': self.cnn is not None,
                'adaptations_enabled': bool(self.adaptation_enabled)}


def create_adaptive_walker(nao_ip="127.0.0.1", nao_port=9559):
    return AdaptiveWalkController(nao_ip, nao_port)


if __name__ == "__main__":
    print("=== Test CNN Caminata Adaptativa ===")
    w = create_adaptive_walker()
    if w.cnn:
        # Demo rápido (no aplica ni camina):
        v = [0.1,-0.05,9.8, 0.02,-0.01,0.0, 0.05,-0.02,
             0.5,0.6,0.4,0.5, 0.6,0.5,0.4,0.6, 0.5,0.3,0.1,0.6]
        print("Pred demo:", w.cnn.predict_gait_params(v))
        a = w.adapt_gait(0.5,0.0,0.0)
        print("Adapt demo:", a)
        # Para aplicar realmente el gait (NO camina por sí solo), descomenta:
        # w.apply_gait_params(a)
    else:
        print("CNN no disponible (instala NumPy).")
