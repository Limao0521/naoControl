#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Test del action recordMode del control_server
Simula llamadas al action para verificar funcionamiento
"""

import sys
import os
import json

# Añadir ruta del sistema
sys.path.append('/data/home/nao/scripts/runtime')

def test_record_functions():
    print("=== TEST DE FUNCIONES DEL RECORD SYSTEM ===")
    
    try:
        # Importar funciones
        from record_system import get_record_system, toggle_record_mode, get_record_status, cleanup_record_system
        print("✓ Importación exitosa")
        
        # Obtener estado inicial
        print("\n1. Estado inicial:")
        status = get_record_status()
        print("   Estado:", json.dumps(status, indent=2))
        
        # Obtener sistema
        print("\n2. Obteniendo sistema:")
        system = get_record_system()
        print("   Sistema creado:", type(system).__name__)
        
        # Alternar modo (activar)
        print("\n3. Activando modo de grabación:")
        result1 = toggle_record_mode()
        print("   Resultado:", result1)
        status1 = get_record_status()
        print("   Estado después:", json.dumps(status1, indent=2))
        
        # Verificar que está activo
        if status1.get("mode_active"):
            print("   ✓ Modo ACTIVADO correctamente")
        else:
            print("   ✗ Modo NO se activó")
        
        # Alternar modo (desactivar)
        print("\n4. Desactivando modo de grabación:")
        result2 = toggle_record_mode()
        print("   Resultado:", result2)
        status2 = get_record_status()
        print("   Estado después:", json.dumps(status2, indent=2))
        
        # Verificar que está desactivo
        if not status2.get("mode_active"):
            print("   ✓ Modo DESACTIVADO correctamente")
        else:
            print("   ✗ Modo NO se desactivó")
        
        print("\n=== TEST COMPLETADO ===")
        
    except Exception as e:
        print("✗ Error durante el test: {}".format(e))
        import traceback
        traceback.print_exc()

def test_control_server_imports():
    print("\n=== TEST DE IMPORTACIÓN EN CONTROL SERVER ===")
    
    try:
        # Simular importación como en control_server
        sys.path.insert(0, '/data/home/nao/scripts/runtime')
        
        # Intentar importar exactamente como en control_server
        from record_system import get_record_system, toggle_record_mode, get_record_status, cleanup_record_system
        RECORD_SYSTEM_AVAILABLE = True
        print("✓ Importación exitosa - RECORD_SYSTEM_AVAILABLE = True")
        
        # Simular action recordMode
        print("\nSimulando action recordMode:")
        success = toggle_record_mode()
        status = get_record_status()
        
        response = {
            "recordMode": {
                "success": success,
                "mode_active": status["mode_active"],
                "recording": status["recording"],
                "current_file": status.get("current_file"),
                "recordings_dir": status.get("recordings_dir"),
                "help": "Presione bumper derecho del pie para grabar (mantener presionado)"
            }
        }
        
        print("Respuesta JSON:")
        print(json.dumps(response, indent=2))
        
    except Exception as e:
        print("✗ Error en importación control_server: {}".format(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_record_functions()
    test_control_server_imports()