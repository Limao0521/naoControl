#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
command_factory.py - Factory Pattern para crear comandos

Centraliza la creación de comandos WebSocket basado en el action recibido.
Permite fácil extensión y mantenimiento de nuevos comandos.
"""

from __future__ import print_function
import sys
import os

# Agregar path del directorio actual y subdirectorios para imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_commands_dir = os.path.join(_current_dir, "commands")
for _path in [_current_dir, _commands_dir]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Imports de comandos (directamente por nombre de archivo)
from movement_commands import WalkCommand, WalkToCommand, TurnLeftCommand, TurnRightCommand, PostureCommand
from basic_commands import MoveCommand, SayCommand, LanguageCommand, VolumeCommand
from led_commands import LedCommand
from system_commands import BatteryCommand, AutonomousLifeCommand, GetConfigCommand
from behavior_commands import (
    KickCommand, SiuCommand, SaxophoneCommand, TaichichuaCommand,
    KissCommand, GangnamstyleCommand, ElephantCommand, MacarenaCommand,
    DiscoCommand, StopBehaviorCommand, ListBehaviorsCommand
)
from gait_commands import GaitCommand, GetGaitCommand, ResetGaitCommand, GaitPresetsCommand
from adaptive_commands import (
    AdaptiveLightGBMCommand, GetLightGBMStatsCommand,
    SetAdaptiveModeCommand, GetAdaptiveModeCommand, PredictGaitCommand
)
from logging_commands import StartLoggingCommand, StopLoggingCommand, GetLoggingStatusCommand, LogSampleCommand
from record_commands import RecordModeCommand, GetRecordStatusCommand
from safety_commands import (
    FootProtectionCommand, FallManagerCommand, GetFallManagerCommand,
    ForceDisableFallManagerCommand, SetStiffnessCommand, EmergencyStopCommand
)
from conversation_commands import (
    StartConversationCommand, StopConversationCommand, GetConversationStatusCommand
)

class CommandFactory(object):
    """
    Factory para crear comandos WebSocket basados en el action recibido.
    Implementa el Factory Pattern para centralizar la creación de comandos.
    """
    
    def __init__(self, nao_facade, logger, movement_context=None):
        """
        Inicializar factory con dependencias.
        
        Args:
            nao_facade: Instancia del facade NAO
            logger: Logger para registro de eventos
            movement_context: Contexto de movimiento para comandos de walk
        """
        self.nao_facade = nao_facade
        self.logger = logger
        self.movement_context = movement_context
        
        # Mapeo de actions a clases de comando
        self.command_classes = {
            # Movimiento
            'walk': WalkCommand,
            'walkTo': WalkToCommand,
            'turnLeft': TurnLeftCommand,
            'turnRight': TurnRightCommand,
            'posture': PostureCommand,
            
            # Básicos
            'move': MoveCommand,
            'say': SayCommand,
            'language': LanguageCommand,
            'volume': VolumeCommand,
            
            # LEDs
            'led': LedCommand,
            
            # Sistema
            'getBattery': BatteryCommand,
            'autonomous': AutonomousLifeCommand,
            'getAutonomousLife': AutonomousLifeCommand,
            'getConfig': GetConfigCommand,
            
            # Behaviors
            'kick': KickCommand,
            'siu': SiuCommand,
            'saxophone': SaxophoneCommand,
            'taichichua': TaichichuaCommand,
            'kiss': KissCommand,
            'gangnamstyle': GangnamstyleCommand,
            'elephant': ElephantCommand,
            'macarena': MacarenaCommand,
            'disco': DiscoCommand,
            'stopBehavior': StopBehaviorCommand,
            'listBehaviors': ListBehaviorsCommand,
            
            # Gait
            'gait': GaitCommand,
            'getGait': GetGaitCommand,
            'resetGait': ResetGaitCommand,
            'gaitPreset': GaitPresetsCommand,
            
            # Adaptativo
            'adaptiveLightGBM': AdaptiveLightGBMCommand,
            'getLightGBMStats': GetLightGBMStatsCommand,
            'setAdaptiveMode': SetAdaptiveModeCommand,
            'getAdaptiveMode': GetAdaptiveModeCommand,
            'predictGait': PredictGaitCommand,
            
            # Logging
            'startLogging': StartLoggingCommand,
            'stopLogging': StopLoggingCommand,
            'getLoggingStatus': GetLoggingStatusCommand,
            'logSample': LogSampleCommand,
            
            # Grabación
            'recordMode': RecordModeCommand,
            'getRecordStatus': GetRecordStatusCommand,
            
            # Seguridad
            'footProtection': FootProtectionCommand,
            'fallManager': FallManagerCommand,
            'getFallManager': GetFallManagerCommand,
            'forceDisableFallManager': ForceDisableFallManagerCommand,
            'setStiffness': SetStiffnessCommand,
            'emergencyStop': EmergencyStopCommand,
            
            # Conversation
            'startConversation': StartConversationCommand,
            'stopConversation': StopConversationCommand,
            'getConversationStatus': GetConversationStatusCommand,
        }
    
    def create_command(self, action):
        """
        Crear comando basado en el action recibido.
        
        Args:
            action (str): Nombre de la acción WebSocket
            
        Returns:
            BaseCommand: Instancia del comando o None si no existe
        """
        command_class = self.command_classes.get(action)
        
        if command_class:
            try:
                # Comandos de movimiento necesitan el movement_context
                if action in ('walk', 'walkTo', 'turnLeft', 'turnRight'):
                    command = command_class(self.nao_facade, self.logger, self.movement_context)
                else:
                    command = command_class(self.nao_facade, self.logger)
                self.logger.debug("Comando creado para action: {}".format(action))
                return command
            except Exception as e:
                self.logger.error("Error creando comando para {}: {}".format(action, e))
                return None
        else:
            self.logger.warning("Action desconocido: {}".format(action))
            return None
    
    def get_supported_actions(self):
        """
        Obtener lista de actions soportados.
        
        Returns:
            list: Lista de strings con actions soportados
        """
        return sorted(self.command_classes.keys())
    
    def register_command(self, action, command_class):
        """
        Registrar un nuevo comando dinámicamente.
        
        Args:
            action (str): Nombre del action
            command_class: Clase del comando que extiende BaseCommand
        """
        self.command_classes[action] = command_class
        self.logger.info("Comando registrado para action: {}".format(action))
    
    def unregister_command(self, action):
        """
        Desregistrar un comando.
        
        Args:
            action (str): Nombre del action a desregistrar
            
        Returns:
            bool: True si se desregistró, False si no existía
        """
        if action in self.command_classes:
            del self.command_classes[action]
            self.logger.info("Comando desregistrado para action: {}".format(action))
            return True
        return False
    
    def get_command_info(self):
        """
        Obtener información detallada de todos los comandos.
        
        Returns:
            dict: Información de comandos organizados por categoría
        """
        categories = {
            'movement': ['walk', 'walkTo', 'turnLeft', 'turnRight', 'posture'],
            'basic': ['move', 'say', 'language', 'volume'],
            'visual': ['led'],
            'system': ['getBattery', 'autonomous', 'getAutonomousLife', 'getConfig'],
            'behaviors': ['kick', 'siu'],
            'gait': ['gait', 'getGait'],
            'adaptive': ['adaptiveLightGBM', 'getLightGBMStats'],
            'logging': ['startLogging', 'stopLogging', 'getLoggingStatus', 'logSample'],
            'recording': ['recordMode', 'getRecordStatus'],
            'safety': ['footProtection', 'fallManager', 'getFallManager', 'forceDisableFallManager']
        }
        
        result = {}
        for category, actions in categories.items():
            result[category] = []
            for action in actions:
                if action in self.command_classes:
                    result[category].append({
                        'action': action,
                        'class': self.command_classes[action].__name__,
                        'available': True
                    })
                else:
                    result[category].append({
                        'action': action,
                        'class': 'Unknown',
                        'available': False
                    })
        
        return result