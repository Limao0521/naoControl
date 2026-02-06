# -*- coding: utf-8 -*-
"""
Strategies package - Movement strategies.

Provides different movement implementations using Strategy Pattern.
"""

from __future__ import print_function
import sys
import os

# Agregar directorio actual al path
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from movement_strategies import (
    MovementStrategy,
    ManualMovementStrategy,
    AdaptiveMovementStrategy,
    CautiousMovementStrategy,
    MovementContext
)

__all__ = [
    'MovementStrategy',
    'ManualMovementStrategy',
    'AdaptiveMovementStrategy',
    'CautiousMovementStrategy',
    'MovementContext'
]

__all__ = [
    'MovementStrategy',
    'DirectWalkStrategy',
    'SmartWalkStrategy',
    'AdaptiveWalkStrategy',
    'MovementContext'
]
