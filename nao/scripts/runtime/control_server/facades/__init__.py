# -*- coding: utf-8 -*-
"""
Facades package - NAOqi access facades.

Provides simplified interfaces to NAOqi services.
"""

from __future__ import print_function
import sys
import os

# Agregar directorio actual al path
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from nao_facade import NAOFacade

__all__ = ['NAOFacade']
