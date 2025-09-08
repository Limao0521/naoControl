#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
core.config

Propósito: Variables de configuración centralizadas para la aplicación.
Edite este archivo para ajustar parámetros de red, límites de seguridad
y rutas de recursos. El encabezado añadido es informativo.
Fecha: 2025-09-08
"""

# Configuración de red
NAO_IP = "127.0.0.1"
NAO_PORT = 9559
WEBSOCKET_PORT = 6671
LOG_WEBSOCKET_PORT = 6672
HTTP_PORT = 8000

# Configuración de logging
LOG_LEVEL = "INFO"
LOG_FILE = "/tmp/nao_system.log"
MAX_LOG_HISTORY = 500

# Configuración de watchdog
WATCHDOG_TIMEOUT = 0.6

# Configuración de video
DEFAULT_VIDEO_RESOLUTION = 1  # VGA
UDP_VIDEO_PORT = 12345

# Configuración de caminata adaptiva
OPTIMAL_GRASS_PARAMS = {
    'StepHeight': 0.020,
    'MaxStepX': 0.040,
    'MaxStepY': 0.140,
    'MaxStepTheta': 0.349,
    'Frequency': 1.000
}

MOVEMENT_SPECIFIC_PARAMS = {
    'forward': {'MaxStepX': 0.045, 'Frequency': 1.1},
    'backward': {'MaxStepX': 0.025, 'Frequency': 0.9},
    'lateral': {'MaxStepY': 0.160, 'Frequency': 0.95},
    'turn': {'MaxStepTheta': 0.380, 'Frequency': 1.05},
    'static': OPTIMAL_GRASS_PARAMS
}

# Configuración de features para ML
FEATURE_ORDER = [
    'accel_x','accel_y','accel_z',
    'gyro_x','gyro_y','gyro_z', 
    'angle_x','angle_y',
    'lfoot_fl','lfoot_fr','lfoot_rl','lfoot_rr',
    'rfoot_fl','rfoot_fr','rfoot_rl','rfoot_rr',
    'vx','vy','wz','vtotal'
]

GAIT_TARGETS = ['StepHeight','MaxStepX','MaxStepY','MaxStepTheta','Frequency']

# Rutas de archivos
MODELS_DIR = "models_npz_automl"
WEB_DIR = "/home/nao/Webs/ControllerWebServer"
SCRIPTS_DIR = "/home/nao/scripts"

# Configuración de servicios
SERVICES_CONFIG = {
    'logger': {'enabled': True, 'auto_start': True},
    'motion': {'enabled': True, 'auto_start': True},
    'adaptive_walk': {'enabled': True, 'auto_start': False, 'mode': 'production'},
    'video_stream': {'enabled': True, 'auto_start': False},
    'websocket_server': {'enabled': True, 'auto_start': True},
    'sensor_reader': {'enabled': True, 'auto_start': True}
}

# Configuración de limites de seguridad
SAFETY_LIMITS = {
    'max_velocity': {'vx': 0.3, 'vy': 0.3, 'wz': 1.0},
    'gait_params': {
        'StepHeight': {'min': 0.005, 'max': 0.05},
        'MaxStepX': {'min': 0.01, 'max': 0.08},
        'MaxStepY': {'min': 0.05, 'max': 0.20},
        'MaxStepTheta': {'min': 0.1, 'max': 0.5},
        'Frequency': {'min': 0.5, 'max': 2.0}
    }
}
