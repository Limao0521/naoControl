#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
gait_utils.py - Utilidades para configuración de marcha

Funciones auxiliares para manejo de parámetros de gait,
conversiones, límites y presets.
"""

from __future__ import print_function
import math


# === Claves válidas para configuración de gait ===
ALLOWED_GAIT_KEYS = set([
    "MaxStepX", "MaxStepY", "MaxStepTheta", "MaxStepFrequency",
    "StepHeight", "TorsoWx", "TorsoWy", "Frequency"
])

# === Presets de marcha para diferentes superficies ===
GAIT_PRESETS = {
    "default": [],
    
    "grass": [
        ["MaxStepX", 0.04],
        ["MaxStepY", 0.14],
        ["MaxStepTheta", 0.35],
        ["StepHeight", 0.025],
        ["Frequency", 0.4]
    ],
    
    "slippery": [
        ["MaxStepX", 0.020],
        ["MaxStepY", 0.10],
        ["MaxStepTheta", 0.18],
        ["StepHeight", 0.015],
        ["Frequency", 0.35]
    ],
    
    "carpet": [
        ["MaxStepX", 0.05],
        ["MaxStepY", 0.16],
        ["MaxStepTheta", 0.40],
        ["StepHeight", 0.030],
        ["Frequency", 0.45]
    ],
    
    "fast": [
        ["MaxStepX", 0.06],
        ["MaxStepY", 0.16],
        ["MaxStepTheta", 0.50],
        ["StepHeight", 0.020],
        ["Frequency", 0.55]
    ],
    
    "careful": [
        ["MaxStepX", 0.025],
        ["MaxStepY", 0.08],
        ["MaxStepTheta", 0.20],
        ["StepHeight", 0.020],
        ["Frequency", 0.30]
    ],
    
    "competition": [
        ["MaxStepX", 0.04],
        ["MaxStepY", 0.14],
        ["MaxStepTheta", 0.35],
        ["StepHeight", 0.025],
        ["Frequency", 0.4]
    ]
}


# === Funciones matemáticas básicas ===

def clamp(v, lo, hi):
    """
    Limitar un valor a un rango.
    
    Args:
        v: Valor a limitar
        lo: Límite inferior
        hi: Límite superior
        
    Returns:
        Valor limitado al rango [lo, hi]
    """
    return lo if v < lo else (hi if v > hi else v)


def lerp(a, b, t):
    """
    Interpolación lineal entre dos valores.
    
    Args:
        a: Valor inicial
        b: Valor final
        t: Factor de interpolación (0.0 a 1.0)
        
    Returns:
        Valor interpolado
    """
    return (1.0 - t) * a + t * b


def ema(prev, current, alpha):
    """
    Media móvil exponencial.
    
    Args:
        prev: Valor previo
        current: Valor actual
        alpha: Factor de suavizado (0.0 a 1.0)
        
    Returns:
        Nuevo valor suavizado
    """
    return (1.0 - alpha) * prev + alpha * current


def smooth_value(current, target, rate):
    """
    Suavizar transición hacia un objetivo.
    
    Args:
        current: Valor actual
        target: Valor objetivo
        rate: Tasa de cambio por ciclo
        
    Returns:
        Nuevo valor más cercano al objetivo
    """
    if current < target:
        return min(target, current + rate)
    elif current > target:
        return max(target, current - rate)
    return target


# === Conversión de configuraciones ===

def pairs_to_dict(pairs):
    """
    Convertir lista de pares a diccionario.
    
    Args:
        pairs: Lista de [key, value] pares
        
    Returns:
        dict: Diccionario {key: value}
    """
    if not pairs:
        return {}
    
    d = {}
    for k, v in pairs:
        d[k] = float(v)
    return d


def dict_to_pairs(d):
    """
    Convertir diccionario a lista de pares.
    
    Args:
        d: Diccionario {key: value}
        
    Returns:
        list: Lista de [key, value]
    """
    if not d:
        return []
    
    return [[k, float(v)] for k, v in d.items()]


def merge_pairs(base_pairs, override_pairs):
    """
    Combinar dos configuraciones de pares.
    
    Args:
        base_pairs: Configuración base
        override_pairs: Configuración que sobrescribe
        
    Returns:
        list: Lista combinada de pares
    """
    d = pairs_to_dict(base_pairs) if base_pairs else {}
    d.update(pairs_to_dict(override_pairs) if override_pairs else {})
    return dict_to_pairs(d)


def config_to_move_list(config_dict_or_list):
    """
    Convertir configuración a lista de pares válidos para NAOqi.
    
    Acepta dict o lista y devuelve lista [[key, val], ...]
    solo con claves válidas.
    
    Args:
        config_dict_or_list: dict o lista de pares
        
    Returns:
        list: Lista de [key, value] solo con claves válidas
    """
    pairs = []
    
    if isinstance(config_dict_or_list, dict):
        items = config_dict_or_list.items()
    elif isinstance(config_dict_or_list, list):
        items = config_dict_or_list
    else:
        return []
    
    for k, v in items:
        if k in ALLOWED_GAIT_KEYS:
            pairs.append([k, float(v)])
    
    return pairs


# === Límites de velocidad ===

# Límites absolutos máximos para velocidades
VELOCITY_LIMITS = {
    "vx": {"min": -0.4, "max": 0.4},
    "vy": {"min": -0.25, "max": 0.25},
    "wz": {"min": -1.0, "max": 1.0}
}


def apply_absolute_limits(vx, vy, wz):
    """
    Aplicar límites absolutos a velocidades de caminar.
    
    Estos límites se aplican SIEMPRE, independientemente de otros sistemas.
    
    Args:
        vx: Velocidad en X (adelante/atrás)
        vy: Velocidad en Y (izquierda/derecha)
        wz: Velocidad angular
        
    Returns:
        tuple: (vx, vy, wz) limitados
    """
    vx = clamp(vx, VELOCITY_LIMITS["vx"]["min"], VELOCITY_LIMITS["vx"]["max"])
    vy = clamp(vy, VELOCITY_LIMITS["vy"]["min"], VELOCITY_LIMITS["vy"]["max"])
    wz = clamp(wz, VELOCITY_LIMITS["wz"]["min"], VELOCITY_LIMITS["wz"]["max"])
    
    return vx, vy, wz


def normalize_velocity(vx, vy):
    """
    Normalizar vector de velocidad si excede magnitud 1.0.
    
    Args:
        vx: Velocidad en X
        vy: Velocidad en Y
        
    Returns:
        tuple: (vx, vy) normalizados
    """
    norm = math.hypot(vx, vy)
    if norm > 1.0:
        vx = vx / norm
        vy = vy / norm
    return vx, vy


# === Suavizado de gait ===

class GaitSmoother(object):
    """
    Clase para suavizar transiciones de parámetros de gait.
    """
    
    def __init__(self, alpha=0.15):
        """
        Inicializar suavizador.
        
        Args:
            alpha: Factor de suavizado (0.0 a 1.0, más bajo = más suave)
        """
        self.alpha = alpha
        self.current = {}
    
    def smooth(self, target_dict):
        """
        Suavizar transición hacia valores objetivo.
        
        Args:
            target_dict: Diccionario con valores objetivo
            
        Returns:
            dict: Valores suavizados
        """
        if not self.current:
            self.current = target_dict.copy()
            return self.current
        
        all_keys = set(self.current.keys()) | set(target_dict.keys())
        
        for k in all_keys:
            current_val = self.current.get(k, target_dict.get(k, 0.0))
            target_val = target_dict.get(k, current_val)
            self.current[k] = lerp(current_val, target_val, self.alpha)
        
        return self.current
    
    def smooth_pairs(self, target_pairs):
        """
        Suavizar transición de lista de pares.
        
        Args:
            target_pairs: Lista de [key, value] objetivo
            
        Returns:
            list: Pares suavizados
        """
        target_dict = pairs_to_dict(target_pairs)
        smoothed_dict = self.smooth(target_dict)
        return dict_to_pairs(smoothed_dict)
    
    def reset(self):
        """Resetear estado interno."""
        self.current = {}


# === Validación ===

def validate_gait_config(config):
    """
    Validar configuración de gait.
    
    Args:
        config: dict o lista de pares
        
    Returns:
        tuple: (is_valid, errors)
    """
    errors = []
    
    if isinstance(config, dict):
        items = config.items()
    elif isinstance(config, list):
        items = config
    else:
        return False, ["Config debe ser dict o lista de pares"]
    
    for k, v in items:
        if k not in ALLOWED_GAIT_KEYS:
            errors.append("Clave inválida: {}".format(k))
        
        try:
            float(v)
        except (TypeError, ValueError):
            errors.append("Valor inválido para {}: {}".format(k, v))
    
    return len(errors) == 0, errors


def get_gait_preset(name):
    """
    Obtener preset de gait por nombre.
    
    Args:
        name: Nombre del preset
        
    Returns:
        list: Lista de pares o None si no existe
    """
    return GAIT_PRESETS.get(name)


def list_gait_presets():
    """
    Listar nombres de presets disponibles.
    
    Returns:
        list: Lista de nombres de presets
    """
    return list(GAIT_PRESETS.keys())
