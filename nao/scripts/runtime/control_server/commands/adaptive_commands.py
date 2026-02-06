#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
adaptive_commands.py - Comandos de IA adaptativa LightGBM

Implementa comandos para controlar el sistema de caminata adaptativa
basado en LightGBM AutoML usando Command Pattern.
"""

from __future__ import print_function
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand


class AdaptiveLightGBMCommand(BaseCommand):
    """Comando para controlar sistema adaptativo LightGBM."""
    
    def __init__(self, nao_facade, logger, adaptive_walker=None, adaptive_state=None):
        """
        Inicializar comando con referencias al sistema adaptativo.
        
        Args:
            nao_facade: Facade NAO
            logger: Logger
            adaptive_walker: Instancia de AdaptiveWalkLightGBM
            adaptive_state: Diccionario compartido con estado adaptativo
        """
        super(AdaptiveLightGBMCommand, self).__init__(nao_facade, logger)
        self.adaptive_walker = adaptive_walker
        self.adaptive_state = adaptive_state or {"enabled": False, "mode": "auto", "slip": False, "last_event": 0.0}
    
    def execute(self, message, websocket):
        """Ejecutar comando adaptiveLightGBM."""
        try:
            enable = message.get("enabled", True)
            mode = str(message.get("mode", self.adaptive_state.get("mode", "auto")))
            
            if self.adaptive_walker:
                # Configurar estado adaptativo
                self.adaptive_state["enabled"] = enable
                
                if mode in ("auto", "slippery"):
                    self.adaptive_state["mode"] = mode
                
                self.adaptive_state["last_event"] = 0.0  # reset suave
                
                # Obtener estadísticas
                stats = {}
                if hasattr(self.adaptive_walker, 'get_stats'):
                    stats = self.adaptive_walker.get_stats()
                
                response = {
                    "adaptiveLightGBM": {
                        "enabled": enable,
                        "mode": self.adaptive_state["mode"],
                        "available": True,
                        "stats": stats
                    }
                }
                websocket.sendMessage(json.dumps(response))
                
                self.logger.info("LightGBM adaptativo {} - Modo: {} - Stats: {}".format(
                    "habilitado" if enable else "deshabilitado", 
                    self.adaptive_state["mode"], 
                    stats))
                return True
            else:
                response = {
                    "adaptiveLightGBM": {
                        "enabled": False,
                        "available": False,
                        "error": "LightGBM AutoML no disponible"
                    }
                }
                websocket.sendMessage(json.dumps(response))
                self.logger.warning("LightGBM adaptativo no disponible")
                return False
                
        except Exception as e:
            self.logger.error("Error controlando LightGBM: {}".format(e))
            websocket.sendMessage(json.dumps({"adaptiveLightGBM": {"error": str(e)}}))
            return False
    
    def get_action_name(self):
        return "adaptiveLightGBM"


class GetLightGBMStatsCommand(BaseCommand):
    """Comando para obtener estadísticas del sistema LightGBM."""
    
    def __init__(self, nao_facade, logger, adaptive_walker=None):
        super(GetLightGBMStatsCommand, self).__init__(nao_facade, logger)
        self.adaptive_walker = adaptive_walker
    
    def execute(self, message, websocket):
        """Ejecutar comando getLightGBMStats."""
        try:
            if self.adaptive_walker:
                stats = {}
                if hasattr(self.adaptive_walker, 'get_stats'):
                    stats = self.adaptive_walker.get_stats()
                
                websocket.sendMessage(json.dumps({"lightGBMStats": stats}))
                self.logger.debug("Estadísticas LightGBM enviadas: {}".format(stats))
                return True
            else:
                websocket.sendMessage(json.dumps({
                    "lightGBMStats": {"error": "LightGBM no disponible"}
                }))
                self.logger.warning("LightGBM no disponible para estadísticas")
                return False
                
        except Exception as e:
            self.logger.error("Error obteniendo estadísticas LightGBM: {}".format(e))
            websocket.sendMessage(json.dumps({"lightGBMStats": {"error": str(e)}}))
            return False
    
    def get_action_name(self):
        return "getLightGBMStats"


class SetAdaptiveModeCommand(BaseCommand):
    """Comando para cambiar modo del sistema adaptativo."""
    
    def __init__(self, nao_facade, logger, adaptive_walker=None):
        super(SetAdaptiveModeCommand, self).__init__(nao_facade, logger)
        self.adaptive_walker = adaptive_walker
    
    def execute(self, message, websocket):
        """Ejecutar comando setAdaptiveMode."""
        try:
            mode = message.get("mode", "")
            
            if self.adaptive_walker and mode in ["training", "production"]:
                self.adaptive_walker.set_mode(mode)
                current_mode = self.adaptive_walker.get_mode()
                
                self.logger.info("Modo adaptativo cambiado a: {}".format(current_mode))
                websocket.sendMessage(json.dumps({
                    "setAdaptiveMode": {
                        "success": True,
                        "mode": current_mode
                    }
                }))
                return True
                
            elif not self.adaptive_walker:
                websocket.sendMessage(json.dumps({
                    "setAdaptiveMode": {
                        "success": False,
                        "error": "Adaptive walker no disponible"
                    }
                }))
                return False
            else:
                websocket.sendMessage(json.dumps({
                    "setAdaptiveMode": {
                        "success": False,
                        "error": "Modo inválido. Use 'training' o 'production'"
                    }
                }))
                return False
                
        except Exception as e:
            self.logger.error("Error cambiando modo adaptativo: {}".format(e))
            websocket.sendMessage(json.dumps({
                "setAdaptiveMode": {
                    "success": False,
                    "error": str(e)
                }
            }))
            return False
    
    def get_action_name(self):
        return "setAdaptiveMode"


class GetAdaptiveModeCommand(BaseCommand):
    """Comando para obtener modo actual del sistema adaptativo."""
    
    def __init__(self, nao_facade, logger, adaptive_walker=None):
        super(GetAdaptiveModeCommand, self).__init__(nao_facade, logger)
        self.adaptive_walker = adaptive_walker
    
    def execute(self, message, websocket):
        """Ejecutar comando getAdaptiveMode."""
        try:
            if self.adaptive_walker:
                current_mode = self.adaptive_walker.get_mode()
                websocket.sendMessage(json.dumps({
                    "getAdaptiveMode": {
                        "success": True,
                        "mode": current_mode
                    }
                }))
                return True
            else:
                websocket.sendMessage(json.dumps({
                    "getAdaptiveMode": {
                        "success": False,
                        "error": "Adaptive walker no disponible"
                    }
                }))
                return False
                
        except Exception as e:
            self.logger.error("Error obteniendo modo adaptativo: {}".format(e))
            websocket.sendMessage(json.dumps({
                "getAdaptiveMode": {
                    "success": False,
                    "error": str(e)
                }
            }))
            return False
    
    def get_action_name(self):
        return "getAdaptiveMode"


class PredictGaitCommand(BaseCommand):
    """Comando para obtener predicción de parámetros de marcha."""
    
    def __init__(self, nao_facade, logger, adaptive_walker=None):
        super(PredictGaitCommand, self).__init__(nao_facade, logger)
        self.adaptive_walker = adaptive_walker
    
    def execute(self, message, websocket):
        """Ejecutar comando predictGait."""
        try:
            if self.adaptive_walker:
                # Obtener predicción
                predicted_params = self.adaptive_walker.predict_gait_parameters()
                
                if predicted_params:
                    websocket.sendMessage(json.dumps({
                        "predictGait": {
                            "success": True,
                            "parameters": predicted_params
                        }
                    }))
                    self.logger.info("Predicción de gait: {}".format(predicted_params))
                    return True
                else:
                    websocket.sendMessage(json.dumps({
                        "predictGait": {
                            "success": False,
                            "error": "No se pudo generar predicción"
                        }
                    }))
                    return False
            else:
                websocket.sendMessage(json.dumps({
                    "predictGait": {
                        "success": False,
                        "error": "Adaptive walker no disponible"
                    }
                }))
                return False
                
        except Exception as e:
            self.logger.error("Error en predicción de gait: {}".format(e))
            websocket.sendMessage(json.dumps({
                "predictGait": {
                    "success": False,
                    "error": str(e)
                }
            }))
            return False
    
    def get_action_name(self):
        return "predictGait"
