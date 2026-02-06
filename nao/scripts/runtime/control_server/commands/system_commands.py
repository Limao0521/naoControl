#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
system_commands.py - Comandos de sistema del robot

Implementa comandos de sistema como batería, vida autónoma, configuración
usando Command Pattern.
"""

from __future__ import print_function
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand


class BatteryCommand(BaseCommand):
    """Comando para obtener estado de batería."""
    
    def execute(self, message, websocket):
        """Ejecutar comando getBattery."""
        try:
            battery_info = self.nao.get_battery_info()
            
            if battery_info:
                response = {
                    "battery": battery_info.get("level", 0),
                    "low": battery_info.get("low", False),
                    "full": battery_info.get("full", False)
                }
                websocket.sendMessage(json.dumps(response))
                self.logger.info("Battery: {}% low={} full={}".format(
                    response["battery"], response["low"], response["full"]))
                return True
            else:
                # Fallback con valor por defecto
                response = {"battery": 100, "low": False, "full": True}
                websocket.sendMessage(json.dumps(response))
                return True
                
        except Exception as e:
            self.logger.error("Error obteniendo batería: {}".format(e))
            websocket.sendMessage(json.dumps({"battery": 0, "low": True, "full": False}))
            return False
    
    def get_action_name(self):
        return "getBattery"


class AutonomousLifeCommand(BaseCommand):
    """Comando para controlar vida autónoma."""
    
    def execute(self, message, websocket):
        """Ejecutar comando autonomous o getAutonomousLife."""
        try:
            action = message.get("action", "autonomous")
            
            if action == "getAutonomousLife":
                # Obtener estado actual
                is_enabled = self.nao.get_autonomous_life_state()
                websocket.sendMessage(json.dumps({"autonomousLifeEnabled": is_enabled}))
                self.logger.info("AutonomousLife: enabled={}".format(is_enabled))
                return True
            else:
                # Configurar estado
                enable = bool(message.get("enable", False))
                success = self.nao.set_autonomous_life(enable)
                
                if success:
                    self.logger.info("AutonomousLife: set to {}".format(
                        "interactive" if enable else "disabled"))
                    return True
                else:
                    self.logger.error("Error configurando AutonomousLife")
                    return False
                
        except Exception as e:
            self.logger.error("Error en AutonomousLife: {}".format(e))
            if "getAutonomousLife" in str(message.get("action", "")):
                websocket.sendMessage(json.dumps({"autonomousLifeEnabled": False}))
            return False
    
    def get_action_name(self):
        return "autonomous"


class GetConfigCommand(BaseCommand):
    """Comando para obtener configuración actual."""
    
    def __init__(self, nao_facade, logger, gait_state=None, adaptive_state=None):
        """
        Inicializar comando con estado compartido.
        
        Args:
            nao_facade: Facade NAO
            logger: Logger
            gait_state: Referencia al estado de gait
            adaptive_state: Referencia al estado adaptativo
        """
        super(GetConfigCommand, self).__init__(nao_facade, logger)
        self.gait_state = gait_state or {}
        self.adaptive_state = adaptive_state or {"enabled": False, "mode": "auto"}
    
    def execute(self, message, websocket):
        """Ejecutar comando getConfig."""
        try:
            # Obtener configuración actual de gait
            gait_applied = self.gait_state.get("applied", [])
            gait_target = self.gait_state.get("target", [])
            gait = gait_applied if gait_applied else gait_target
            
            response = {
                "gait": gait,
                "adaptive": self.adaptive_state
            }
            
            websocket.sendMessage(json.dumps(response))
            self.logger.info("Config: gait={} adaptive={}".format(gait, self.adaptive_state))
            return True
            
        except Exception as e:
            self.logger.error("Error obteniendo config: {}".format(e))
            websocket.sendMessage(json.dumps({"gait": [], "adaptive": {"enabled": False}}))
            return False
    
    def get_action_name(self):
        return "getConfig"


class GetSystemInfoCommand(BaseCommand):
    """Comando para obtener información del sistema."""
    
    def execute(self, message, websocket):
        """Ejecutar comando getSystemInfo."""
        try:
            system_info = {
                "battery": self.nao.get_battery_info(),
                "autonomousLife": self.nao.get_autonomous_life_state(),
                "fallManager": self.nao.get_fall_manager_state(),
                "robotName": self.nao.get_robot_name(),
                "naoqiVersion": self.nao.get_naoqi_version()
            }
            
            websocket.sendMessage(json.dumps({"systemInfo": system_info}))
            self.logger.info("SystemInfo enviado")
            return True
            
        except Exception as e:
            self.send_error_response(websocket, "getSystemInfo", str(e))
            return False
    
    def get_action_name(self):
        return "getSystemInfo"


class RestartServicesCommand(BaseCommand):
    """Comando para reiniciar servicios del robot."""
    
    def execute(self, message, websocket):
        """Ejecutar comando restartServices."""
        try:
            service = message.get("service", "all")
            
            # Por ahora solo reiniciar estado local
            if service == "motion":
                self.nao.stop_move()
                self.nao.set_stiffnesses("Body", 1.0)
            elif service == "tts":
                pass  # TTS no requiere reinicio
            elif service == "all":
                self.nao.stop_move()
                self.nao.set_stiffnesses("Body", 1.0)
            
            self.send_success_response(websocket, "restartServices", {"service": service})
            return True
            
        except Exception as e:
            self.send_error_response(websocket, "restartServices", str(e))
            return False
    
    def get_action_name(self):
        return "restartServices"
