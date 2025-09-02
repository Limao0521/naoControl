#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
nao_config.py - Configuración Centralizada del Sistema NAO
========================================================

Archivo de configuración central que elimina la duplicación de constantes
en múltiples archivos del sistema.

Contiene:
- Orden de features para ML
- Parámetros de gait
- Configuraciones de red
- Constantes del sistema
- Parámetros por defecto

Usado por:
- adaptive_walk_lightgbm_nao.py
- data_logger.py  
- analyze_gait_logs.py
- control_server.py
- Y otros módulos del sistema
"""

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE MACHINE LEARNING
# ═══════════════════════════════════════════════════════════════════════════════

# Orden estricto de features para modelos ML (NO MODIFICAR SIN REENTRENAR)
FEATURE_ORDER = [
    'accel_x', 'accel_y', 'accel_z',
    'gyro_x', 'gyro_y', 'gyro_z', 
    'angle_x', 'angle_y',
    'lfoot_fl', 'lfoot_fr', 'lfoot_rl', 'lfoot_rr',
    'rfoot_fl', 'rfoot_fr', 'rfoot_rl', 'rfoot_rr',
    'vx', 'vy', 'wz', 'vtotal'
]

# Parámetros de gait que predice/controla el sistema
GAIT_TARGETS = ['StepHeight', 'MaxStepX', 'MaxStepY', 'MaxStepTheta', 'Frequency']

# Mapeo de sensores NAOqi a nombres de features
SENSOR_MAPPINGS = {
    # Acelerómetro
    'accel_x': 'Device/SubDeviceList/InertialSensor/AccX/Sensor/Value',
    'accel_y': 'Device/SubDeviceList/InertialSensor/AccY/Sensor/Value', 
    'accel_z': 'Device/SubDeviceList/InertialSensor/AccZ/Sensor/Value',
    
    # Giroscopio
    'gyro_x': 'Device/SubDeviceList/InertialSensor/GyroX/Sensor/Value',
    'gyro_y': 'Device/SubDeviceList/InertialSensor/GyroY/Sensor/Value',
    'gyro_z': 'Device/SubDeviceList/InertialSensor/GyroZ/Sensor/Value',
    
    # Ángulos de inclinación
    'angle_x': 'Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value',
    'angle_y': 'Device/SubDeviceList/InertialSensor/AngleY/Sensor/Value',
    
    # FSR Pie Izquierdo
    'lfoot_fl': 'Device/SubDeviceList/LFoot/FSR/FrontLeft/Sensor/Value',
    'lfoot_fr': 'Device/SubDeviceList/LFoot/FSR/FrontRight/Sensor/Value',
    'lfoot_rl': 'Device/SubDeviceList/LFoot/FSR/RearLeft/Sensor/Value',
    'lfoot_rr': 'Device/SubDeviceList/LFoot/FSR/RearRight/Sensor/Value',
    
    # FSR Pie Derecho  
    'rfoot_fl': 'Device/SubDeviceList/RFoot/FSR/FrontLeft/Sensor/Value',
    'rfoot_fr': 'Device/SubDeviceList/RFoot/FSR/FrontRight/Sensor/Value',
    'rfoot_rl': 'Device/SubDeviceList/RFoot/FSR/RearLeft/Sensor/Value',
    'rfoot_rr': 'Device/SubDeviceList/RFoot/FSR/RearRight/Sensor/Value'
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE GAIT Y MOVIMIENTO
# ═══════════════════════════════════════════════════════════════════════════════

# Límites absolutos de velocidad (para pasto/exterior)
VELOCITY_LIMITS = {
    'vx_max': 0.6,    # Velocidad máxima adelante/atrás
    'vx_min': -0.6,
    'vy_max': 0.45,   # Velocidad máxima lateral  
    'vy_min': -0.45,
    'wz_max': 3.0,    # Rotación sin límite estricto
    'wz_min': -3.0
}

# Parámetros de gait por defecto (OPTIMIZADOS PARA PASTO SINTÉTICO)
# Extraídos de análisis de 538 registros de caminata exitosa
OPTIMAL_GRASS_PARAMS = {
    'MaxStepX': 0.040000,       # Paso máximo adelante/atrás (m)
    'MaxStepY': 0.140000,       # Paso máximo lateral (m)  
    'MaxStepTheta': 0.349000,   # Rotación máxima por paso (rad)
    'StepHeight': 0.020000,     # Altura de paso (m)
    'Frequency': 1.000000       # Frecuencia de paso (Hz)
}

# 🎯 PARÁMETROS ESPECÍFICOS POR TIPO DE MOVIMIENTO
# Para mejorar estabilidad en diferentes direcciones
MOVEMENT_SPECIFIC_PARAMS = {
    'forward': {         # Movimiento hacia adelante
        'MaxStepX': 0.040000,
        'MaxStepY': 0.140000,
        'MaxStepTheta': 0.349000,
        'StepHeight': 0.020000,
        'Frequency': 1.000000
    },
    'backward': {        # Movimiento hacia atrás (más conservador)
        'MaxStepX': 0.030000,    # Pasos más cortos atrás
        'MaxStepY': 0.120000,    # Menor paso lateral
        'MaxStepTheta': 0.250000, # Menor rotación
        'StepHeight': 0.025000,  # Más altura para clearance
        'Frequency': 0.800000    # Más lento para estabilidad
    },
    'sideways': {        # Movimiento lateral
        'MaxStepX': 0.025000,    # Pasos cortos adelante/atrás
        'MaxStepY': 0.100000,    # Pasos laterales más pequeños
        'MaxStepTheta': 0.200000, # Mínima rotación
        'StepHeight': 0.025000,  # Mayor altura
        'Frequency': 0.900000    # Frecuencia reducida
    },
    'rotation': {        # Rotación en el lugar
        'MaxStepX': 0.020000,    # Pasos mínimos
        'MaxStepY': 0.080000,    # Base estrecha para rotación
        'MaxStepTheta': 0.400000, # Rotación máxima
        'StepHeight': 0.030000,  # Alta para clearance
        'Frequency': 0.800000    # Lento para control
    },
    'mixed': {           # Movimiento combinado (conservador)
        'MaxStepX': 0.035000,
        'MaxStepY': 0.120000,
        'MaxStepTheta': 0.300000,
        'StepHeight': 0.025000,
        'Frequency': 0.900000
    }
}

# Parámetros de gait por defecto (conservadores - fallback)
DEFAULT_GAIT_PARAMS = {
    'MaxStepX': 0.04,       # Paso máximo adelante/atrás (m)
    'MaxStepY': 0.14,       # Paso máximo lateral (m)  
    'MaxStepTheta': 0.35,   # Rotación máxima por paso (rad)
    'StepHeight': 0.02,     # Altura de paso (m)
    'Frequency': 1.0        # Frecuencia de paso (Hz)
}

# Rangos válidos para parámetros de gait
GAIT_PARAM_RANGES = {
    'MaxStepX': (0.01, 0.08),
    'MaxStepY': (0.05, 0.20),
    'MaxStepTheta': (0.1, 0.5),
    'StepHeight': (0.005, 0.05),
    'Frequency': (0.5, 2.0)
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE RED Y COMUNICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

# Puertos del sistema
PORTS = {
    'naoqi': 9559,           # Puerto NAOqi estándar
    'control_server': 6671,  # WebSocket control principal
    'logger': 6672,          # WebSocket logging
    'video_stream': 8080,    # Stream de video HTTP
    'video_udp': 8081        # Video UDP
}

# IPs comunes
DEFAULT_IPS = {
    'localhost': '127.0.0.1',
    'nao_default': '192.168.1.100',  # IP típica de NAO
    'nao_ethernet': '169.254.1.1'    # IP ethernet directa
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE LOGGING Y MONITOREO  
# ═══════════════════════════════════════════════════════════════════════════════

# Configuración de archivos de log
LOG_CONFIG = {
    'max_history': 500,
    'log_file': '/tmp/nao_system.log',
    'csv_columns': ['timestamp', 'Walking'] + GAIT_TARGETS + [
        'FSR_Left', 'FSR_Right', 'FSR_Total', 
        'AccX', 'AccY', 'AccZ', 'GyroX', 'GyroY', 'AngleX', 'AngleY'
    ]
}

# Módulos del sistema para logging
SYSTEM_MODULES = [
    'LAUNCHER', 'CONTROL', 'CAMERA', 'ADAPTIVE', 'LOGGER', 'MONITOR'
]

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE MODELOS Y RUTAS
# ═══════════════════════════════════════════════════════════════════════════════

# Directorios de modelos
MODEL_DIRECTORIES = {
    'lightgbm_automl': 'models_npz_automl',
    'randomforest': 'models',  # Legado
    'datasets': 'datasets/walks',
    'logs': 'logs',
    'analysis': 'analysis'
}

# Archivos de modelo esperados
MODEL_FILES = {
    'feature_scaler': 'feature_scaler.npz',
    'lightgbm_models': [
        'lightgbm_model_StepHeight.npz',
        'lightgbm_model_MaxStepX.npz', 
        'lightgbm_model_MaxStepY.npz',
        'lightgbm_model_MaxStepTheta.npz',
        'lightgbm_model_Frequency.npz'
    ]
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN ADAPTATIVA
# ═══════════════════════════════════════════════════════════════════════════════

# Modos de operación del sistema adaptativo
ADAPTIVE_MODES = {
    'TRAINING': 'training',     # Usa predicciones ML para explorar
    'PRODUCTION': 'production'  # Converge hacia parámetros óptimos fijos
}

# Parámetros del sistema adaptativo
ADAPTIVE_CONFIG = {
    'enabled': True,
    'mode': ADAPTIVE_MODES['PRODUCTION'],  # Modo por defecto: PRODUCCIÓN
    'update_frequency': 10,    # Hz
    'smoothing_alpha': 0.15,   # Factor de suavizado EMA
    'watchdog_timeout': 3.0,   # Segundos sin comando para parar
    'stability_threshold': 0.01,
    
    # Configuración específica por modo
    'training': {
        'use_ml_predictions': True,
        'target_params': None,  # No hay target fijo
        'convergence_rate': 0.1
    },
    'production': {
        'use_ml_predictions': False,
        'target_params': OPTIMAL_GRASS_PARAMS,  # Converge hacia parámetros óptimos
        'convergence_rate': 0.05  # Más lento para estabilidad
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES DE CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def get_naoqi_sensor_keys():
    """Obtener todas las claves de sensores NAOqi necesarias"""
    return list(SENSOR_MAPPINGS.values())

def get_feature_sensor_mapping():
    """Obtener mapeo completo feature -> sensor NAOqi"""
    return SENSOR_MAPPINGS.copy()

def validate_gait_params(params):
    """Validar que los parámetros de gait estén en rangos válidos"""
    validated = {}
    for param, value in params.items():
        if param in GAIT_PARAM_RANGES:
            min_val, max_val = GAIT_PARAM_RANGES[param]
            validated[param] = max(min_val, min(max_val, float(value)))
        else:
            validated[param] = value
    return validated

def clamp_velocity(vx, vy, wz):
    """Aplicar límites de velocidad"""
    vx = max(VELOCITY_LIMITS['vx_min'], min(VELOCITY_LIMITS['vx_max'], vx))
    vy = max(VELOCITY_LIMITS['vy_min'], min(VELOCITY_LIMITS['vy_max'], vy))
    wz = max(VELOCITY_LIMITS['wz_min'], min(VELOCITY_LIMITS['wz_max'], wz))
    return vx, vy, wz

def get_optimal_grass_gait():
    """Obtener parámetros óptimos para pasto sintético como lista de pares"""
    return [[param, value] for param, value in OPTIMAL_GRASS_PARAMS.items()]

def get_adaptive_target_params(mode):
    """Obtener parámetros objetivo según el modo adaptativo"""
    if mode == ADAPTIVE_MODES['PRODUCTION']:
        return OPTIMAL_GRASS_PARAMS.copy()
    else:
        return None  # Training mode - sin target fijo

def get_default_gait():
    """Obtener parámetros de gait por defecto como lista de pares"""
    return [[param, value] for param, value in DEFAULT_GAIT_PARAMS.items()]

# ═══════════════════════════════════════════════════════════════════════════════
# INFORMACIÓN DEL SISTEMA
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_INFO = {
    'version': '2.1.0',
    'name': 'NAO Control System',
    'description': 'Sistema de control adaptativo para robot NAO con LightGBM AutoML',
    'author': 'NAO Control Team',
    'python_compatibility': ['2.7', '3.x'],
    'naoqi_version': '2.8+',
    'last_updated': '2025-09-02'
}

if __name__ == "__main__":
    print("📋 NAO CONTROL SYSTEM - CONFIGURACIÓN")
    print("=" * 40)
    print("Versión: {}".format(SYSTEM_INFO['version']))
    print("Features ML: {}".format(len(FEATURE_ORDER)))
    print("Parámetros Gait: {}".format(len(GAIT_TARGETS)))
    print("Sensores NAOqi: {}".format(len(SENSOR_MAPPINGS)))
    print("Puertos sistema: {}".format(list(PORTS.keys())))
    print("\n✅ Configuración cargada correctamente")
