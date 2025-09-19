#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
data_logger.py - Generic data logger for gait training datasets

Creates CSV datasets with inertial, foot pressure and gait-parameter columns.
Designed to run on NAO (Python 2.7) and on desktop (Python 3.x) for data collection.

Usage (example):
  python data_logger.py --output ./datasets/walk_session.csv --duration 300 --frequency 10

This module replaces the older data_logger_xgboost.py and is agnostic to the
machine-learning model used later (RandomForest, XGBoost, etc.).
"""

from __future__ import print_function
import os
import sys
import csv
import time
import argparse
import io
from datetime import datetime

try:
    from naoqi import ALProxy
    NAOQI_AVAILABLE = True
except Exception:
    NAOQI_AVAILABLE = False

# Order of features (kept compatible with earlier tools)
FEAT_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z',
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_PARAMS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']


class SensorReader(object):
    """Reads sensors from NAO (or simulates values when NAOqi not available)."""

    def __init__(self, nao_ip="127.0.0.1", nao_port=9559):
        self.motion = None
        self.memory = None
        if NAOQI_AVAILABLE:
            try:
                self.motion = ALProxy("ALMotion", nao_ip, nao_port)
                self.memory = ALProxy("ALMemory", nao_ip, nao_port)
                print("[INFO] Connected to NAOqi on %s:%d" % (nao_ip, nao_port))
            except Exception as e:
                print("[WARN] Could not connect to NAOqi: %s" % e)
                self.motion = None
                self.memory = None

        self.last_gait_params = self._get_default_gait_params()

    def _get_default_gait_params(self):
        return {
            'StepHeight': 0.025,
            'MaxStepX': 0.04,
            'MaxStepY': 0.14,
            'MaxStepTheta': 0.35,
            'Frequency': 1.0
        }

    def _safe_get_sensor(self, key, default=0.0):
        if self.memory is None:
            return default
        try:
            value = self.memory.getData(key)
            return float(value) if value is not None else default
        except Exception:
            return default

    def get_inertial_data(self):
        data = {}
        data['accel_x'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AccX/Sensor/Value", 0.0)
        data['accel_y'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AccY/Sensor/Value", 0.0)
        data['accel_z'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AccZ/Sensor/Value", 9.81)
        data['gyro_x'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/GyrX/Sensor/Value", 0.0)
        data['gyro_y'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/GyrY/Sensor/Value", 0.0)
        data['gyro_z'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/GyrZ/Sensor/Value", 0.0)
        data['angle_x'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value", 0.0)
        data['angle_y'] = self._safe_get_sensor("Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value", 0.0)
        return data

    def get_foot_pressure_data(self):
        data = {}
        data['lfoot_fl'] = self._safe_get_sensor("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value", 0.0)
        data['lfoot_fr'] = self._safe_get_sensor("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value", 0.0)
        data['lfoot_rl'] = self._safe_get_sensor("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value", 0.0)
        data['lfoot_rr'] = self._safe_get_sensor("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value", 0.0)
        data['rfoot_fl'] = self._safe_get_sensor("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value", 0.0)
        data['rfoot_fr'] = self._safe_get_sensor("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value", 0.0)
        data['rfoot_rl'] = self._safe_get_sensor("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value", 0.0)
        data['rfoot_rr'] = self._safe_get_sensor("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value", 0.0)
        return data

    def get_velocity_data(self):
        return {'vx': 0.0, 'vy': 0.0, 'wz': 0.0, 'vtotal': 0.0}

    def get_current_gait_params(self):
        if self.motion is None:
            return self.last_gait_params.copy()
        try:
            return self.last_gait_params.copy()
        except Exception:
            return self.last_gait_params.copy()

    def set_gait_params(self, params):
        if self.motion is None:
            self.last_gait_params.update(params)
            return False
        try:
            config_list = []
            if 'StepHeight' in params:
                config_list.append(["StepHeight", float(params['StepHeight'])])
            if 'MaxStepX' in params:
                config_list.append(["MaxStepX", float(params['MaxStepX'])])
            if 'MaxStepY' in params:
                config_list.append(["MaxStepY", float(params['MaxStepY'])])
            if 'MaxStepTheta' in params:
                config_list.append(["MaxStepTheta", float(params['MaxStepTheta'])])
            if 'Frequency' in params:
                config_list.append(["MaxStepFrequency", float(params['Frequency'])])
            self.motion.setMoveConfig(config_list)
            self.last_gait_params.update(params)
            return True
        except Exception:
            return False

    def get_complete_sample(self):
        sample = {}
        sample.update(self.get_inertial_data())
        sample.update(self.get_foot_pressure_data())
        sample.update(self.get_velocity_data())
        sample.update(self.get_current_gait_params())
        sample['timestamp'] = time.time()
        return sample


class DataLogger(object):
    """Generic CSV data logger for gait samples."""

    def __init__(self, output_file, sensor_reader):
        self.output_file = output_file
        self.sensor_reader = sensor_reader
        self.csv_writer = None
        self.csv_file = None
        self.samples_written = 0

        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def _open_csv(self):
        # Python 3: newline='' to avoid extra blank lines; Python 2: binary mode
        if sys.version_info[0] >= 3:
            return open(self.output_file, 'w', newline='')
        else:
            return open(self.output_file, 'wb')

    def start_logging(self):
        try:
            self.csv_file = self._open_csv()
            fieldnames = FEAT_ORDER + GAIT_PARAMS + ['timestamp']
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames, extrasaction='ignore')
            self.csv_writer.writeheader()
            print('[INFO] Logging started -> %s' % self.output_file)
            return True
        except Exception as e:
            print('[ERROR] Could not start logging: %s' % e)
            return False

    def log_sample(self):
        if self.csv_writer is None:
            return False
        try:
            sample = self.sensor_reader.get_complete_sample()
            # Ensure only expected fields are passed (DictWriter extrasaction='ignore')
            self.csv_writer.writerow(sample)
            try:
                self.csv_file.flush()
            except Exception:
                pass
            self.samples_written += 1
            return True
        except Exception as e:
            print('[ERROR] Error writing sample: %s' % e)
            return False

    def stop_logging(self):
        if self.csv_file:
            try:
                self.csv_file.close()
            except Exception:
                pass
            self.csv_file = None
            self.csv_writer = None
        print('[INFO] Logging stopped. Samples written: %d' % self.samples_written)


def main():
    parser = argparse.ArgumentParser(description='Data logger for gait training datasets')
    parser.add_argument('--output', required=True, help='Output CSV file')
    parser.add_argument('--duration', type=float, default=60.0, help='Duration in seconds (0=infinite)')
    parser.add_argument('--frequency', type=float, default=10.0, help='Sampling frequency (Hz)')
    parser.add_argument('--nao-ip', default='127.0.0.1', help='NAO IP')
    parser.add_argument('--nao-port', type=int, default=9559, help='NAOqi port')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    if args.frequency <= 0:
        print('[ERROR] frequency must be > 0')
        sys.exit(1)

    sample_period = 1.0 / args.frequency

    print('=== Data Logger ===')
    print('Output: %s' % args.output)
    print('Duration: %s' % ('infinite' if args.duration <= 0 else str(args.duration)))
    print('Frequency: %.1f Hz' % args.frequency)

    sensor_reader = SensorReader(args.nao_ip, args.nao_port)
    data_logger = DataLogger(args.output, sensor_reader)

    if not data_logger.start_logging():
        sys.exit(1)

    start_time = time.time()
    last_sample_time = 0

    try:
        print('\n[INFO] Starting data collection... (Ctrl+C to stop)')
        while True:
            current_time = time.time()
            if current_time - last_sample_time >= sample_period:
                if data_logger.log_sample():
                    last_sample_time = current_time
                    if args.verbose:
                        elapsed = current_time - start_time
                        print('  Sample %d (t=%.1fs)' % (data_logger.samples_written, elapsed))
                else:
                    print('[WARN] Error logging sample %d' % (data_logger.samples_written + 1))

            if args.duration > 0 and (current_time - start_time) >= args.duration:
                print('\n[INFO] Duration completed')
                break

            time.sleep(0.01)

    except KeyboardInterrupt:
        print('\n[INFO] Stopped by user')
    except Exception as e:
        print('\n[ERROR] Unexpected error: %s' % e)
    finally:
        data_logger.stop_logging()
        elapsed_total = time.time() - start_time
        if elapsed_total > 0:
            actual_frequency = float(data_logger.samples_written) / elapsed_total
            print('\nStats:')
            print('  Total time: %.1f s' % elapsed_total)
            print('  Samples: %d' % data_logger.samples_written)
            print('  Real frequency: %.2f Hz' % actual_frequency)


if __name__ == '__main__':
    main()
