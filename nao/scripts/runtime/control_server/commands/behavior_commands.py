#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
behavior_commands.py - Comandos de behaviors del robot

Implementa comandos para ejecutar behaviors (kick, siu, etc.) usando Command Pattern.
"""

from __future__ import print_function
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_command import BaseCommand


class GenericBehaviorCommand(BaseCommand):
    """Comando base para ejecutar behaviors genéricos."""
    
    def __init__(self, nao_facade, logger, behavior_name=None, search_term=None):
        """
        Inicializar comando de behavior.
        
        Args:
            nao_facade: Facade NAO
            logger: Logger
            behavior_name: Nombre exacto del behavior
            search_term: Término de búsqueda para behavior alternativo
        """
        super(GenericBehaviorCommand, self).__init__(nao_facade, logger)
        self.behavior_name = behavior_name
        self.search_term = search_term or (behavior_name.split("-")[0] if behavior_name else "")
    
    def execute(self, message, websocket):
        """Ejecutar behavior."""
        try:
            action = message.get("action", self.get_action_name())
            
            # Verificar si behavior está instalado
            if self.nao.is_behavior_installed(self.behavior_name):
                # Detener behaviors en ejecución
                self.nao.stop_all_behaviors()
                
                # Ejecutar behavior
                success = self.nao.run_behavior(self.behavior_name)
                
                if success:
                    response = {action: {"success": True, "behavior": self.behavior_name}}
                    websocket.sendMessage(json.dumps(response))
                    self.logger.info("{}: Ejecutando behavior '{}'".format(action, self.behavior_name))
                    return True
                else:
                    response = {action: {"success": False, "error": "Error ejecutando behavior"}}
                    websocket.sendMessage(json.dumps(response))
                    return False
            else:
                # Buscar behavior alternativo
                alternative = self.nao.find_behavior(self.search_term)
                
                if alternative:
                    self.nao.stop_all_behaviors()
                    success = self.nao.run_behavior(alternative)
                    
                    response = {action: {"success": success, "behavior": alternative}}
                    websocket.sendMessage(json.dumps(response))
                    self.logger.info("{}: Ejecutando behavior alternativo '{}'".format(action, alternative))
                    return success
                else:
                    installed = self.nao.get_installed_behaviors()[:10]
                    error_msg = "Behavior '{}' no instalado. Disponibles: {}".format(
                        self.behavior_name, installed)
                    response = {action: {"success": False, "error": error_msg}}
                    websocket.sendMessage(json.dumps(response))
                    self.logger.warning("{}: {}".format(action, error_msg))
                    return False
                    
        except Exception as e:
            action = message.get("action", self.get_action_name())
            response = {action: {"success": False, "error": str(e)}}
            websocket.sendMessage(json.dumps(response))
            self.logger.error("{}: Error - {}".format(action, e))
            return False
    
    def get_action_name(self):
        return "behavior"


class KickCommand(GenericBehaviorCommand):
    """Comando para ejecutar behavior de kick."""
    
    def __init__(self, nao_facade, logger):
        super(KickCommand, self).__init__(
            nao_facade, logger,
            behavior_name="kicknao-f6eb94/behavior_1",
            search_term="kick"
        )
    
    def get_action_name(self):
        return "kick"


class SiuCommand(GenericBehaviorCommand):
    """Comando para ejecutar behavior siu (celebración)."""
    
    def __init__(self, nao_facade, logger):
        super(SiuCommand, self).__init__(
            nao_facade, logger,
            behavior_name="siu-17777b/behavior_1",
            search_term="siu"
        )
    
    def get_action_name(self):
        return "siu"


class SaxophoneCommand(GenericBehaviorCommand):
    """Comando para ejecutar behavior saxophone."""
    
    def __init__(self, nao_facade, logger):
        super(SaxophoneCommand, self).__init__(
            nao_facade, logger,
            behavior_name="saxophone-f56d02/behavior_1",
            search_term="saxophone"
        )
    
    def get_action_name(self):
        return "saxophone"


class TaichichuaCommand(GenericBehaviorCommand):
    """Comando para ejecutar behavior taichichua."""
    
    def __init__(self, nao_facade, logger):
        super(TaichichuaCommand, self).__init__(
            nao_facade, logger,
            behavior_name="taichichua-a22a25/behavior_1",
            search_term="taichi"
        )
    
    def get_action_name(self):
        return "taichichua"


class KissCommand(GenericBehaviorCommand):
    """Comando para ejecutar behavior kiss."""
    
    def __init__(self, nao_facade, logger):
        super(KissCommand, self).__init__(
            nao_facade, logger,
            behavior_name="kiss-45d3e2",
            search_term="kiss"
        )
    
    def get_action_name(self):
        return "kiss"


class GangnamstyleCommand(GenericBehaviorCommand):
    """Comando para ejecutar behavior gangnam style."""
    
    def __init__(self, nao_facade, logger):
        super(GangnamstyleCommand, self).__init__(
            nao_facade, logger,
            behavior_name="gangnamstyle-0ff3ac/behavior_1",
            search_term="gangnam"
        )
    
    def get_action_name(self):
        return "gangnamstyle"


class ElephantCommand(GenericBehaviorCommand):
    """Comando para ejecutar behavior elephant."""
    
    def __init__(self, nao_facade, logger):
        super(ElephantCommand, self).__init__(
            nao_facade, logger,
            behavior_name="elephant-692231/behavior_1",
            search_term="elephant"
        )
    
    def get_action_name(self):
        return "elephant"


class MacarenaCommand(GenericBehaviorCommand):
    """Comando para ejecutar behavior macarena."""
    
    def __init__(self, nao_facade, logger):
        super(MacarenaCommand, self).__init__(
            nao_facade, logger,
            behavior_name="macarena-original-055bea/behavior_1",
            search_term="macarena"
        )
    
    def get_action_name(self):
        return "macarena"


class DiscoCommand(GenericBehaviorCommand):
    """Comando para ejecutar behavior disco."""
    
    def __init__(self, nao_facade, logger):
        super(DiscoCommand, self).__init__(
            nao_facade, logger,
            behavior_name="disco-8c59b8/behavior_1",
            search_term="disco"
        )
    
    def get_action_name(self):
        return "disco"


class StopBehaviorCommand(BaseCommand):
    """Comando para detener behavior en ejecución."""
    
    def execute(self, message, websocket):
        """Detener behaviors."""
        try:
            behavior_name = message.get("behavior", None)
            
            if behavior_name:
                success = self.nao.stop_behavior(behavior_name)
            else:
                success = self.nao.stop_all_behaviors()
            
            if success:
                self.send_success_response(websocket, "stopBehavior", {
                    "stopped": behavior_name or "all"
                })
            else:
                self.send_error_response(websocket, "stopBehavior", "No se pudo detener behavior")
            
            return success
            
        except Exception as e:
            self.send_error_response(websocket, "stopBehavior", str(e))
            return False
    
    def get_action_name(self):
        return "stopBehavior"


class ListBehaviorsCommand(BaseCommand):
    """Comando para listar behaviors disponibles."""
    
    def execute(self, message, websocket):
        """Listar behaviors instalados."""
        try:
            installed = self.nao.get_installed_behaviors()
            running = self.nao.get_running_behaviors()
            
            response = {
                "listBehaviors": {
                    "installed": installed,
                    "running": running,
                    "count": len(installed)
                }
            }
            websocket.sendMessage(json.dumps(response))
            self.logger.info("Behaviors listados: {} instalados, {} en ejecución".format(
                len(installed), len(running)))
            return True
            
        except Exception as e:
            self.send_error_response(websocket, "listBehaviors", str(e))
            return False
    
    def get_action_name(self):
        return "listBehaviors"
