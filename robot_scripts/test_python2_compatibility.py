#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
test_python2_compatibility.py - Prueba de compatibilidad con Python 2.7

Test básico para verificar que el código funciona en Python 2.7
"""

def test_imports():
    """Probar las importaciones básicas"""
    try:
        import sys
        import time
        import math
        import numpy as np
        import os
        print("[OK] Importaciones básicas exitosas")
        
        # Test básico de numpy
        arr = np.array([1, 2, 3])
        print("[OK] NumPy funcional: {}".format(arr))
        
        return True
    except Exception as e:
        print("[ERROR] Error en importaciones: {}".format(e))
        return False

def test_adaptive_walk_import():
    """Probar importación del adaptive walk"""
    try:
        # Cambiar al directorio donde está el script
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Intentar importar
        from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
        print("[OK] AdaptiveWalkLightGBM importado exitosamente")
        
        # Intentar crear instancia (sin modelos)
        try:
            walker = AdaptiveWalkLightGBM("models_test_dir")
            print("[OK] Instancia creada (sin modelos)")
        except Exception as e:
            print("[INFO] Instancia no creada (esperado sin modelos): {}".format(e))
        
        return True
    except Exception as e:
        print("[ERROR] Error importando AdaptiveWalkLightGBM: {}".format(e))
        return False

def test_naoqi_simulation():
    """Probar modo simulación (sin NAOqi)"""
    try:
        from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
        
        # Crear directorio temporal para test
        import os
        test_dir = "models_test_temp"
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
        
        # Instanciar en modo simulación
        walker = AdaptiveWalkLightGBM(test_dir)
        
        # Probar obtener datos de sensores (simulados)
        sensor_data = walker._get_sensor_data()
        print("[OK] Datos de sensores simulados: {}".format(len(sensor_data)))
        
        # Limpiar
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        
        return True
    except Exception as e:
        print("[ERROR] Error en simulación: {}".format(e))
        return False

def main():
    """Función principal de test"""
    print("="*50)
    print("TEST DE COMPATIBILIDAD PYTHON 2.7")
    print("="*50)
    
    tests = [
        ("Importaciones básicas", test_imports),
        ("Importación AdaptiveWalk", test_adaptive_walk_import),
        ("Simulación NAOqi", test_naoqi_simulation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print("\n[TEST] {}...".format(test_name))
        try:
            if test_func():
                print("[PASS] {} ✓".format(test_name))
                passed += 1
            else:
                print("[FAIL] {} ✗".format(test_name))
        except Exception as e:
            print("[FAIL] {} ✗ - {}".format(test_name, e))
    
    print("\n" + "="*50)
    print("RESULTADOS: {}/{} tests pasaron".format(passed, total))
    
    if passed == total:
        print("[SUCCESS] Código compatible con Python 2.7")
        return True
    else:
        print("[WARNING] Algunos tests fallaron")
        return False

if __name__ == "__main__":
    main()
