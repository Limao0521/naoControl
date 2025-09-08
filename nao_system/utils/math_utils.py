#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
utils.math_utils

Funciones utilitarias numéricas y clases auxiliares usadas por servicios.
Este encabezado es informativo y no altera la lógica existente.
Fecha: 2025-09-08
"""

import math

def clamp(value, min_val, max_val):
    """Limitar valor entre min y max"""
    return max(min_val, min(max_val, value))

def lerp(a, b, t):
    """Interpolación lineal"""
    return a + (b - a) * t

def ema(prev, x, alpha):
    """Media móvil exponencial"""
    return alpha * x + (1.0 - alpha) * prev

def safe_float(value, default=0.0):
    """Convertir a float de forma segura"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Convertir a int de forma segura"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def validate_velocity(vx, vy, wz, max_limits=None):
    """Validar y limitar velocidades"""
    if max_limits is None:
        max_limits = {'vx': 0.3, 'vy': 0.3, 'wz': 1.0}
    
    vx = clamp(safe_float(vx), -max_limits['vx'], max_limits['vx'])
    vy = clamp(safe_float(vy), -max_limits['vy'], max_limits['vy']) 
    wz = clamp(safe_float(wz), -max_limits['wz'], max_limits['wz'])
    
    return vx, vy, wz

def calculate_distance(x1, y1, x2, y2):
    """Calcular distancia euclidiana"""
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def normalize_angle(angle):
    """Normalizar ángulo a rango [-pi, pi]"""
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle

def dict_to_pairs(data_dict):
    """Convertir diccionario a lista de pares [key, value]"""
    return [[key, value] for key, value in data_dict.items()]

def pairs_to_dict(pairs_list):
    """Convertir lista de pares a diccionario"""
    return {pair[0]: pair[1] for pair in pairs_list if len(pair) >= 2}

def merge_dicts(base_dict, override_dict):
    """Fusionar diccionarios, override tiene prioridad"""
    result = base_dict.copy()
    result.update(override_dict)
    return result

class MovingAverage(object):
    """Clase para calcular media móvil"""
    
    def __init__(self, window_size=10):
        self.window_size = window_size
        self.values = []
    
    def add_value(self, value):
        """Agregar nuevo valor"""
        self.values.append(value)
        if len(self.values) > self.window_size:
            self.values.pop(0)
    
    def get_average(self):
        """Obtener promedio actual"""
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)
    
    def reset(self):
        """Resetear valores"""
        self.values = []

class RateLimiter(object):
    """Limitador de velocidad para operaciones"""
    
    def __init__(self, max_calls_per_second=10):
        self.max_calls_per_second = max_calls_per_second
        self.min_interval = 1.0 / max_calls_per_second
        self.last_call_time = 0.0
    
    def can_proceed(self):
        """Verificar si se puede proceder"""
        import time
        current_time = time.time()
        
        if current_time - self.last_call_time >= self.min_interval:
            self.last_call_time = current_time
            return True
        
        return False
    
    def wait_if_needed(self):
        """Esperar si es necesario para respetar el límite"""
        import time
        current_time = time.time()
        time_since_last = current_time - self.last_call_time
        
        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)
        
        self.last_call_time = time.time()
