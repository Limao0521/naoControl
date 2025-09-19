#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
nao_diagnostics_utils.py - Utilidades Consolidadas de Diagnóstico y Setup NAO
===========================================================================

ARCHIVO CONSOLIDADO que combina:
- nao_connection_test.py (diagnóstico de conexión NAOqi)
- nao_gait_init.py (inicialización de parámetros de gait)

Funcionalidades:
- Diagnóstico completo de conectividad NAOqi
- Test de red y puertos
- Inicialización automática del robot para monitoreo  
- Setup de parámetros de gait
- Verificación de estado del robot

Uso:
    python nao_diagnostics_utils.py --test-only           # Solo diagnóstico
    python nao_diagnostics_utils.py --init-gait          # Diagnóstico + inicialización
    python nao_diagnostics_utils.py --ip 192.168.1.100   # IP específica
"""

from __future__ import print_function
import sys
import time
import socket
import argparse

def test_naoqi_import():
    """Test 1: Verificar importación de NAOqi"""
    print("\n=== TEST 1: Importación NAOqi ===")
    try:
        from naoqi import ALProxy
        import almath
        print("[OK] NAOqi modules importados correctamente")
        return True, ALProxy
    except ImportError as e:
        print("[ERROR] No se puede importar NAOqi: {}".format(e))
        print("[INFO] Posibles soluciones:")
        print("  - Instalar NAOqi SDK")
        print("  - Configurar PYTHONPATH")
        print("  - Ejecutar desde entorno NAO")
        return False, None

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
            print("[INFO] Verificar:")
            print("  - Robot encendido y conectado")
            print("  - IP correcta")
            print("  - Firewall/red")
            return False
    except Exception as e:
        print("[ERROR] Error de red: {}".format(e))
        return False

def test_basic_proxies(ALProxy, ip="127.0.0.1", port=9559):
    """Test 3: Verificar proxies básicos de NAOqi"""
    print("\n=== TEST 3: Proxies NAOqi Básicos ===")
    
    proxies_to_test = [
        ("ALMemory", "Memoria del robot"),
        ("ALMotion", "Control de movimiento"),
        ("ALRobotPosture", "Control de postura"),
        ("ALTextToSpeech", "Síntesis de voz")
    ]
    
    working_proxies = {}
    
    for proxy_name, description in proxies_to_test:
        try:
            proxy = ALProxy(proxy_name, ip, port)
            print("[OK] {}: {}".format(proxy_name, description))
            working_proxies[proxy_name] = proxy
        except Exception as e:
            print("[ERROR] {}: {}".format(proxy_name, e))
    
    return working_proxies

def test_robot_state(working_proxies):
    """Test 4: Verificar estado actual del robot"""
    print("\n=== TEST 4: Estado del Robot ===")
    
    try:
        memory = working_proxies.get("ALMemory")
        motion = working_proxies.get("ALMotion")
        
        if not memory or not motion:
            print("[SKIP] Proxies necesarios no disponibles")
            return False
        
        # Test estado despierto
        try:
            is_awake = memory.getData("robotIsWakeUp")
            print("[INFO] Robot despierto: {}".format("Sí" if is_awake else "No"))
        except:
            print("[WARN] No se pudo verificar estado de despierto")
        
        # Test rigidez
        try:
            stiffness = motion.getStiffnesses("Body")
            avg_stiffness = sum(stiffness) / len(stiffness) if stiffness else 0
            print("[INFO] Rigidez promedio: {:.2f}".format(avg_stiffness))
        except:
            print("[WARN] No se pudo verificar rigidez")
        
        # Test temperatura
        try:
            temp_head = memory.getData("Device/SubDeviceList/HeadYaw/Temperature/Sensor/Value")
            print("[INFO] Temperatura cabeza: {:.1f}°C".format(temp_head))
        except:
            print("[WARN] No se pudo verificar temperatura")
        
        return True
        
    except Exception as e:
        print("[ERROR] Error verificando estado: {}".format(e))
        return False

def init_robot_for_monitoring(working_proxies):
    """Inicialización completa del robot para monitoreo"""
    print("\n🤖 Inicializando NAO para monitoreo de parámetros...")
    
    try:
        memory = working_proxies.get("ALMemory")
        motion = working_proxies.get("ALMotion")
        posture = working_proxies.get("ALRobotPosture")
        
        if not all([memory, motion, posture]):
            print("❌ No todos los proxies necesarios están disponibles")
            return False
        
        # 1. Despertar robot si está dormido
        print("⏰ Verificando estado del robot...")
        try:
            is_awake = memory.getData("robotIsWakeUp")
            if not is_awake:
                print("💤 Robot dormido, despertando...")
                motion.wakeUp()
                time.sleep(3)
                print("✅ Robot despierto")
            else:
                print("✅ Robot ya está despierto")
        except:
            print("⚠️  No se pudo verificar estado, intentando despertar...")
            motion.wakeUp()
            time.sleep(3)
        
        # 2. Configurar rigidez
        print("💪 Configurando rigidez corporal...")
        motion.setStiffnesses("Body", 1.0)
        time.sleep(1)
        print("✅ Rigidez corporal activada")
        
        # 3. Posición inicial
        print("🕴️  Estableciendo postura inicial...")
        try:
            posture.goToPosture("Stand", 0.8)
            print("✅ Postura Stand establecida")
        except Exception as e:
            print("⚠️  Error en postura: {}".format(e))
        
        # 4. Configurar parámetros de gait iniciales
        print("👣 Configurando parámetros de gait básicos...")
        try:
            # Parámetros conservadores para empezar
            motion.setMoveArmsEnabled(True, True)
            motion.setMotionConfig([["ENABLE_FOOT_CONTACT_PROTECTION", True]])
            
            # Establecer parámetros básicos de gait
            default_gait = [
                ["MaxStepX", 0.04],
                ["MaxStepY", 0.14], 
                ["MaxStepTheta", 0.35],
                ["StepHeight", 0.02],
                ["Frequency", 1.0]
            ]
            
            motion.setMoveArmsEnabled(True, True)
            print("✅ Parámetros de gait configurados")
            
        except Exception as e:
            print("⚠️  Error configurando gait: {}".format(e))
        
        # 5. Verificar que los parámetros se pueden leer
        print("🔍 Verificando lectura de parámetros...")
        try:
            # Test de lectura de algunos valores clave
            test_reads = [
                "Device/SubDeviceList/LFoot/FSR/FrontLeft/Sensor/Value",
                "Device/SubDeviceList/InertialSensor/AccX/Sensor/Value",
                "Device/SubDeviceList/InertialSensor/AngleX/Sensor/Value"
            ]
            
            readable_count = 0
            for key in test_reads:
                try:
                    value = memory.getData(key)
                    readable_count += 1
                except:
                    pass
            
            print("✅ {}/{} sensores legibles".format(readable_count, len(test_reads)))
            
        except Exception as e:
            print("⚠️  Error verificando sensores: {}".format(e))
        
        print("\n🎉 Inicialización completada!")
        print("💡 El robot está listo para:")
        print("   - Monitoreo con monitor_live_gait_params_local.py")
        print("   - Control remoto con control_server.py")
        print("   - Captura de datos con data_logger.py")
        
        return True
        
    except Exception as e:
        print("❌ Error durante inicialización: {}".format(e))
        return False

def run_complete_diagnostic(ip="127.0.0.1", port=9559, init_gait=False):
    """Ejecutar diagnóstico completo"""
    print("🔧 DIAGNÓSTICO COMPLETO NAO")
    print("=" * 30)
    print("IP: {}:{}".format(ip, port))
    print("Inicialización: {}".format("Sí" if init_gait else "No"))
    
    # Test 1: Importación
    naoqi_ok, ALProxy = test_naoqi_import()
    if not naoqi_ok:
        return False
    
    # Test 2: Red
    network_ok = test_network_connection(ip, port)
    if not network_ok:
        return False
    
    # Test 3: Proxies
    working_proxies = test_basic_proxies(ALProxy, ip, port)
    if not working_proxies:
        print("\n❌ No se pudieron establecer proxies NAOqi")
        return False
    
    # Test 4: Estado
    state_ok = test_robot_state(working_proxies)
    
    # Inicialización opcional
    if init_gait:
        init_ok = init_robot_for_monitoring(working_proxies)
        if not init_ok:
            print("\n⚠️  Inicialización falló, pero diagnóstico OK")
    
    print("\n✅ DIAGNÓSTICO COMPLETADO")
    print("🤖 Robot NAO operativo en {}:{}".format(ip, port))
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Diagnóstico y utilidades consolidadas para NAO',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python nao_diagnostics_utils.py --test-only
  python nao_diagnostics_utils.py --init-gait --ip 192.168.1.100
  python nao_diagnostics_utils.py --full-diagnostic
        """
    )
    
    parser.add_argument('--ip', default='127.0.0.1', 
                        help='IP del robot NAO (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=9559,
                        help='Puerto NAOqi (default: 9559)')
    parser.add_argument('--test-only', action='store_true',
                        help='Solo ejecutar diagnósticos, sin inicialización')
    parser.add_argument('--init-gait', action='store_true',
                        help='Incluir inicialización de gait')
    parser.add_argument('--full-diagnostic', action='store_true',
                        help='Diagnóstico completo + inicialización')
    
    args = parser.parse_args()
    
    # Determinar modo de operación
    if args.full_diagnostic:
        init_gait = True
    elif args.init_gait:
        init_gait = True
    else:
        init_gait = False
    
    try:
        success = run_complete_diagnostic(args.ip, args.port, init_gait)
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Diagnóstico interrumpido por usuario")
        sys.exit(1)
    except Exception as e:
        print("\n❌ Error inesperado: {}".format(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
