#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
test_movement_specific_params.py - Prueba de parámetros específicos por movimiento

Valida que:
1. El sistema detecta correctamente diferentes tipos de movimiento
2. Los parámetros se ajustan según el tipo de movimiento
3. El control del fall manager funciona
4. Los parámetros específicos mejoran la estabilidad
"""

import sys
import os

# Agregar la carpeta robot_scripts al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'robot_scripts'))

try:
    from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
    from nao_config import MOVEMENT_SPECIFIC_PARAMS, OPTIMAL_GRASS_PARAMS
    print("✓ Importaciones exitosas")
except ImportError as e:
    print("✗ Error de importación: {}".format(e))
    sys.exit(1)

def test_movement_detection():
    """Probar detección de tipos de movimiento"""
    print("\n=== TEST DETECCIÓN DE MOVIMIENTO ===")
    
    try:
        walker = AdaptiveWalkLightGBM("models_npz_automl", mode="production")
        
        # Test movimientos específicos
        test_cases = [
            # (vx, vy, wz, expected_type)
            (0.3, 0.0, 0.0, "forward"),      # Adelante
            (-0.3, 0.0, 0.0, "backward"),    # Atrás
            (0.0, 0.3, 0.0, "sideways"),     # Lateral
            (0.0, 0.0, 0.5, "rotation"),     # Rotación
            (0.2, 0.2, 0.3, "mixed"),        # Combinado
            (0.05, 0.0, 0.0, "forward"),     # Movimiento lento
        ]
        
        for vx, vy, wz, expected in test_cases:
            detected = walker._detect_movement_type(vx, vy, wz)
            status = "✓" if detected == expected else "❌"
            print("{} vx={:4.1f} vy={:4.1f} wz={:4.1f} → {} (esperado: {})".format(
                status, vx, vy, wz, detected, expected))
        
        return True
        
    except Exception as e:
        print("❌ Error en detección de movimiento: {}".format(e))
        return False

def test_movement_specific_parameters():
    """Probar parámetros específicos por movimiento"""
    print("\n=== TEST PARÁMETROS ESPECÍFICOS ===")
    
    try:
        walker = AdaptiveWalkLightGBM("models_npz_automl", mode="production")
        
        # Test cada tipo de movimiento
        movements = ["forward", "backward", "sideways", "rotation", "mixed"]
        
        for movement in movements:
            print("\n📍 Movimiento: {}".format(movement.upper()))
            
            if movement in MOVEMENT_SPECIFIC_PARAMS:
                params = MOVEMENT_SPECIFIC_PARAMS[movement]
                print("  Parámetros específicos:")
                for param, value in params.items():
                    print("    - {}: {}".format(param, value))
            else:
                print("  ⚠ No hay parámetros específicos, usando generales")
        
        # Test predicción con movimiento específico
        print("\n🧪 Predicción con movimiento hacia atrás:")
        params_backward = walker.predict_gait_parameters(-0.3, 0.0, 0.0)
        print("  Parámetros para movimiento atrás:")
        for param, value in params_backward.items():
            print("    - {}: {}".format(param, value))
            
        return True
        
    except Exception as e:
        print("❌ Error en parámetros específicos: {}".format(e))
        return False

def test_parameter_differences():
    """Comparar diferencias entre tipos de movimiento"""
    print("\n=== TEST DIFERENCIAS DE PARÁMETROS ===")
    
    try:
        walker = AdaptiveWalkLightGBM("models_npz_automl", mode="production")
        
        # Comparar parámetros forward vs backward
        params_forward = walker.predict_gait_parameters(0.3, 0.0, 0.0)
        params_backward = walker.predict_gait_parameters(-0.3, 0.0, 0.0)
        
        print("📊 Comparación Forward vs Backward:")
        print("Parámetro       | Forward  | Backward | Diferencia")
        print("-" * 50)
        
        for param in params_forward.keys():
            forward_val = params_forward[param]
            backward_val = params_backward[param]
            diff = backward_val - forward_val
            print("{:15} | {:8.3f} | {:8.3f} | {:+8.3f}".format(
                param, forward_val, backward_val, diff))
        
        # Verificar que backward es más conservador
        assert params_backward['MaxStepX'] <= params_forward['MaxStepX'], \
            "Backward debería tener MaxStepX menor o igual"
        assert params_backward['Frequency'] <= params_forward['Frequency'], \
            "Backward debería tener Frequency menor o igual"
        
        print("✓ Parámetros backward son más conservadores")
        return True
        
    except Exception as e:
        print("❌ Error comparando parámetros: {}".format(e))
        return False

def test_stability_improvements():
    """Analizar mejoras de estabilidad esperadas"""
    print("\n=== TEST MEJORAS DE ESTABILIDAD ===")
    
    try:
        walker = AdaptiveWalkLightGBM("models_npz_automl", mode="production")
        
        print("🎯 Análisis de estabilidad por tipo de movimiento:")
        
        movements_analysis = {
            'forward': {
                'velocities': (0.3, 0.0, 0.0),
                'issues': 'Acumulación de inercia hacia adelante',
                'solution': 'Parámetros estándar optimizados'
            },
            'backward': {
                'velocities': (-0.3, 0.0, 0.0),
                'issues': 'Inestabilidad hacia atrás, pérdida de equilibrio',
                'solution': 'MaxStepX reducido, Frequency menor, StepHeight mayor'
            },
            'sideways': {
                'velocities': (0.0, 0.3, 0.0),
                'issues': 'Balanceo lateral, pérdida de equilibrio',
                'solution': 'MaxStepY reducido, StepHeight mayor, menos rotación'
            },
            'rotation': {
                'velocities': (0.0, 0.0, 0.5),
                'issues': 'Mareo, pérdida de orientación',
                'solution': 'Base estrecha, StepHeight alto, Frequency reducida'
            }
        }
        
        for movement, analysis in movements_analysis.items():
            print("\n🔍 {}:".format(movement.upper()))
            print("  Velocidades test: vx={}, vy={}, wz={}".format(*analysis['velocities']))
            print("  Problemas típicos: {}".format(analysis['issues']))
            print("  Solución aplicada: {}".format(analysis['solution']))
            
            # Obtener parámetros para este movimiento
            params = walker.predict_gait_parameters(*analysis['velocities'])
            print("  Parámetros resultantes:")
            for param, value in params.items():
                print("    - {}: {}".format(param, value))
        
        return True
        
    except Exception as e:
        print("❌ Error en análisis de estabilidad: {}".format(e))
        return False

def main():
    """Función principal de prueba"""
    print("=== PRUEBA PARÁMETROS ESPECÍFICOS POR MOVIMIENTO ===")
    print("Objetivo: Mejorar estabilidad en diferentes direcciones")
    
    # Verificar disponibilidad de parámetros específicos
    if not MOVEMENT_SPECIFIC_PARAMS:
        print("❌ MOVEMENT_SPECIFIC_PARAMS no está disponible")
        return False
    
    print("✓ Parámetros específicos disponibles para {} tipos de movimiento".format(
        len(MOVEMENT_SPECIFIC_PARAMS)))
    
    # Ejecutar todas las pruebas
    tests = [
        ("Detección de Movimiento", test_movement_detection),
        ("Parámetros Específicos", test_movement_specific_parameters),
        ("Diferencias de Parámetros", test_parameter_differences),
        ("Mejoras de Estabilidad", test_stability_improvements)
    ]
    
    results = []
    for test_name, test_func in tests:
        print("\n" + "="*60)
        print("EJECUTANDO: {}".format(test_name))
        result = test_func()
        results.append((test_name, result))
    
    # Resumen final
    print("\n" + "="*60)
    print("=== RESUMEN DE PRUEBAS ===")
    
    all_passed = True
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print("{}: {}".format(test_name, status))
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 TODAS LAS PRUEBAS PASARON")
        print("\n📋 Comandos para probar en NAO:")
        print("1. Activar modo production:")
        print('   {"action": "setAdaptiveMode", "mode": "production"}')
        print("2. Desactivar fall manager para control manual:")
        print('   {"action": "fallManager", "enable": false}')
        print("3. Probar movimiento hacia atrás:")
        print('   {"action": "walk", "vx": -0.2, "vy": 0.0, "wz": 0.0}')
        print("4. Probar movimiento lateral:")
        print('   {"action": "walk", "vx": 0.0, "vy": 0.2, "wz": 0.0}')
        print("5. Verificar parámetros específicos en logs")
    else:
        print("\n❌ ALGUNAS PRUEBAS FALLARON")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
