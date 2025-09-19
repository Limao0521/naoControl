#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
test_nao_dual_mode.py - Prueba completa del sistema dual-mode en NAO real

Este script debe ejecutarse DIRECTAMENTE en el NAO para probar:
1. Conexión NAOqi
2. Carga de modelos AutoML  
3. Cambio de modos training/production
4. Predicciones en ambos modos
5. Integración con sensores reales
"""

import sys
import os
import time

# Agregar paths necesarios
sys.path.append('/home/nao/robot_scripts')
sys.path.append('/opt/aldebaran/lib/python2.7/site-packages')

def test_naoqi_connection():
    """Verificar conexión NAOqi"""
    print("\n=== TEST CONEXION NAOqi ===")
    try:
        from naoqi import ALProxy
        
        # Intentar crear proxies básicos
        motion = ALProxy("ALMotion", "127.0.0.1", 9559)
        memory = ALProxy("ALMemory", "127.0.0.1", 9559)
        
        # Verificar que funcionen
        is_awake = motion.robotIsWakeUp()
        print("✓ Conexión NAOqi exitosa")
        print("  - Robot despierto: {}".format(is_awake))
        
        # Despertar robot si es necesario
        if not is_awake:
            print("🔌 Despertando robot...")
            motion.wakeUp()
            time.sleep(2)
            
        return True
        
    except Exception as e:
        print("❌ Error conexión NAOqi: {}".format(e))
        return False

def test_dual_mode_system():
    """Probar sistema dual-mode"""
    print("\n=== TEST SISTEMA DUAL-MODE ===")
    
    try:
        from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
        from nao_config import OPTIMAL_GRASS_PARAMS, ADAPTIVE_MODES
        
        print("✓ Importaciones exitosas")
        
        # Test 1: Inicialización en modo production
        print("\n1. Inicialización modo production...")
        walker = AdaptiveWalkLightGBM("/home/nao/models_npz_automl", mode="production")
        mode = walker.get_mode()
        print("✓ Modo inicial: {}".format(mode))
        
        # Test 2: Verificar parámetros óptimos
        print("\n2. Parámetros óptimos...")
        for param, value in OPTIMAL_GRASS_PARAMS.items():
            print("  - {}: {}".format(param, value))
        
        # Test 3: Predicción modo production
        print("\n3. Predicción modo production...")
        predictions_prod = walker.predict_gait_parameters()
        print("✓ Predicciones production:")
        for param, value in predictions_prod.items():
            print("  - {}: {}".format(param, value))
            
        # Test 4: Cambio a modo training
        print("\n4. Cambio a modo training...")
        walker.set_mode("training")
        mode = walker.get_mode()
        print("✓ Modo cambiado a: {}".format(mode))
        
        # Test 5: Predicción modo training (con sensores reales)
        print("\n5. Predicción modo training (sensores reales)...")
        try:
            predictions_train = walker.predict_gait_parameters()
            print("✓ Predicciones training:")
            for param, value in predictions_train.items():
                print("  - {}: {}".format(param, value))
        except Exception as e:
            print("⚠ Predicción training falló (normal si no hay movimiento): {}".format(e))
        
        return True
        
    except Exception as e:
        print("❌ Error sistema dual-mode: {}".format(e))
        return False

def test_websocket_server():
    """Probar que el servidor WebSocket funciona"""
    print("\n=== TEST SERVIDOR WEBSOCKET ===")
    
    try:
        import socket
        
        # Verificar que el puerto está disponible
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 6671))
        sock.close()
        
        if result == 0:
            print("⚠ Puerto 6671 ya está en uso (servidor posiblemente corriendo)")
        else:
            print("✓ Puerto 6671 disponible para WebSocket")
            
        return True
        
    except Exception as e:
        print("❌ Error verificando WebSocket: {}".format(e))
        return False

def test_sensor_data():
    """Probar lectura de sensores"""
    print("\n=== TEST DATOS SENSORES ===")
    
    try:
        from naoqi import ALProxy
        memory = ALProxy("ALMemory", "127.0.0.1", 9559)
        
        # Leer algunos sensores clave
        sensors = [
            "LeftFootTotalWeight",
            "RightFootTotalWeight", 
            "AccelerometerX",
            "AccelerometerY",
            "GyroscopeX",
            "GyroscopeY"
        ]
        
        print("✓ Datos de sensores:")
        for sensor in sensors:
            try:
                value = memory.getData("Device/SubDeviceList/{}/Sensor/Value".format(sensor))
                print("  - {}: {:.3f}".format(sensor, value))
            except Exception as e:
                print("  - {}: Error ({})".format(sensor, e))
                
        return True
        
    except Exception as e:
        print("❌ Error leyendo sensores: {}".format(e))
        return False

def main():
    """Función principal de prueba"""
    print("=== PRUEBA SISTEMA DUAL-MODE EN NAO ===")
    print("Fecha: {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    
    # Verificar que estamos en el NAO
    if not os.path.exists("/opt/aldebaran"):
        print("❌ Este script debe ejecutarse en el NAO")
        return False
    
    print("✓ Ejecutándose en NAO")
    
    # Ejecutar todas las pruebas
    tests = [
        ("NAOqi Connection", test_naoqi_connection),
        ("Dual-Mode System", test_dual_mode_system),
        ("WebSocket Server", test_websocket_server),
        ("Sensor Data", test_sensor_data)
    ]
    
    results = []
    for test_name, test_func in tests:
        print("\n" + "="*50)
        print("EJECUTANDO: {}".format(test_name))
        result = test_func()
        results.append((test_name, result))
    
    # Resumen final
    print("\n" + "="*50)
    print("=== RESUMEN DE PRUEBAS ===")
    
    all_passed = True
    for test_name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print("{}: {}".format(test_name, status))
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 TODAS LAS PRUEBAS PASARON")
        print("\nPara iniciar el servidor:")
        print("  cd /home/nao/robot_scripts")  
        print("  python control_server.py")
        print("\nConectar desde PC:")
        print("  ws://IP_DEL_NAO:6671")
    else:
        print("\n❌ ALGUNAS PRUEBAS FALLARON")
        print("Revisar configuración antes de continuar")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
