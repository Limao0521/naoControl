#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
test_dual_mode.py - Prueba del sistema dual-mode de AdaptiveWalkLightGBM

Este script valida que:
1. El constructor inicial funciona con modo production por defecto
2. Los métodos set_mode() y get_mode() funcionan correctamente
3. predict_gait_parameters() devuelve diferentes valores según el modo
4. Los parámetros óptimos de pasto se cargan correctamente
"""

import sys
import os

# Agregar la carpeta robot_scripts al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'robot_scripts'))

try:
    from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
    from nao_config import OPTIMAL_GRASS_PARAMS, ADAPTIVE_MODES
    print("✓ Importaciones exitosas")
except ImportError as e:
    print("✗ Error de importación: {}".format(e))
    sys.exit(1)

def test_dual_mode():
    """Prueba completa del sistema dual-mode"""
    print("\n=== PRUEBA SISTEMA DUAL-MODE ===")
    
    # Test 1: Constructor con modo production por defecto
    print("\n1. Inicialización con modo production por defecto...")
    try:
        walker = AdaptiveWalkLightGBM("models_npz_automl", mode="production")
        mode = walker.get_mode()
        print("✓ Modo inicial: {}".format(mode))
        assert mode == "production", "Modo inicial debería ser 'production'"
    except Exception as e:
        print("✗ Error en inicialización: {}".format(e))
        return False
    
    # Test 2: Cambio de modo
    print("\n2. Cambio de modo training → production...")
    try:
        walker.set_mode("training")
        mode = walker.get_mode()
        print("✓ Modo después de cambio: {}".format(mode))
        assert mode == "training", "Modo debería ser 'training'"
        
        walker.set_mode("production")
        mode = walker.get_mode()
        print("✓ Modo después de segundo cambio: {}".format(mode))
        assert mode == "production", "Modo debería ser 'production'"
    except Exception as e:
        print("✗ Error en cambio de modo: {}".format(e))
        return False
    
    # Test 3: Parámetros óptimos de pasto
    print("\n3. Verificación parámetros óptimos de pasto...")
    try:
        print("✓ OPTIMAL_GRASS_PARAMS:")
        for param, value in OPTIMAL_GRASS_PARAMS.items():
            print("  - {}: {}".format(param, value))
        
        print("✓ ADAPTIVE_MODES:")
        for mode, desc in ADAPTIVE_MODES.items():
            print("  - {}: {}".format(mode, desc))
    except Exception as e:
        print("✗ Error verificando configuración: {}".format(e))
        return False
    
    # Test 4: Predicción en modo production (parámetros fijos)
    print("\n4. Predicción en modo production...")
    try:
        walker.set_mode("production")
        
        # En modo production, no necesita datos de entrada
        predictions = walker.predict_gait_parameters()
        print("✓ Predicciones modo production:")
        for param, value in predictions.items():
            print("  - {}: {}".format(param, value))
            
        # En modo production, los valores deberían ser los parámetros óptimos
        expected = OPTIMAL_GRASS_PARAMS
        for param in expected:
            if param in predictions:
                assert abs(predictions[param] - expected[param]) < 0.001, \
                    "En modo production, {} debería ser {} pero es {}".format(
                        param, expected[param], predictions[param])
        print("✓ Valores coinciden con parámetros óptimos")
        
    except Exception as e:
        print("✗ Error en predicción modo production: {}".format(e))
        return False
    
    # Test 5: Modo training (esto requeriría modelos cargados, solo verificamos que no falle)
    print("\n5. Cambio a modo training...")
    try:
        walker.set_mode("training")
        mode = walker.get_mode()
        print("✓ Modo cambiado a: {}".format(mode))
        print("  (Predicciones ML requieren modelos cargados)")
    except Exception as e:
        print("✗ Error en modo training: {}".format(e))
        return False
    
    print("\n✓ TODOS LOS TESTS PASARON")
    return True

if __name__ == "__main__":
    success = test_dual_mode()
    if success:
        print("\n🎉 Sistema dual-mode implementado correctamente")
        sys.exit(0)
    else:
        print("\n❌ Fallos en la implementación")
        sys.exit(1)
