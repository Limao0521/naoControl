#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
commands package - Comandos modulares para el control server

Este paquete contiene todos los comandos organizados por funcionalidad:
- movement_commands: Caminar, girar, posturas
- basic_commands: Articulaciones, TTS, volumen
- led_commands: Control de LEDs
- system_commands: Batería, vida autónoma, configuración
- behavior_commands: Behaviors del robot
- gait_commands: Parámetros de marcha
- adaptive_commands: IA adaptativa LightGBM
- logging_commands: Data logging CSV
- record_commands: Sistema de grabación
- safety_commands: Fall manager, protección de pies
"""

from __future__ import print_function
import sys
import os

# Agregar directorio padre al path para que los comandos encuentren base_command
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Movement commands
from movement_commands import (
    WalkCommand,
    WalkToCommand,
    TurnLeftCommand,
    TurnRightCommand,
    PostureCommand
)

# Basic commands
from basic_commands import (
    MoveCommand,
    SayCommand,
    LanguageCommand,
    VolumeCommand
)

# LED commands
from led_commands import LedCommand

# System commands
from system_commands import (
    BatteryCommand,
    AutonomousLifeCommand,
    GetConfigCommand
)

# Behavior commands
from behavior_commands import (
    KickCommand,
    SiuCommand,
    SaxophoneCommand,
    TaichichuaCommand,
    KissCommand,
    GangnamstyleCommand,
    ElephantCommand,
    MacarenaCommand,
    DiscoCommand,
    GenericBehaviorCommand,
    StopBehaviorCommand,
    ListBehaviorsCommand
)

# Gait commands
from gait_commands import (
    GaitCommand,
    GetGaitCommand,
    ResetGaitCommand,
    GaitPresetsCommand
)

# Adaptive commands
from adaptive_commands import (
    AdaptiveLightGBMCommand,
    GetLightGBMStatsCommand,
    SetAdaptiveModeCommand,
    GetAdaptiveModeCommand,
    PredictGaitCommand
)

# Logging commands
from logging_commands import (
    StartLoggingCommand,
    StopLoggingCommand,
    GetLoggingStatusCommand,
    LogSampleCommand
)

# Record commands
from record_commands import (
    RecordModeCommand,
    GetRecordStatusCommand
)

# Safety commands
from safety_commands import (
    FootProtectionCommand,
    FallManagerCommand,
    GetFallManagerCommand,
    ForceDisableFallManagerCommand,
    SetStiffnessCommand,
    EmergencyStopCommand
)

__all__ = [
    # Movement
    'WalkCommand', 'WalkToCommand', 'TurnLeftCommand', 'TurnRightCommand', 'PostureCommand',
    # Basic
    'MoveCommand', 'SayCommand', 'LanguageCommand', 'VolumeCommand',
    # LED
    'LedCommand',
    # System
    'BatteryCommand', 'AutonomousLifeCommand', 'GetConfigCommand',
    # Behavior
    'KickCommand', 'SiuCommand', 'SaxophoneCommand', 'TaichichuaCommand',
    'KissCommand', 'GangnamstyleCommand', 'ElephantCommand', 'MacarenaCommand',
    'DiscoCommand', 'GenericBehaviorCommand',
    # Gait
    'GaitCommand', 'GetGaitCommand',
    # Adaptive
    'AdaptiveLightGBMCommand', 'GetLightGBMStatsCommand',
    'SetAdaptiveModeCommand', 'GetAdaptiveModeCommand',
    # Logging
    'StartLoggingCommand', 'StopLoggingCommand', 'GetLoggingStatusCommand', 'LogSampleCommand',
    # Record
    'RecordModeCommand', 'GetRecordStatusCommand',
    # Safety
    'FootProtectionCommand', 'FallManagerCommand', 'GetFallManagerCommand',
    'ForceDisableFallManagerCommand'
]
