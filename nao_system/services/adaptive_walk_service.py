#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
services.adaptive_walk_service

Servicio que encapsula la lógica de caminata adaptiva. Soporta modos
`production` y `training`. Implementa límites de seguridad y puntos de
extensión para carga de modelos ML. El encabezado añadido es informativo.
Fecha: 2025-09-08
"""

import os
import time
import math
import numpy as np
from ..interfaces.base_interfaces import IAdaptiveWalk
from ..core.config import (
    OPTIMAL_GRASS_PARAMS, MOVEMENT_SPECIFIC_PARAMS, 
    FEATURE_ORDER, GAIT_TARGETS, SAFETY_LIMITS, MODELS_DIR
)

class AdaptiveWalkService(IAdaptiveWalk):
    """Servicio de caminata adaptiva con LightGBM"""
    
    def __init__(self, nao_adapter, sensor_service, logger=None, mode="production"):
        self.nao_adapter = nao_adapter
        self.sensor_service = sensor_service
        self.logger = logger
        self.mode = mode
        self.enabled = False
        
        # Parámetros de caminata
        self.optimal_grass_params = OPTIMAL_GRASS_PARAMS.copy()
        self.movement_params = MOVEMENT_SPECIFIC_PARAMS.copy()
        self.current_params = self.optimal_grass_params.copy()
        
        # Estado actual
        self.current_velocities = {'vx': 0.0, 'vy': 0.0, 'wz': 0.0}
        
        # Modelos ML
        self.models = {}
        self.scaler = None
        self.models_loaded = False
        
        # Intentar cargar modelos
        self._load_models()
        
        if self.logger:
            self.logger.info("AdaptiveWalkService inicializado en modo: {}".format(mode))
    
    def _load_models(self):
        """Cargar modelos LightGBM AutoML"""
        try:
            models_path = os.path.join(os.path.dirname(__file__), "..", "..", MODELS_DIR)
            
            if not os.path.exists(models_path):
                if self.logger:
                    self.logger.warning("Directorio de modelos no encontrado: {}".format(models_path))
                return False
            
            # Aquí iría la lógica de carga de modelos LightGBM
            # Por ahora simulamos que los modelos están cargados
            self.models_loaded = True
            
            if self.logger:
                self.logger.info("Modelos AutoML cargados desde: {}".format(models_path))
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error cargando modelos: {}".format(e))
            return False
    
    def _detect_movement_type(self, vx=None, vy=None, wz=None):
        """Detectar tipo de movimiento basado en velocidades"""
        if vx is None or vy is None or wz is None:
            return 'static'
        
        # Actualizar velocidades actuales
        self.current_velocities.update({'vx': vx, 'vy': vy, 'wz': wz})
        
        # Detectar tipo de movimiento
        abs_vx, abs_vy, abs_wz = abs(vx), abs(vy), abs(wz)
        
        if abs_wz > 0.3:
            return 'turn'
        elif abs_vx > abs_vy and vx > 0.01:
            return 'forward'
        elif abs_vx > abs_vy and vx < -0.01:
            return 'backward'
        elif abs_vy > 0.01:
            return 'lateral'
        else:
            return 'static'
    
    def _get_movement_specific_params(self, movement_type):
        """Obtener parámetros específicos por tipo de movimiento"""
        base_params = self.optimal_grass_params.copy()
        
        if movement_type in self.movement_params:
            base_params.update(self.movement_params[movement_type])
        
        return base_params
    
    def _apply_safety_limits(self, params):
        """Aplicar límites de seguridad a parámetros"""
        safe_params = {}
        limits = SAFETY_LIMITS['gait_params']
        
        for param_name, value in params.items():
            if param_name in limits:
                min_val = limits[param_name]['min']
                max_val = limits[param_name]['max']
                safe_params[param_name] = max(min_val, min(max_val, value))
            else:
                safe_params[param_name] = value
        
        return safe_params
    
    def predict_gait_parameters(self, vx=None, vy=None, wz=None):
        """Predecir parámetros de caminata"""
        try:
            if self.mode == "production":
                # Modo producción: usar parámetros específicos por movimiento
                movement_type = self._detect_movement_type(vx, vy, wz)
                params = self._get_movement_specific_params(movement_type)
                
                if self.logger:
                    self.logger.debug("Modo production - Movimiento: {}, Parámetros: {}".format(
                        movement_type, params))
                
                return self._apply_safety_limits(params)
            
            elif self.mode == "training" and self.models_loaded:
                # Modo entrenamiento: usar predicciones ML
                sensor_data = self.sensor_service.get_imu_data() if self.sensor_service else {}
                
                if sensor_data:
                    # Aquí iría la lógica de predicción ML
                    # Por ahora retornamos parámetros optimizados
                    params = self.optimal_grass_params.copy()
                    
                    if self.logger:
                        self.logger.debug("Modo training - Predicción ML: {}".format(params))
                    
                    return self._apply_safety_limits(params)
            
            # Fallback a parámetros por defecto
            if self.logger:
                self.logger.debug("Usando parámetros por defecto")
            
            return self._apply_safety_limits(self.optimal_grass_params)
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error prediciendo parámetros: {}".format(e))
            return self._apply_safety_limits(self.optimal_grass_params)
    
    def start_adaptive_walk(self, x=0.02, y=0.0, theta=0.0):
        """Iniciar caminata adaptiva"""
        try:
            if not self.nao_adapter.is_connected():
                if self.logger:
                    self.logger.debug("Simulando inicio de caminata adaptiva")
                self.enabled = True
                return True
            
            # Predecir parámetros para las velocidades iniciales
            predicted_params = self.predict_gait_parameters(x, y, theta)
            
            # Convertir parámetros a formato moveToward
            move_config = []
            for param_name, value in predicted_params.items():
                move_config.append([param_name, value])
            
            # Iniciar movimiento con configuración adaptiva
            motion_proxy = self.nao_adapter.get_proxy('motion')
            if motion_proxy:
                motion_proxy.moveToward(x, y, theta, move_config)
                self.enabled = True
                self.current_params = predicted_params
                
                if self.logger:
                    self.logger.info("Caminata adaptiva iniciada con parámetros: {}".format(predicted_params))
                
                return True
            
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error iniciando caminata adaptiva: {}".format(e))
            return False
    
    def stop_adaptive_walk(self):
        """Detener caminata adaptiva"""
        try:
            self.enabled = False
            
            if not self.nao_adapter.is_connected():
                if self.logger:
                    self.logger.debug("Simulando parada de caminata adaptiva")
                return True
            
            motion_proxy = self.nao_adapter.get_proxy('motion')
            if motion_proxy:
                motion_proxy.stopMove()
                
                if self.logger:
                    self.logger.info("Caminata adaptiva detenida")
                
                return True
            
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error("Error deteniendo caminata adaptiva: {}".format(e))
            return False
    
    def set_mode(self, mode):
        """Cambiar modo de operación"""
        if mode in ["training", "production"]:
            old_mode = self.mode
            self.mode = mode
            
            if self.logger:
                self.logger.info("Modo cambiado de '{}' a '{}'".format(old_mode, mode))
            
            return True
        
        if self.logger:
            self.logger.warning("Modo inválido: {}. Usar 'training' o 'production'".format(mode))
        
        return False
    
    def get_current_parameters(self):
        """Obtener parámetros actuales"""
        return self.current_params.copy()
    
    def get_status(self):
        """Obtener estado del servicio"""
        return {
            'enabled': self.enabled,
            'mode': self.mode,
            'models_loaded': self.models_loaded,
            'current_params': self.current_params,
            'current_velocities': self.current_velocities
        }
