#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
safety_commands.py - Comandos de seguridad del robot

Implementa comandos de seguridad como fall manager, protección de pies
usando Command Pattern.
"""

from __future__ import print_function
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand


class FootProtectionCommand(BaseCommand):
    """Comando para controlar protección de contacto de pie."""
    
    def execute(self, message, websocket):
        """Ejecutar comando footProtection."""
        try:
            enable = bool(message.get("enable", True))
            
            success = self.nao.set_foot_contact_protection(enable)
            
            if success:
                response = {"footProtection": enable}
                websocket.sendMessage(json.dumps(response))
                self.logger.info("FootProtection: set to {}".format(enable))
                return True
            else:
                self.send_error_response(websocket, "footProtection", 
                    "No se pudo configurar protección de pie")
                return False
                
        except Exception as e:
            self.send_error_response(websocket, "footProtection", str(e))
            return False
    
    def get_action_name(self):
        return "footProtection"


class FallManagerCommand(BaseCommand):
    """Comando para controlar Fall Manager."""
    
    def execute(self, message, websocket):
        """Ejecutar comando fallManager."""
        try:
            enable = bool(message.get("enable", True))
            
            if enable:
                # Activar Fall Manager (simple)
                success = self.nao.set_fall_manager(True)
                status = "ENABLED" if success else "FAILED"
                self.logger.info("Fall Manager ENABLED: auto-recovery ON")
            else:
                # Desactivar Fall Manager (requiere pasos especiales)
                success = self.nao.set_fall_manager(False)
                status = "DISABLED" if success else "FAILED"
                
                if not success:
                    # Intentar método alternativo
                    success = self.nao.force_disable_fall_manager()
                    status = "FORCE_DISABLED" if success else "FAILED"
                    if success:
                        self.logger.warning("Fall Manager DISABLED via fallback method")
            
            response = {
                "fallManager": {
                    "success": success,
                    "enabled": enable if success else not enable,
                    "status": status
                }
            }
            websocket.sendMessage(json.dumps(response))
            return success
            
        except Exception as e:
            self.logger.error("Error configurando Fall Manager: {}".format(e))
            websocket.sendMessage(json.dumps({
                "fallManager": {
                    "success": False,
                    "error": str(e),
                    "help": "Try: motion.setFallManagerEnabled(False, True) or restart NAOqi"
                }
            }))
            return False
    
    def get_action_name(self):
        return "fallManager"


class GetFallManagerCommand(BaseCommand):
    """Comando para obtener estado del Fall Manager."""
    
    def execute(self, message, websocket):
        """Ejecutar comando getFallManager."""
        try:
            enabled = self.nao.get_fall_manager_state()
            
            response = {
                "getFallManager": {
                    "success": True,
                    "enabled": enabled,
                    "status": "ENABLED" if enabled else "DISABLED"
                }
            }
            websocket.sendMessage(json.dumps(response))
            return True
            
        except Exception as e:
            self.logger.error("Error obteniendo estado Fall Manager: {}".format(e))
            websocket.sendMessage(json.dumps({
                "getFallManager": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "getFallManager"


class ForceDisableFallManagerCommand(BaseCommand):
    """Comando para forzar desactivación del Fall Manager."""
    
    def execute(self, message, websocket):
        """Ejecutar comando forceDisableFallManager."""
        try:
            self.logger.warning("Intentando forzar desactivación del Fall Manager...")
            
            methods_tried = []
            success = False
            
            # Método 1: setFallManagerEnabled con allowDisable
            try:
                self.nao.motion.setFallManagerEnabled(False, True)
                methods_tried.append("setFallManagerEnabled(False, True) - SUCCESS")
                success = True
            except Exception as e1:
                methods_tried.append("setFallManagerEnabled(False, True) - FAILED: {}".format(str(e1)))
            
            # Método 2: ALMemory directo
            if not success:
                try:
                    self.nao.memory.insertData("FallManagerEnabled", False)
                    methods_tried.append("ALMemory insertData - SUCCESS")
                    success = True
                except Exception as e2:
                    methods_tried.append("ALMemory insertData - FAILED: {}".format(str(e2)))
            
            # Método 3: Configuración de movimiento
            if not success:
                try:
                    self.nao.motion.setMotionConfig([["ENABLE_FALL_MANAGER", False]])
                    methods_tried.append("setMotionConfig ENABLE_FALL_MANAGER - SUCCESS")
                    success = True
                except Exception as e3:
                    methods_tried.append("setMotionConfig - FAILED: {}".format(str(e3)))
            
            if success:
                self.logger.info("Fall Manager forzado a DISABLED")
                response = {
                    "forceDisableFallManager": {
                        "success": True,
                        "enabled": False,
                        "status": "FORCE_DISABLED",
                        "methods_tried": methods_tried
                    }
                }
            else:
                self.logger.error("No se pudo forzar desactivación del Fall Manager")
                response = {
                    "forceDisableFallManager": {
                        "success": False,
                        "error": "All methods failed",
                        "methods_tried": methods_tried,
                        "help": "Fall Manager protection is active. Consider restarting NAOqi or using Choregraphe."
                    }
                }
            
            websocket.sendMessage(json.dumps(response))
            return success
            
        except Exception as e:
            self.logger.error("Error forzando desactivación Fall Manager: {}".format(e))
            websocket.sendMessage(json.dumps({
                "forceDisableFallManager": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "forceDisableFallManager"


class SetStiffnessCommand(BaseCommand):
    """Comando para controlar rigidez de articulaciones."""
    
    def execute(self, message, websocket):
        """Ejecutar comando setStiffness."""
        try:
            names = message.get("names", "Body")
            stiffness = float(message.get("stiffness", 1.0))
            
            # Validar rango
            if not (0.0 <= stiffness <= 1.0):
                self.send_error_response(websocket, "setStiffness",
                    "Stiffness debe estar entre 0.0 y 1.0")
                return False
            
            success = self.nao.set_stiffnesses(names, stiffness)
            
            if success:
                self.send_success_response(websocket, "setStiffness", {
                    "names": names,
                    "stiffness": stiffness
                })
            else:
                self.send_error_response(websocket, "setStiffness",
                    "No se pudo configurar rigidez")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "setStiffness", str(e))
            return False
    
    def get_action_name(self):
        return "setStiffness"


class EmergencyStopCommand(BaseCommand):
    """Comando de parada de emergencia."""
    
    def execute(self, message, websocket):
        """Ejecutar comando emergencyStop."""
        try:
            self.logger.warning("EMERGENCY STOP ejecutado!")
            
            # Detener todo movimiento
            self.nao.stop_move()
            
            # Detener behaviors
            self.nao.stop_all_behaviors()
            
            # Opcional: quitar rigidez (configurable)
            release_stiffness = message.get("release", False)
            if release_stiffness:
                self.nao.set_stiffnesses("Body", 0.0)
                self.logger.warning("Rigidez liberada - robot puede caer!")
            
            response = {
                "emergencyStop": {
                    "success": True,
                    "released": release_stiffness,
                    "message": "Robot detenido"
                }
            }
            websocket.sendMessage(json.dumps(response))
            return True
            
        except Exception as e:
            self.logger.error("Error en emergency stop: {}".format(e))
            websocket.sendMessage(json.dumps({
                "emergencyStop": {"success": False, "error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "emergencyStop"


class GetSafetyStatusCommand(BaseCommand):
    """Comando para obtener estado completo de seguridad."""
    
    def execute(self, message, websocket):
        """Ejecutar comando getSafetyStatus."""
        try:
            fall_manager = self.nao.get_fall_manager_state()
            # Foot protection no tiene getter directo, asumimos True por defecto
            
            response = {
                "safetyStatus": {
                    "fallManager": fall_manager,
                    "footProtection": True,  # Asumido
                    "stiffness": self.nao.get_stiffnesses("Body") if hasattr(self.nao, 'get_stiffnesses') else 1.0
                }
            }
            websocket.sendMessage(json.dumps(response))
            return True
            
        except Exception as e:
            self.logger.error("Error obteniendo estado de seguridad: {}".format(e))
            websocket.sendMessage(json.dumps({
                "safetyStatus": {"error": str(e)}
            }))
            return False
    
    def get_action_name(self):
        return "getSafetyStatus"
