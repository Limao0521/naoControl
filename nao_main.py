#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Sistema NAO Modular - Punto de entrada principal
Arquitectura mejorada para mejor mantenibilidad
"""

import sys
import os

# Agregar el directorio del sistema al path
sys.path.insert(0, os.path.dirname(__file__))

from nao_system.core.system_manager import get_system_manager, initialize_system
from nao_system.services.launcher_service import TouchLauncher

def main():
    """Función principal del sistema NAO modular"""
    print("=" * 60)
    print("Sistema NAO Modular v2.0")
    print("Arquitectura mejorada para mejor mantenibilidad")
    print("=" * 60)
    
    try:
        # Inicializar sistema
        print("Inicializando sistema...")
        system_manager = get_system_manager()
        
        if not system_manager.nao_adapter.is_connected():
            print("ADVERTENCIA: NAOqi no está disponible - ejecutando en modo simulación")
        
        # Mostrar estado inicial
        status = system_manager.get_system_status()
        print("\nEstado del sistema:")
        print("- NAO conectado: {}".format(status['nao_connected']))
        print("- Servicios disponibles: {}".format(len(status['services'])))
        
        for service_name, service_info in status['services'].items():
            print("  - {}: {}".format(service_name, service_info['type']))
        
        print("\nIniciando launcher...")
        
        # Crear y ejecutar launcher
        launcher = TouchLauncher()
        launcher.start()
        
    except KeyboardInterrupt:
        print("\nInterrupción de usuario detectada")
    except Exception as e:
        print("Error fatal: {}".format(e))
        import traceback
        traceback.print_exc()
    finally:
        print("\nCerrando sistema...")
        try:
            from nao_system.core.system_manager import shutdown_system
            shutdown_system()
        except Exception as e:
            print("Error cerrando sistema: {}".format(e))
        
        print("Sistema cerrado")

if __name__ == "__main__":
    main()
