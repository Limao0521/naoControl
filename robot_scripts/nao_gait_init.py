#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NAO Gait Parameters Initializer
===============================

Script para inicializar correctamente el robot NAO y configurar parámetros
de gait para que el monitor pueda leerlos correctamente.

Ejecutar ANTES del monitor para asegurar que los parámetros estén disponibles.

Uso en el NAO:
    python nao_gait_init.py

Compatible con Python 2.7 (NAO)
"""

import sys
import time

try:
    from naoqi import ALProxy
except ImportError:
    print("Error: Este script debe ejecutarse en el NAO con naoqi disponible")
    sys.exit(1)

def init_nao_for_monitoring():
    """Inicializar NAO para monitoreo de parámetros"""
    print("🤖 Inicializando NAO para monitoreo de parámetros de gait...")
    
    try:
        # Conectar proxies
        print("📡 Conectando proxies...")
        memory = ALProxy("ALMemory", "localhost", 9559)
        motion = ALProxy("ALMotion", "localhost", 9559)
        posture = ALProxy("ALRobotPosture", "localhost", 9559)
        print("✅ Proxies conectados")
        
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
        
        # 2. Poner robot en postura de pie
        print("🚶 Configurando postura...")
        try:
            current_posture = posture.getPosture()
            print("📍 Postura actual: {}".format(current_posture))
            
            if current_posture != "Stand":
                print("🔄 Cambiando a postura Stand...")
                posture.goToPosture("Stand", 0.8)
                time.sleep(2)
                print("✅ Robot en postura Stand")
            else:
                print("✅ Robot ya está en postura Stand")
        except Exception as e:
            print("⚠️  Error configurando postura: {}".format(e))
        
        # 3. Configurar parámetros de gait por defecto
        print("⚙️  Configurando parámetros de gait...")
        
        # Parámetros por defecto típicos del NAO
        default_params = {
            "MaxStepX": 0.04,      # 4 cm
            "MaxStepY": 0.14,      # 14 cm  
            "MaxStepTheta": 0.349, # ~20 grados
            "StepHeight": 0.02,    # 2 cm
            "Frequency": 1.0       # 1 Hz
        }
        
        # Intentar configurar usando diferentes métodos
        params_set = False
        
        # Método 1: ALMemory directo
        try:
            for param, value in default_params.items():
                memory_key = "Motion/Walk/{}".format(param)
                memory.insertData(memory_key, float(value))
            print("✅ Parámetros configurados en ALMemory")
            params_set = True
        except Exception as e:
            print("⚠️  Error configurando ALMemory: {}".format(e))
        
        # Método 2: ALMotion setWalkConfig (si existe)
        try:
            motion.setWalkConfig(
                default_params["MaxStepX"],
                default_params["MaxStepY"], 
                default_params["MaxStepTheta"],
                default_params["StepHeight"],
                default_params["Frequency"]
            )
            print("✅ Parámetros configurados en ALMotion")
            params_set = True
        except Exception as e:
            print("⚠️  setWalkConfig no disponible: {}".format(e))
        
        # 4. Verificar que los parámetros están disponibles
        print("🔍 Verificando parámetros configurados...")
        
        for param, expected_value in default_params.items():
            try:
                # Intentar leer desde ALMemory
                memory_key = "Motion/Walk/{}".format(param)
                actual_value = memory.getData(memory_key)
                
                if actual_value is not None:
                    print("✅ {}: {:.4f}".format(param, float(actual_value)))
                else:
                    print("⚠️  {}: No disponible en ALMemory".format(param))
            except Exception as e:
                print("❌ {}: Error leyendo - {}".format(param, e))
        
        # 5. Mensaje final
        if params_set:
            print("\n🎉 ¡NAO inicializado correctamente!")
            print("📊 Ahora puedes ejecutar el monitor:")
            print("   python monitor_live_gait_params_local.py")
        else:
            print("\n⚠️  Inicialización parcial")
            print("🔄 El monitor puede mostrar valores por defecto")
        
        print("\n💡 COMANDOS ÚTILES:")
        print("🏃 Para hacer caminar: motion.moveToward(0.5, 0, 0)")
        print("🛑 Para detener: motion.stopMove()")
        print("📊 Para monitorear: python monitor_live_gait_params_local.py")
        
    except Exception as e:
        print("❌ Error durante inicialización: {}".format(e))
        return False
    
    return True

def test_walking_basic():
    """Test básico de caminata para verificar parámetros"""
    print("\n🧪 Test básico de caminata...")
    
    try:
        motion = ALProxy("ALMotion", "localhost", 9559)
        
        print("🏃 Iniciando caminata lenta...")
        motion.moveToward(0.3, 0, 0)  # Velocidad lenta hacia adelante
        
        print("⏱️  Caminando por 3 segundos...")
        time.sleep(3)
        
        print("🛑 Deteniendo...")
        motion.stopMove()
        
        print("✅ Test de caminata completado")
        print("📊 Ahora ejecutar monitor para ver parámetros durante la caminata")
        
    except Exception as e:
        print("❌ Error en test de caminata: {}".format(e))

def main():
    """Función principal"""
    print("🚀 NAO GAIT PARAMETERS INITIALIZER")
    print("===================================")
    print("Este script prepara el NAO para monitoreo de parámetros de gait")
    print()
    
    # Inicializar
    success = init_nao_for_monitoring()
    
    if success:
        print("\n¿Quieres hacer un test básico de caminata? (y/n): ")
        try:
            # Python 2 compatible input
            import sys
            if sys.version_info[0] >= 3:
                response = input().strip().lower()
            else:
                response = raw_input().strip().lower()
                
            if response in ['y', 'yes', 'si', 's']:
                test_walking_basic()
        except Exception as e:
            print("⚠️  No se pudo leer entrada: {}".format(e))
    
    print("\n👋 Inicializador finalizado")

if __name__ == "__main__":
    main()
