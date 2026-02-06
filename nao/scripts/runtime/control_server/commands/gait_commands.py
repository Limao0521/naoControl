#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
gait_commands.py - Comandos de configuración de marcha

Implementa comandos para configurar parámetros de marcha usando Command Pattern.
"""

from __future__ import print_function
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand


# Claves válidas para configuración de gait
ALLOWED_GAIT_KEYS = set([
    "MaxStepX", "MaxStepY", "MaxStepTheta", "MaxStepFrequency",
    "StepHeight", "TorsoWx", "TorsoWy", "Frequency"
])


def config_to_pairs(config):
    """
    Convertir configuración (dict o lista) a lista de pares válidos.
    
    Args:
        config: dict o lista de pares
        
    Returns:
        list: Lista de [key, value] solo con claves válidas
    """
    pairs = []
    
    if isinstance(config, dict):
        items = config.items()
    elif isinstance(config, list):
        items = config
    else:
        return []
    
    for k, v in items:
        if k in ALLOWED_GAIT_KEYS:
            pairs.append([k, float(v)])
    
    return pairs


def pairs_to_dict(pairs):
    """Convertir lista de pares a diccionario."""
    return {k: float(v) for k, v in pairs}


def dict_to_pairs(d):
    """Convertir diccionario a lista de pares."""
    return [[k, float(v)] for k, v in d.items()]


class GaitCommand(BaseCommand):
    """Comando para configurar parámetros de marcha."""
    
    def __init__(self, nao_facade, logger, gait_state=None):
        """
        Inicializar comando con estado compartido.
        
        Args:
            nao_facade: Facade NAO
            logger: Logger
            gait_state: Diccionario compartido con estado de gait
        """
        super(GaitCommand, self).__init__(nao_facade, logger)
        self.gait_state = gait_state or {"target": [], "applied": [], "source": "none"}
    
    def execute(self, message, websocket):
        """Ejecutar comando gait."""
        try:
            user_config = message.get("config", {})
            
            # Validar tipo de configuración
            if not isinstance(user_config, (dict, list)):
                self.send_error_response(websocket, "gait", 
                    "config debe ser dict o lista de pares")
                return False
            
            # Convertir a pares válidos
            gait_pairs = config_to_pairs(user_config)
            
            if not gait_pairs:
                self.send_error_response(websocket, "gait",
                    "No se encontraron parámetros válidos. Válidos: {}".format(
                        list(ALLOWED_GAIT_KEYS)))
                return False
            
            # Actualizar estado compartido
            self.gait_state["target"] = gait_pairs
            self.gait_state["source"] = "manual"
            
            # Responder con la configuración aplicada
            response = {"gaitApplied": gait_pairs}
            websocket.sendMessage(json.dumps(response))
            
            self.logger.info("Gait: Nueva configuración (manual) = {}".format(gait_pairs))
            return True
            
        except Exception as e:
            self.send_error_response(websocket, "gait", str(e))
            return False
    
    def get_action_name(self):
        return "gait"


class GetGaitCommand(BaseCommand):
    """Comando para obtener configuración de marcha actual."""
    
    def __init__(self, nao_facade, logger, gait_state=None):
        """
        Inicializar comando con estado compartido.
        
        Args:
            nao_facade: Facade NAO
            logger: Logger
            gait_state: Diccionario compartido con estado de gait
        """
        super(GetGaitCommand, self).__init__(nao_facade, logger)
        self.gait_state = gait_state or {"target": [], "applied": [], "source": "none"}
    
    def execute(self, message, websocket):
        """Ejecutar comando getGait."""
        try:
            applied = self.gait_state.get("applied", [])
            target = self.gait_state.get("target", [])
            source = self.gait_state.get("source", "none")
            
            response = {
                "gait": applied if applied else target,
                "target": target,
                "applied": applied,
                "source": source
            }
            
            websocket.sendMessage(json.dumps(response))
            self.logger.info("Gait: getGait → applied={} target={} source={}".format(
                applied, target, source))
            return True
            
        except Exception as e:
            self.send_error_response(websocket, "getGait", str(e))
            return False
    
    def get_action_name(self):
        return "getGait"


class ResetGaitCommand(BaseCommand):
    """Comando para resetear configuración de marcha a valores por defecto."""
    
    def __init__(self, nao_facade, logger, gait_state=None):
        super(ResetGaitCommand, self).__init__(nao_facade, logger)
        self.gait_state = gait_state or {"target": [], "applied": [], "source": "none"}
    
    def execute(self, message, websocket):
        """Ejecutar comando resetGait."""
        try:
            # Resetear a valores vacíos (NAOqi usará defaults)
            self.gait_state["target"] = []
            self.gait_state["applied"] = []
            self.gait_state["source"] = "none"
            
            response = {
                "resetGait": {
                    "success": True,
                    "gait": [],
                    "message": "Gait reseteado a valores por defecto de NAOqi"
                }
            }
            websocket.sendMessage(json.dumps(response))
            self.logger.info("Gait: Configuración reseteada a defaults")
            return True
            
        except Exception as e:
            self.send_error_response(websocket, "resetGait", str(e))
            return False
    
    def get_action_name(self):
        return "resetGait"


class GaitPresetsCommand(BaseCommand):
    """Comando para aplicar presets de configuración de marcha."""
    
    # Presets predefinidos para diferentes superficies
    PRESETS = {
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
        ]
    }
    
    def __init__(self, nao_facade, logger, gait_state=None):
        super(GaitPresetsCommand, self).__init__(nao_facade, logger)
        self.gait_state = gait_state or {"target": [], "applied": [], "source": "none"}
    
    def execute(self, message, websocket):
        """Ejecutar comando gaitPreset."""
        try:
            preset_name = message.get("preset", "default")
            
            if preset_name not in self.PRESETS:
                available = list(self.PRESETS.keys())
                self.send_error_response(websocket, "gaitPreset",
                    "Preset '{}' no existe. Disponibles: {}".format(preset_name, available))
                return False
            
            # Aplicar preset
            preset_config = self.PRESETS[preset_name]
            self.gait_state["target"] = preset_config
            self.gait_state["source"] = "preset:{}".format(preset_name)
            
            response = {
                "gaitPreset": {
                    "success": True,
                    "preset": preset_name,
                    "config": preset_config
                }
            }
            websocket.sendMessage(json.dumps(response))
            self.logger.info("Gait: Preset '{}' aplicado = {}".format(preset_name, preset_config))
            return True
            
        except Exception as e:
            self.send_error_response(websocket, "gaitPreset", str(e))
            return False
    
    def get_action_name(self):
        return "gaitPreset"
