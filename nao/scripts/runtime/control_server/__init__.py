#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Control Server Package - Modular NAO Control Backend

Este paquete contiene TODO el backend del robot NAO:
- Servidor WebSocket para control remoto
- Sistema de logging centralizado
- Streaming de video
- Data logger para ML
- Comandos modulares por categoría

Arquitectura basada en patrones de diseño:
- Command Pattern: Para encapsular acciones WebSocket
- Strategy Pattern: Para diferentes estrategias de movimiento
- Factory Pattern: Para crear comandos
- Facade Pattern: Para simplificar NAOqi
- Observer Pattern: Para eventos y logging

Estructura:
    control_server/
    ├── server.py           # Servidor WebSocket principal
    ├── logger.py           # Sistema de logging (puerto 6672)
    ├── video_stream.py     # Streaming de video (puerto 8080)
    ├── data_logger.py      # Data logger CSV para ML
    ├── base_command.py     # Clase base Command Pattern
    ├── command_factory.py  # Factory de comandos
    ├── commands/           # Comandos por categoría
    ├── facades/            # Facades para NAOqi
    ├── strategies/         # Estrategias de movimiento
    └── libs/               # Librerías utilitarias
"""

__version__ = "2.0.0"
__author__ = "Luis Ramirez, Andres Azcona"

# Componentes principales del backend
COMPONENTS = {
    'server': 'server.py',
    'logger': 'logger.py',
    'video': 'video_stream.py',
    'data_logger': 'data_logger.py'
}

# Puertos del sistema
PORTS = {
    'websocket': 6671,      # Control WebSocket
    'logger_ws': 6672,      # Logger WebSocket
    'video_http': 8080,     # Video MJPEG
    'video_udp': 6666,      # Video UDP
    'naoqi': 9559           # NAOqi (interno)
}