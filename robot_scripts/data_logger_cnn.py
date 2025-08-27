#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
data_logger_cnn.py — Logger de dataset (NAOqi puro, Python 2.7)

CAMBIO: Solo registra filas cuando el robot está caminando.
Criterios de "caminando":
  1) Si ALMotion.moveIsActive() es True, o
  2) Si la norma de la velocidad (vx,vy,wz) > --speed-threshold

Qué registra (igual que antes):
  • 20 features usados por la CNN:
      IMU (accel, gyro), ángulos (AngleX, AngleY),
      FSR (8 pads), velocidades (vx, vy, wz, vtotal)
  • Parámetros de marcha vigentes (StepHeight, MaxStepX/Y/Theta, Frequency)
    (leídos de /home/nao/.local/share/adaptive_gait/last_params.json)
  • Etiqueta de estabilidad (auto por umbral de pitch) opcional

Salida: CSV con cabecera en --out-dir (por defecto /home/nao/datasets/walks)

Ejemplos:
  python2 data_logger_cnn.py --duration 120
  python2 data_logger_cnn.py --out-dir /home/nao/datasets/walks --period 0.05 --label-mode auto --tilt-threshold 0.14
  python2 data_logger_cnn.py --only-walking --speed-threshold 0.02
"""

from __future__ import print_function
import os, sys, csv, time, math, json, argparse
from datetime import datetime

try:
    from naoqi import ALProxy
except Exception as e:
    print("ERROR: NAOqi ALProxy no disponible: %s" % e)
    sys.exit(1)

# ------- Claves ALMemory (mismas señales que usa la CNN) -------
MEM_KEYS = {
    'accel_x': "Device/SubDeviceList/InertialSensor/AccelerometerX/Sensor/Value",
    'accel_y': "Device/SubDeviceList/InertialSensor/AccelerometerY/Sensor/Value",
    'accel_z': "Device/SubDeviceList/InertialSensor/AccelerometerZ/Sensor/Value",
    'gyro_x':  "Device/SubDeviceList/InertialSensor/GyroscopeX/Sensor/Value",
    'gyro_y':  "Device/SubDeviceList/InertialSensor/GyroscopeY/Sensor/Value",
    'gyro_z':  "Device/SubDeviceList/InertialSensor/GyroscopeZ/Sensor/Value",
    'angle_x': "Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value",
    'angle_y': "Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value",
    'lfoot_fl': "Device/SubDeviceList/LFoot/FSR/FrontLeft/Sensor/Value",
    'lfoot_fr': "Device/SubDeviceList/LFoot/FSR/FrontRight/Sensor/Value",
    'lfoot_rl': "Device/SubDeviceList/LFoot/FSR/RearLeft/Sensor/Value",
    'lfoot_rr': "Device/SubDeviceList/LFoot/FSR/RearRight/Sensor/Value",
    'rfoot_fl': "Device/SubDeviceList/RFoot/FSR/FrontLeft/Sensor/Value",
    'rfoot_fr': "Device/SubDeviceList/RFoot/FSR/FrontRight/Sensor/Value",
    'rfoot_rl': "Device/SubDeviceList/RFoot/FSR/RearLeft/Sensor/Value",
    'rfoot_rr': "Device/SubDeviceList/RFoot/FSR/RearRight/Sensor/Value",
}

CSV_HEADER = [
    'timestamp',
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal',
    'StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency',
    'stable'
]

DEFAULT_GAIT_JSON = "/home/nao/.local/share/adaptive_gait/last_params.json"
DEFAULT_OUT_DIR   = "/home/nao/datasets/walks"

def safe_get(mem, key, default=0.0):
    try:
        v = mem.getData(key)
        return float(v) if v is not None else default
    except Exception:
        return default

def read_sensors(memory):
    d = {}
    for name, key in MEM_KEYS.items():
        d[name] = safe_get(memory, key, 0.0)
    return d

def read_velocity(motion):
    try:
        vx, vy, wz = motion.getRobotVelocity()
        vx = float(vx or 0.0); vy = float(vy or 0.0); wz = float(wz or 0.0)
        vtotal = math.sqrt(vx*vx + vy*vy + wz*wz)
        return vx, vy, wz, vtotal
    except Exception:
        return 0.0, 0.0, 0.0, 0.0

def load_gait_params(path_json):
    defaults = {'StepHeight':0.025,'MaxStepX':0.04,'MaxStepY':0.14,'MaxStepTheta':0.3,'Frequency':0.8}
    try:
        with open(path_json, 'rb') as f:
            data = json.load(f)
        out = defaults.copy()
        for k in out.keys():
            if k in data:
                out[k] = float(data[k])
        return out
    except Exception:
        return defaults

def compute_stable_label(angle_x, tilt_thr):
    try:
        return 0 if abs(float(angle_x)) > float(tilt_thr) else 1
    except Exception:
        return 1

def is_robot_walking(motion, vtotal, speed_thr):
    """
    Devuelve True si el robot está caminando:
      - moveIsActive() es True, o
      - vtotal > speed_thr
    """
    try:
        if hasattr(motion, "moveIsActive") and motion.moveIsActive():
            return True
    except Exception:
        pass
    try:
        return float(vtotal) > float(speed_thr)
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser(description="Logger de dataset NAOqi → CSV (solo caminando si se indica)")
    ap.add_argument('--nao-ip', default='127.0.0.1')
    ap.add_argument('--nao-port', type=int, default=9559)
    ap.add_argument('--out-dir', default=DEFAULT_OUT_DIR)
    ap.add_argument('--period', type=float, default=0.05, help='segundos entre muestras (0.05 ≈ 20 Hz)')
    ap.add_argument('--duration', type=float, default=0.0, help='duración en s (0 = infinito)')
    ap.add_argument('--gait-json', default=DEFAULT_GAIT_JSON, help='ruta JSON con últimos parámetros aplicados')
    ap.add_argument('--label-mode', choices=['none','auto'], default='auto')
    ap.add_argument('--tilt-threshold', type=float, default=0.14, help='umbral pitch (rad) para label auto')
    ap.add_argument('--only-walking', action='store_true', default=True,
                    help='solo registrar filas cuando el robot camina (default: True)')
    ap.add_argument('--speed-threshold', type=float, default=0.02,
                    help='umbral de velocidad total para considerar movimiento')
    args = ap.parse_args()

    # Crear proxies
    try:
        memory = ALProxy("ALMemory", args.nao_ip, args.nao_port)
        motion = ALProxy("ALMotion", args.nao_ip, args.nao_port)
        print("[INFO] Conectado a NAOqi en %s:%d" % (args.nao_ip, args.nao_port))
    except Exception as e:
        print("[ERROR] No se pudo conectar a NAOqi: %s" % e)
        sys.exit(1)

    # Preparar salida
    if not os.path.isdir(args.out_dir):
        try:
            os.makedirs(args.out_dir)
        except Exception as e:
            print("[ERROR] No se pudo crear out-dir: %s" % e)
            sys.exit(1)

    ts_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(args.out_dir, "walklog_%s.csv" % ts_name)
    print("[INFO] Escribiendo CSV en: %s" % csv_path)
    print("[INFO] only-walking=%s | speed-threshold=%.3f" % (args.only_walking, args.speed_threshold))

    # Bucle de muestreo
    t0 = time.time()
    n_logged = 0
    n_seen = 0
    with open(csv_path, 'wb') as f:
        wr = csv.writer(f)
        wr.writerow(CSV_HEADER)
        f.flush()

        while True:
            t = time.time()
            if args.duration > 0 and (t - t0) >= args.duration:
                break

            # Lecturas
            s = read_sensors(memory)
            vx, vy, wz, vtotal = read_velocity(motion)
            gait = load_gait_params(args.gait_json)

            # ¿Caminando?
            walking = is_robot_walking(motion, vtotal, args.speed_threshold)
            n_seen += 1

            if (not args.only_walking) or walking:
                if args.label_mode == 'auto':
                    stable = compute_stable_label(s['angle_x'], args.tilt_threshold)
                else:
                    stable = 1

                row = [
                    datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    s['accel_x'], s['accel_y'], s['accel_z'],
                    s['gyro_x'], s['gyro_y'], s['gyro_z'],
                    s['angle_x'], s['angle_y'],
                    s['lfoot_fl'], s['lfoot_fr'], s['lfoot_rl'], s['lfoot_rr'],
                    s['rfoot_fl'], s['rfoot_fr'], s['rfoot_rl'], s['rfoot_rr'],
                    vx, vy, wz, vtotal,
                    gait['StepHeight'], gait['MaxStepX'], gait['MaxStepY'], gait['MaxStepTheta'], gait['Frequency'],
                    stable
                ]
                wr.writerow(row)
                n_logged += 1
                if (n_logged % 50) == 0:
                    sys.stdout.write("\r[INFO] Filas registradas: %d (vistas: %d)" % (n_logged, n_seen)); sys.stdout.flush()
            else:
                # No se registra esta muestra por estar en reposo
                if (n_seen % 100) == 0:
                    sys.stdout.write("\r[INFO] Reposo/idle... registradas: %d (vistas: %d)" % (n_logged, n_seen)); sys.stdout.flush()

            # Esperar periodo
            dt = time.time() - t
            sleep_t = args.period - dt
            if sleep_t > 0:
                time.sleep(sleep_t)

    print("\n[OK] Fin de registro. Filas registradas: %d de %d muestras vistas." % (n_logged, n_seen))
    print("[OK] Archivo CSV: %s" % csv_path)

if __name__ == '__main__':
    main()
  