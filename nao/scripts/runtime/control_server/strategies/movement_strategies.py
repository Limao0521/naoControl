#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
movement_strategies.py - Strategy Pattern para diferentes tipos de movimiento

Define diferentes estrategias de movimiento: manual, adaptativo, etc.
Permite cambiar algoritmos de movimiento dinámicamente.
"""

from __future__ import print_function
import math
import time
from abc import ABCMeta, abstractmethod

class MovementStrategy(object):
    """Interfaz base para estrategias de movimiento."""
    __metaclass__ = ABCMeta
    
    def __init__(self, nao_facade, logger):
        self.nao = nao_facade
        self.logger = logger
    
    @abstractmethod
    def execute_movement(self, vx, vy, wz, config=None):
        """
        Ejecutar movimiento con la estrategia específica.
        
        Args:
            vx, vy, wz (float): Velocidades de movimiento
            config: Configuración de gait opcional
            
        Returns:
            bool: True si el movimiento fue exitoso
        """
        pass
    
    @abstractmethod
    def get_strategy_name(self):
        """Obtener nombre de la estrategia."""
        pass

class ManualMovementStrategy(MovementStrategy):
    """Estrategia de movimiento manual con límites absolutos."""
    
    def execute_movement(self, vx, vy, wz, config=None):
        """Ejecutar movimiento manual con límites de seguridad."""
        try:
            # Aplicar límites absolutos forzados
            vx, vy, wz = self._apply_absolute_limits(vx, vy, wz)
            
            # Normalizar magnitud del vector (x,y) si excede 1.0
            norm = math.hypot(vx, vy)
            if norm > 1.0:
                vx, vy = vx/norm, vy/norm
            
            # Ejecutar movimiento
            success = self.nao.move_toward(vx, vy, wz, config)
            
            self.logger.info("Manual Movement: moveToward(vx={:.2f}, vy={:.2f}, wz={:.2f}) - {}".format(
                vx, vy, wz, "SUCCESS" if success else "FAILED"))
            
            return success
            
        except Exception as e:
            self.logger.error("Error en movimiento manual: {}".format(e))
            return False
    
    def _apply_absolute_limits(self, vx, vy, wz):
        """Aplicar límites absolutos a las velocidades."""
        # Límites para pasto
        if vx > 0.4:
            vx = 0.4
        elif vx < -0.4:
            vx = -0.4

        if vy > 0.25:
            vy = 0.25
        elif vy < -0.25:
            vy = -0.25
        
        # wz sin límites adicionales (se deja para otros sistemas)
        return vx, vy, wz
    
    def get_strategy_name(self):
        return "manual"

class AdaptiveMovementStrategy(MovementStrategy):
    """Estrategia de movimiento adaptativo con LightGBM."""
    
    def __init__(self, nao_facade, logger, adaptive_walker=None):
        super(AdaptiveMovementStrategy, self).__init__(nao_facade, logger)
        self.adaptive_walker = adaptive_walker
        self.manual_fallback = ManualMovementStrategy(nao_facade, logger)
    
    def execute_movement(self, vx, vy, wz, config=None):
        """Ejecutar movimiento adaptativo con predicción LightGBM."""
        try:
            # Intentar obtener parámetros adaptativos
            adaptive_config = self._get_adaptive_config()
            
            if adaptive_config:
                # Usar configuración adaptativa
                final_config = adaptive_config
                strategy_used = "LightGBM"
            else:
                # Fallback a configuración manual
                final_config = config
                strategy_used = "Manual_Fallback"
            
            # Aplicar límites de seguridad (igual que manual)
            vx, vy, wz = self.manual_fallback._apply_absolute_limits(vx, vy, wz)
            
            # Normalizar magnitud
            norm = math.hypot(vx, vy)
            if norm > 1.0:
                vx, vy = vx/norm, vy/norm
            
            # Ejecutar movimiento
            success = self.nao.move_toward(vx, vy, wz, final_config)
            
            self.logger.info("Adaptive Movement: moveToward(vx={:.2f}, vy={:.2f}, wz={:.2f}) cfg={} [{}] - {}".format(
                vx, vy, wz, final_config, strategy_used, "SUCCESS" if success else "FAILED"))
            
            return success
            
        except Exception as e:
            self.logger.error("Error en movimiento adaptativo: {}".format(e))
            # Fallback a movimiento manual
            return self.manual_fallback.execute_movement(vx, vy, wz, config)
    
    def _get_adaptive_config(self):
        """Obtener configuración adaptativa desde LightGBM."""
        if not self.adaptive_walker:
            return None
        
        try:
            adaptive_params = self.adaptive_walker.predict_gait_parameters()
            if adaptive_params:
                # Convertir a formato esperado por NAOqi
                config = []
                for param, value in adaptive_params.items():
                    if param in ["MaxStepX", "MaxStepY", "MaxStepTheta", "StepHeight", "Frequency"]:
                        config.append([param, float(value)])
                
                self.logger.debug("Configuración adaptativa: {}".format(adaptive_params))
                return config if config else None
        except Exception as e:
            self.logger.warning("Error obteniendo configuración adaptativa: {}".format(e))
        
        return None
    
    def get_strategy_name(self):
        return "adaptive"

class CautiousMovementStrategy(MovementStrategy):
    """Estrategia de movimiento cautelosa con límites muy restrictivos."""
    
    def execute_movement(self, vx, vy, wz, config=None):
        """Ejecutar movimiento cauteloso con límites muy restrictivos."""
        try:
            # Límites aún más restrictivos
            vx = max(-0.2, min(0.2, vx))
            vy = max(-0.15, min(0.15, vy))
            wz = max(-0.3, min(0.3, wz))
            
            # Normalizar
            norm = math.hypot(vx, vy)
            if norm > 0.5:  # Límite más bajo
                vx, vy = (vx/norm) * 0.5, (vy/norm) * 0.5
            
            # Ejecutar movimiento
            success = self.nao.move_toward(vx, vy, wz, config)
            
            self.logger.info("Cautious Movement: moveToward(vx={:.2f}, vy={:.2f}, wz={:.2f}) - {}".format(
                vx, vy, wz, "SUCCESS" if success else "FAILED"))
            
            return success
            
        except Exception as e:
            self.logger.error("Error en movimiento cauteloso: {}".format(e))
            return False
    
    def get_strategy_name(self):
        return "cautious"

class MovementContext(object):
    """
    Contexto para manejar diferentes estrategias de movimiento.
    Permite cambiar estrategias dinámicamente.
    """
    
    def __init__(self, nao_facade, logger, adaptive_walker=None):
        self.nao = nao_facade
        self.logger = logger
        
        # Crear todas las estrategias disponibles
        self.strategies = {
            'manual': ManualMovementStrategy(nao_facade, logger),
            'adaptive': AdaptiveMovementStrategy(nao_facade, logger, adaptive_walker),
            'cautious': CautiousMovementStrategy(nao_facade, logger)
        }
        
        # Estrategia por defecto
        self.current_strategy = self.strategies['manual']
        self.current_strategy_name = 'manual'
    
    def set_strategy(self, strategy_name):
        """
        Cambiar estrategia de movimiento.
        
        Args:
            strategy_name (str): Nombre de la estrategia ('manual', 'adaptive', 'cautious')
            
        Returns:
            bool: True si se cambió exitosamente
        """
        if strategy_name in self.strategies:
            self.current_strategy = self.strategies[strategy_name]
            self.current_strategy_name = strategy_name
            self.logger.info("Estrategia de movimiento cambiada a: {}".format(strategy_name))
            return True
        else:
            self.logger.warning("Estrategia desconocida: {}".format(strategy_name))
            return False
    
    def execute_movement(self, vx, vy, wz, config=None):
        """Ejecutar movimiento con la estrategia actual."""
        return self.current_strategy.execute_movement(vx, vy, wz, config)
    
    def get_current_strategy(self):
        """Obtener nombre de la estrategia actual."""
        return self.current_strategy_name
    
    def get_available_strategies(self):
        """Obtener lista de estrategias disponibles."""
        return list(self.strategies.keys())
    
    def get_strategy_info(self):
        """Obtener información detallada de estrategias."""
        return {
            'current': self.current_strategy_name,
            'available': self.get_available_strategies(),
            'descriptions': {
                'manual': 'Movimiento manual con límites de seguridad',
                'adaptive': 'Movimiento adaptativo con predicción LightGBM',
                'cautious': 'Movimiento cauteloso con límites muy restrictivos'
            }
        }