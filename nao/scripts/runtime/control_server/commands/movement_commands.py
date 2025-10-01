#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
movement_commands.py - Comandos de movimiento del robot

Implementa comandos para walk, walkTo, turnLeft, turnRight, posture usando Command Pattern.
"""

from __future__ import print_function
import time
import math
import sys
import os

# Importar desde módulo padre
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand

class WalkCommand(BaseCommand):
    """Comando para movimiento reactivo del robot."""
    
    def __init__(self, nao_facade, logger, movement_context=None):
        super(WalkCommand, self).__init__(nao_facade, logger)
        self.movement_context = movement_context
    
    def execute(self, message, websocket):
        """Ejecutar comando de caminar."""
        try:
            # Obtener parámetros
            vx = self.get_param_safe(message, "vx", 0.0, float)
            vy = self.get_param_safe(message, "vy", 0.0, float) 
            wz = self.get_param_safe(message, "wz", 0.0, float)
            
            # Ejecutar movimiento según estrategia actual
            if self.movement_context:
                success = self.movement_context.execute_movement(vx, vy, wz)
                strategy = self.movement_context.get_current_strategy()
            else:
                # Fallback a movimiento directo
                success = self.nao.move_toward(vx, vy, wz)
                strategy = "direct"
            
            if success:
                self.send_success_response(websocket, "walk", {
                    "vx": vx, "vy": vy, "wz": wz,
                    "strategy": strategy
                })
            else:
                self.send_error_response(websocket, "walk", "No se pudo ejecutar movimiento")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "walk", str(e))
            return False
    
    def get_action_name(self):
        return "walk"

class WalkToCommand(BaseCommand):
    """Comando para movimiento a posición específica."""
    
    def execute(self, message, websocket):
        """Ejecutar comando walkTo."""
        try:
            # Validar parámetros requeridos
            is_valid, missing = self.validate_required_params(message, ["x", "y", "theta"])
            if not is_valid:
                self.send_error_response(websocket, "walkTo", 
                                       "Parámetros faltantes: {}".format(missing))
                return False
            
            # Obtener parámetros
            x = self.get_param_safe(message, "x", 0.0, float)
            y = self.get_param_safe(message, "y", 0.0, float)
            theta = self.get_param_safe(message, "theta", 0.0, float)
            
            # TODO: Obtener configuración de gait actual desde context
            config = None  # Se implementará con el sistema de gait
            
            # Ejecutar movimiento
            success = self.nao.move_to(x, y, theta, config)
            
            if success:
                self.send_success_response(websocket, "walkTo", {
                    "x": x, "y": y, "theta": theta
                })
            else:
                self.send_error_response(websocket, "walkTo", "No se pudo ejecutar moveTo")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "walkTo", str(e))
            return False
    
    def get_action_name(self):
        return "walkTo"

class TurnLeftCommand(BaseCommand):
    """Comando para girar a la izquierda."""
    
    def execute(self, message, websocket):
        """Ejecutar comando turnLeft."""
        try:
            # Obtener parámetros
            angular_speed = self.get_param_safe(message, "speed", 0.5, float)
            duration = self.get_param_safe(message, "duration", 0.0, float)
            
            if duration > 0:
                # Giro por tiempo específico
                success = self.nao.move_toward(0.0, 0.0, angular_speed)
                if success:
                    time.sleep(duration)
                    self.nao.stop_move()
                    
                    self.send_success_response(websocket, "turnLeft", {
                        "speed": angular_speed,
                        "duration": duration,
                        "type": "timed"
                    })
                else:
                    self.send_error_response(websocket, "turnLeft", "No se pudo iniciar giro")
            else:
                # Giro continuo
                success = self.nao.move_toward(0.0, 0.0, angular_speed)
                if success:
                    self.send_success_response(websocket, "turnLeft", {
                        "speed": angular_speed,
                        "type": "continuous"
                    })
                else:
                    self.send_error_response(websocket, "turnLeft", "No se pudo iniciar giro continuo")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "turnLeft", str(e))
            return False
    
    def get_action_name(self):
        return "turnLeft"

class TurnRightCommand(BaseCommand):
    """Comando para girar a la derecha."""
    
    def execute(self, message, websocket):
        """Ejecutar comando turnRight."""
        try:
            # Obtener parámetros
            angular_speed = self.get_param_safe(message, "speed", 0.5, float)
            duration = self.get_param_safe(message, "duration", 0.0, float)
            
            # Hacer negativo para girar a la derecha
            angular_speed = -angular_speed
            
            if duration > 0:
                # Giro por tiempo específico
                success = self.nao.move_toward(0.0, 0.0, angular_speed)
                if success:
                    time.sleep(duration)
                    self.nao.stop_move()
                    
                    self.send_success_response(websocket, "turnRight", {
                        "speed": abs(angular_speed),
                        "duration": duration,
                        "type": "timed"
                    })
                else:
                    self.send_error_response(websocket, "turnRight", "No se pudo iniciar giro")
            else:
                # Giro continuo
                success = self.nao.move_toward(0.0, 0.0, angular_speed)
                if success:
                    self.send_success_response(websocket, "turnRight", {
                        "speed": abs(angular_speed),
                        "type": "continuous"
                    })
                else:
                    self.send_error_response(websocket, "turnRight", "No se pudo iniciar giro continuo")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "turnRight", str(e))
            return False
    
    def get_action_name(self):
        return "turnRight"

class PostureCommand(BaseCommand):
    """Comando para cambiar postura del robot."""
    
    def execute(self, message, websocket):
        """Ejecutar comando posture."""
        try:
            # Obtener parámetros
            posture_name = self.get_param_safe(message, "value", "Stand", str)
            speed = self.get_param_safe(message, "speed", 0.7, float)
            
            # Ejecutar cambio de postura
            success = self.nao.go_to_posture(posture_name, speed)
            
            if success:
                self.send_success_response(websocket, "posture", {
                    "posture": posture_name,
                    "speed": speed
                })
            else:
                self.send_error_response(websocket, "posture", 
                                       "No se pudo cambiar a postura: {}".format(posture_name))
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "posture", str(e))
            return False
    
    def get_action_name(self):
        return "posture"