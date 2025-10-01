#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Control Server Package - Modular NAO Control System

Arquitectura basada en patrones de diseño:
- Command Pattern: Para encapsular acciones WebSocket
- Strategy Pattern: Para diferentes estrategias de movimiento
- Factory Pattern: Para crear comandos
- Facade Pattern: Para simplificar NAOqi
- Observer Pattern: Para eventos y logging
"""

__version__ = "2.0.0"
__author__ = "Luis Ramirez, Andres Azcona"