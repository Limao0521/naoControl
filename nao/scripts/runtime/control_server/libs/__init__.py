#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
libs package - Librerías auxiliares para el control server

Este paquete contiene utilidades reutilizables:
- sensor_reader: Lectura de sensores FSR, IMU, batería
- gait_utils: Funciones para configuración de marcha
- motion_helpers: Wrappers seguros para operaciones NAOqi
"""

from __future__ import print_function
import sys
import os

# Agregar directorio actual al path
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from sensor_reader import SensorReader, FSRReader, IMUReader
from gait_utils import (
    clamp, lerp, ema,
    pairs_to_dict, dict_to_pairs, merge_pairs,
    config_to_move_list, apply_absolute_limits,
    ALLOWED_GAIT_KEYS, GAIT_PRESETS
)
from motion_helpers import (
    safe_nao_call, 
    MotionHelper,
    WatchdogTimer
)

__all__ = [
    # Sensor reader
    'SensorReader', 'FSRReader', 'IMUReader',
    # Gait utils
    'clamp', 'lerp', 'ema',
    'pairs_to_dict', 'dict_to_pairs', 'merge_pairs',
    'config_to_move_list', 'apply_absolute_limits',
    'ALLOWED_GAIT_KEYS', 'GAIT_PRESETS',
    # Motion helpers
    'safe_nao_call', 'MotionHelper', 'WatchdogTimer'
]
