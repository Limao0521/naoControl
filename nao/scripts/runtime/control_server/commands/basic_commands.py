#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
basic_commands.py - Comandos básicos del robot

Implementa comandos básicos como move, say, language, volume usando Command Pattern.
"""

from __future__ import print_function
import sys
import os

# Importar desde módulo padre
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand

class MoveCommand(BaseCommand):
    """Comando para movimiento directo de articulaciones."""
    
    def execute(self, message, websocket):
        """Ejecutar comando move."""
        try:
            # Validar parámetros requeridos
            is_valid, missing = self.validate_required_params(message, ["joint", "value"])
            if not is_valid:
                self.send_error_response(websocket, "move", 
                                       "Parámetros faltantes: {}".format(missing))
                return False
            
            # Obtener parámetros
            joint = self.get_param_safe(message, "joint", "", str)
            value = self.get_param_safe(message, "value", 0.0, float)
            speed = self.get_param_safe(message, "speed", 0.1, float)
            
            # Ejecutar movimiento de articulación
            success = self.nao.set_angles(joint, value, speed)
            
            if success:
                self.send_success_response(websocket, "move", {
                    "joint": joint,
                    "value": value,
                    "speed": speed
                })
            else:
                self.send_error_response(websocket, "move", 
                                       "No se pudo mover articulación: {}".format(joint))
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "move", str(e))
            return False
    
    def get_action_name(self):
        return "move"

class SayCommand(BaseCommand):
    """Comando para hacer hablar al robot."""
    
    def execute(self, message, websocket):
        """Ejecutar comando say."""
        try:
            # Obtener parámetros
            text = self.get_param_safe(message, "text", "", str)
            
            if not text:
                self.send_error_response(websocket, "say", "Texto vacío")
                return False
            
            # Ejecutar TTS
            success = self.nao.say(text)
            
            if success:
                self.send_success_response(websocket, "say", {
                    "text": text
                })
            else:
                self.send_error_response(websocket, "say", "No se pudo reproducir texto")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "say", str(e))
            return False
    
    def get_action_name(self):
        return "say"

class LanguageCommand(BaseCommand):
    """Comando para cambiar idioma TTS."""
    
    def execute(self, message, websocket):
        """Ejecutar comando language."""
        try:
            # Obtener parámetros
            language = self.get_param_safe(message, "value", "English", str)
            
            # Cambiar idioma
            success = self.nao.set_language(language)
            
            if success:
                self.send_success_response(websocket, "language", {
                    "language": language
                })
            else:
                self.send_error_response(websocket, "language", 
                                       "No se pudo cambiar a idioma: {}".format(language))
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "language", str(e))
            return False
    
    def get_action_name(self):
        return "language"

class VolumeCommand(BaseCommand):
    """Comando para cambiar volumen de audio."""
    
    def execute(self, message, websocket):
        """Ejecutar comando volume."""
        try:
            # Obtener parámetros
            volume = self.get_param_safe(message, "value", 50.0, float)
            
            # Validar rango
            if not (0 <= volume <= 100):
                self.send_error_response(websocket, "volume", 
                                       "Volumen debe estar entre 0 y 100")
                return False
            
            # Cambiar volumen
            success = self.nao.set_volume(volume)
            
            if success:
                self.send_success_response(websocket, "volume", {
                    "volume": volume
                })
            else:
                self.send_error_response(websocket, "volume", "No se pudo cambiar volumen")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "volume", str(e))
            return False
    
    def get_action_name(self):
        return "volume"