#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
nao_connection_test.py - Diagnóstico de conexión NAOqi

Este script ayuda a diagnosticar problemas de conexión con NAOqi
"""

from __future__ import print_function
import sys
import time
import socket

def test_naoqi_import():
    """Test 1: Verificar importación de NAOqi"""
    print("\n=== TEST 1: Importación NAOqi ===")
    try:
        from naoqi import ALProxy
        import almath
        print("[OK] NAOqi modules importados correctamente")
        return True
    except ImportError as e:
        print("[ERROR] No se puede importar NAOqi: {}".format(e))
        print("[INFO] Posibles soluciones:")
        print("  - Instalar NAOqi SDK")
        print("  - Configurar PYTHONPATH")
        print("  - Ejecutar desde entorno NAO")
        return False

def test_network_connection(ip="127.0.0.1", port=9559):
    """Test 2: Verificar conexión de red"""
    print("\n=== TEST 2: Conexión de Red ===")
    print("Probando conexión a {}:{}...".format(ip, port))
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result == 0:
            print("[OK] Puerto accesible en {}:{}".format(ip, port))
            return True
        else:
            print("[ERROR] No se puede conectar a {}:{}".format(ip, port))
            print("[INFO] Código de error: {}".format(result))
            return False
    except Exception as e:
        print("[ERROR] Error de red: {}".format(e))
        return False

def test_naoqi_connection(ip="127.0.0.1", port=9559):
    """Test 3: Verificar conexión NAOqi"""
    print("\n=== TEST 3: Conexión NAOqi ===")
    
    try:
        from naoqi import ALProxy
        
        print("Creando proxy ALMotion...")
        motion = ALProxy("ALMotion", ip, port)
        
        print("Verificando estado del robot...")
        is_awake = motion.robotIsWakeUp()
        print("[OK] Robot conectado. Despierto: {}".format(is_awake))
        
        print("Probando funciones básicas...")
        stiffness = motion.getStiffnesses("Body")
        print("[OK] Rigidez corporal: {:.2f}".format(stiffness[0] if stiffness else 0.0))
        
        return True
        
    except Exception as e:
        print("[ERROR] Error conectando a NAOqi: {}".format(e))
        print("[INFO] Detalles del error:")
        print("  Tipo: {}".format(type(e).__name__))
        print("  Mensaje: {}".format(str(e)))
        return False

def test_memory_proxy(ip="127.0.0.1", port=9559):
    """Test 4: Verificar proxy ALMemory"""
    print("\n=== TEST 4: Proxy ALMemory ===")
    
    try:
        from naoqi import ALProxy
        
        memory = ALProxy("ALMemory", ip, port)
        
        # Probar lectura de datos básicos
        test_keys = [
            "Device/SubDeviceList/InertialSensor/AccelerometerX/Sensor/Value",
            "MiddleTactilTouched",
            "Device/SubDeviceList/LFoot/FSR/FrontLeft/Sensor/Value"
        ]
        
        for key in test_keys:
            try:
                value = memory.getData(key)
                print("[OK] {}: {}".format(key.split('/')[-3], value))
            except Exception as e:
                print("[WARN] No se pudo leer {}: {}".format(key.split('/')[-1], e))
        
        return True
        
    except Exception as e:
        print("[ERROR] Error con ALMemory: {}".format(e))
        return False

def test_robot_status(ip="127.0.0.1", port=9559):
    """Test 5: Estado del robot"""
    print("\n=== TEST 5: Estado del Robot ===")
    
    try:
        from naoqi import ALProxy
        
        motion = ALProxy("ALMotion", ip, port)
        battery = ALProxy("ALBattery", ip, port)
        life = ALProxy("ALAutonomousLife", ip, port)
        
        # Estado básico
        awake = motion.robotIsWakeUp()
        print("Robot despierto: {}".format(awake))
        
        # Batería
        try:
            charge = battery.getBatteryCharge()
            print("Batería: {}%".format(charge))
        except:
            print("Batería: No disponible")
        
        # Autonomous Life
        try:
            life_state = life.getState()
            print("Autonomous Life: {}".format(life_state))
        except:
            print("Autonomous Life: No disponible")
        
        # Rigidez
        try:
            stiffness = motion.getStiffnesses("Body")
            avg_stiffness = sum(stiffness) / len(stiffness) if stiffness else 0
            print("Rigidez promedio: {:.2f}".format(avg_stiffness))
        except:
            print("Rigidez: No disponible")
        
        return True
        
    except Exception as e:
        print("[ERROR] Error verificando estado: {}".format(e))
        return False

def show_connection_help():
    """Mostrar ayuda para problemas de conexión"""
    print("\n" + "="*50)
    print("AYUDA PARA PROBLEMAS DE CONEXIÓN")
    print("="*50)
    print()
    print("Si hay errores de conexión, verifica:")
    print()
    print("1. ROBOT ENCENDIDO:")
    print("   - Presiona botón pecho del NAO")
    print("   - Espera que los ojos se pongan azules")
    print("   - El robot debe decir algo al encender")
    print()
    print("2. RED CONECTADA:")
    print("   - Verifica que NAO y PC están en la misma red")
    print("   - Prueba hacer ping: ping <IP_DEL_NAO>")
    print("   - Verifica IP del NAO en sus ojos")
    print()
    print("3. NAOQI EJECUTÁNDOSE:")
    print("   - NAOqi se inicia automáticamente al encender")
    print("   - Si falla, reinicia el robot")
    print("   - Verifica que puerto 9559 está abierto")
    print()
    print("4. DESDE EL NAO (SSH):")
    print("   - La IP debe ser 127.0.0.1 (localhost)")
    print("   - NAOqi ya está ejecutándose localmente")
    print()
    print("5. DESDE PC EXTERNO:")
    print("   - Usar IP real del NAO (ej: 192.168.1.100)")
    print("   - Verificar firewall y red")
    print()

def safe_input(prompt):
    """Input compatible con Python 2/3"""
    try:
        return raw_input(prompt)
    except NameError:
        return input(prompt)

def main():
    """Función principal de diagnóstico"""
    print("="*60)
    print("NAO CONNECTION DIAGNOSTIC TOOL")
    print("="*60)
    
    # Determinar si estamos en el NAO o en PC externo
    try:
        with open('/etc/hostname', 'r') as f:
            hostname = f.read().strip()
        if hostname == 'nao':
            print("Ejecutando DESDE el NAO - usando localhost")
            ip = "127.0.0.1"
        else:
            print("Ejecutando desde PC externo")
            ip = safe_input("IP del NAO (ej: 192.168.1.100): ").strip()
    except:
        print("Ejecutando desde PC externo")
        try:
            ip = safe_input("IP del NAO (ej: 192.168.1.100): ").strip()
        except:
            ip = safe_input("IP del NAO (ej: 192.168.1.100): ").strip()
    
    if not ip:
        ip = "127.0.0.1"
    
    port = 9559
    
    print("Probando conexión a {}:{}".format(ip, port))
    
    # Ejecutar tests
    tests = [
        ("Importación NAOqi", lambda: test_naoqi_import()),
        ("Conexión de red", lambda: test_network_connection(ip, port)),
        ("Conexión NAOqi", lambda: test_naoqi_connection(ip, port)),
        ("Proxy ALMemory", lambda: test_memory_proxy(ip, port)),
        ("Estado del robot", lambda: test_robot_status(ip, port))
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except KeyboardInterrupt:
            print("\nTest interrumpido por usuario")
            break
        except Exception as e:
            print("[ERROR] Test '{}' falló: {}".format(test_name, e))
            results.append((test_name, False))
    
    # Resumen de resultados
    print("\n" + "="*50)
    print("RESUMEN DE TESTS")
    print("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print("{}: {}".format(test_name, status))
        if result:
            passed += 1
    
    print("\nTests pasados: {}/{}".format(passed, len(results)))
    
    if passed == len(results):
        print("\n[SUCCESS] Conexión NAOqi funcionando correctamente!")
        print("El adaptive walk debería funcionar sin problemas.")
    elif passed >= 3:
        print("\n[WARNING] Conexión parcialmente funcional")
        print("Algunos tests fallaron pero funcionalidad básica disponible.")
    else:
        print("\n[ERROR] Problemas serios de conexión detectados")
        show_connection_help()

if __name__ == "__main__":
    main()
