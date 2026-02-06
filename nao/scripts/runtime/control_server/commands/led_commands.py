#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
led_commands.py - Comandos de control de LEDs

Implementa comandos para control de LEDs usando Command Pattern.
"""

from __future__ import print_function
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand


class LedCommand(BaseCommand):
    """Comando para control de LEDs RGB del robot."""
    
    def execute(self, message, websocket):
        """Ejecutar comando LED."""
        try:
            # Obtener grupo de LEDs
            group = message.get("group", "ChestLeds")
            
            # Python 2/3 compatibility para unicode
            try:
                unicode_type = unicode
            except NameError:
                unicode_type = str
            
            if isinstance(group, unicode_type):
                try:
                    group = group.encode('utf-8')
                except Exception:
                    pass
            
            # Obtener valores RGB (0.0 a 1.0)
            r = self.get_param_safe(message, "r", 0.0, float)
            g = self.get_param_safe(message, "g", 0.0, float)
            b = self.get_param_safe(message, "b", 0.0, float)
            duration = self.get_param_safe(message, "duration", 0.3, float)
            
            # Ejecutar cambio de LED
            success = self.nao.set_led_rgb(group, r, g, b, duration)
            
            if success:
                self.send_success_response(websocket, "led", {
                    "group": group,
                    "r": r,
                    "g": g,
                    "b": b,
                    "duration": duration
                })
            else:
                self.send_error_response(websocket, "led", 
                                       "No se pudo configurar LED: {}".format(group))
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "led", str(e))
            return False
    
    def get_action_name(self):
        return "led"


class LedOffCommand(BaseCommand):
    """Comando para apagar todos los LEDs."""
    
    def execute(self, message, websocket):
        """Ejecutar comando para apagar LEDs."""
        try:
            group = message.get("group", "AllLeds")
            
            success = self.nao.set_led_rgb(group, 0.0, 0.0, 0.0, 0.0)
            
            if success:
                self.send_success_response(websocket, "ledOff", {"group": group})
            else:
                self.send_error_response(websocket, "ledOff", "No se pudo apagar LEDs")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "ledOff", str(e))
            return False
    
    def get_action_name(self):
        return "ledOff"


class LedBlinkCommand(BaseCommand):
    """Comando para hacer parpadear LEDs."""
    
    def execute(self, message, websocket):
        """Ejecutar comando de parpadeo de LEDs."""
        try:
            group = message.get("group", "FaceLeds")
            r = self.get_param_safe(message, "r", 1.0, float)
            g = self.get_param_safe(message, "g", 1.0, float)
            b = self.get_param_safe(message, "b", 1.0, float)
            duration = self.get_param_safe(message, "duration", 0.5, float)
            times = self.get_param_safe(message, "times", 3, int)
            
            success = self.nao.blink_leds(group, r, g, b, duration, times)
            
            if success:
                self.send_success_response(websocket, "ledBlink", {
                    "group": group,
                    "times": times
                })
            else:
                self.send_error_response(websocket, "ledBlink", "No se pudo hacer parpadear LEDs")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "ledBlink", str(e))
            return False
    
    def get_action_name(self):
        return "ledBlink"
