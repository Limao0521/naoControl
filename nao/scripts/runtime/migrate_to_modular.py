#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
migrate_to_modular.py - Script de migración a arquitectura modular

Este script facilita la migración del control_server.py monolítico 
a la nueva arquitectura modular v2.0
"""

from __future__ import print_function
import os
import sys
import shutil
import time
from datetime import datetime

def print_banner():
    """Mostrar banner de migración."""
    print("=" * 70)
    print("  CONTROL SERVER - MIGRACIÓN A ARQUITECTURA MODULAR v2.0")
    print("=" * 70)
    print()

def backup_original():
    """Crear respaldo del control_server.py original."""
    original_path = "/data/home/nao/scripts/runtime/control_server.py"
    
    if os.path.exists(original_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = "/data/home/nao/scripts/runtime/control_server_v1_backup_{}.py".format(timestamp)
        
        try:
            shutil.copy2(original_path, backup_path)
            print("✓ Respaldo creado: {}".format(backup_path))
            return backup_path
        except Exception as e:
            print("✗ Error creando respaldo: {}".format(e))
            return None
    else:
        print("⚠ Archivo original no encontrado: {}".format(original_path))
        return None

def check_dependencies():
    """Verificar dependencias necesarias."""
    print("\n--- VERIFICANDO DEPENDENCIAS ---")
    
    dependencies = [
        "naoqi",
        "SimpleWebSocketServer", 
        "json",
        "threading",
        "socket"
    ]
    
    missing = []
    for dep in dependencies:
        try:
            __import__(dep)
            print("✓ {} - OK".format(dep))
        except ImportError:
            print("✗ {} - FALTANTE".format(dep))
            missing.append(dep)
    
    if missing:
        print("\n⚠ Dependencias faltantes: {}".format(", ".join(missing)))
        return False
    else:
        print("\n✓ Todas las dependencias están disponibles")
        return True

def verify_modular_structure():
    """Verificar que la estructura modular esté presente."""
    print("\n--- VERIFICANDO ESTRUCTURA MODULAR ---")
    
    base_path = "/data/home/nao/scripts/runtime/control_server"
    
    required_files = [
        "__init__.py",
        "base_command.py", 
        "command_factory.py",
        "server.py",
        "facades/nao_facade.py",
        "strategies/movement_strategies.py",
        "commands/movement_commands.py",
        "commands/basic_commands.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            print("✓ {}".format(file_path))
        else:
            print("✗ {} - FALTANTE".format(file_path))
            missing_files.append(file_path)
    
    if missing_files:
        print("\n⚠ Archivos faltantes: {}".format(len(missing_files)))
        return False
    else:
        print("\n✓ Estructura modular completa")
        return True

def test_import_modular():
    """Probar importación de componentes modulares."""
    print("\n--- PROBANDO IMPORTACIÓN MODULAR ---")
    
    # Cambiar al directorio correcto
    original_path = sys.path[:]
    sys.path.insert(0, "/data/home/nao/scripts/runtime")
    
    try:
        # Probar imports principales
        from control_server.facades.nao_facade import NAOFacade
        print("✓ NAOFacade importado")
        
        from control_server.command_factory import CommandFactory
        print("✓ CommandFactory importado")
        
        from control_server.base_command import BaseCommand
        print("✓ BaseCommand importado")
        
        from control_server.strategies.movement_strategies import MovementContext
        print("✓ MovementContext importado")
        
        print("\n✓ Todos los módulos se importaron correctamente")
        return True
        
    except ImportError as e:
        print("✗ Error de importación: {}".format(e))
        return False
    except Exception as e:
        print("✗ Error inesperado: {}".format(e))
        return False
    finally:
        # Restaurar path original
        sys.path[:] = original_path

def create_launcher_script():
    """Crear script launcher que mantenga compatibilidad."""
    print("\n--- CREANDO LAUNCHER COMPATIBLE ---")
    
    launcher_content = '''#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
control_server.py - Launcher compatible con v2.0

Este script mantiene compatibilidad con llamadas antiguas
pero ejecuta la nueva arquitectura modular.
"""

from __future__ import print_function
import sys
import os

# Añadir paths necesarios
sys.path.insert(0, os.path.dirname(__file__))

def main():
    print("Control Server - Launcher v2.0 Compatible")
    print("Iniciando arquitectura modular...")
    
    try:
        # Importar e iniciar servidor modular
        from control_server.server import ModularControlServer
        
        server = ModularControlServer()
        return server.start_server()
        
    except ImportError as e:
        print("Error: No se pudo importar servidor modular: {}".format(e))
        print("Verificar que la estructura modular esté completa")
        return False
    except Exception as e:
        print("Error fatal: {}".format(e))
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
'''
    
    launcher_path = "/data/home/nao/scripts/runtime/control_server_v2.py"
    
    try:
        with open(launcher_path, 'w') as f:
            f.write(launcher_content)
        
        # Hacer ejecutable
        os.chmod(launcher_path, 0o755)
        
        print("✓ Launcher creado: {}".format(launcher_path))
        return launcher_path
    except Exception as e:
        print("✗ Error creando launcher: {}".format(e))
        return None

def run_migration():
    """Ejecutar proceso completo de migración."""
    print_banner()
    
    # Paso 1: Crear respaldo
    print("PASO 1: Creando respaldo del archivo original...")
    backup_path = backup_original()
    
    # Paso 2: Verificar dependencias
    print("\nPASO 2: Verificando dependencias...")
    if not check_dependencies():
        print("\n❌ MIGRACIÓN ABORTADA: Dependencias faltantes")
        return False
    
    # Paso 3: Verificar estructura modular
    print("\nPASO 3: Verificando estructura modular...")
    if not verify_modular_structure():
        print("\n❌ MIGRACIÓN ABORTADA: Estructura modular incompleta")
        return False
    
    # Paso 4: Probar importaciones
    print("\nPASO 4: Probando importaciones...")
    if not test_import_modular():
        print("\n❌ MIGRACIÓN ABORTADA: Errores de importación")
        return False
    
    # Paso 5: Crear launcher compatible
    print("\nPASO 5: Creando launcher compatible...")
    launcher_path = create_launcher_script()
    if not launcher_path:
        print("\n⚠ ADVERTENCIA: No se pudo crear launcher, usar ruta completa")
    
    # Paso 6: Resumen final
    print("\n" + "="*70)
    print("  MIGRACIÓN COMPLETADA EXITOSAMENTE ✓")
    print("="*70)
    
    print("\n📋 RESUMEN:")
    if backup_path:
        print("   • Respaldo original: {}".format(backup_path))
    print("   • Servidor modular: /data/home/nao/scripts/runtime/control_server/server.py")
    if launcher_path:
        print("   • Launcher compatible: {}".format(launcher_path))
    
    print("\n🚀 OPCIONES DE EJECUCIÓN:")
    print("   1. Directo:    python2 control_server/server.py")
    if launcher_path:
        print("   2. Launcher:   python2 control_server_v2.py")
    
    print("\n📖 DOCUMENTACIÓN:")
    print("   • README: control_server/README.md")
    print("   • Arquitectura: Patrones Command, Strategy, Factory, Facade")
    
    print("\n⚡ VENTAJAS v2.0:")
    print("   • Código modular y mantenible")
    print("   • Fácil extensión con nuevos comandos")
    print("   • Mejor testing y debugging")
    print("   • API 100% compatible con v1.0")
    
    print("\n" + "="*70)
    return True

if __name__ == "__main__":
    try:
        success = run_migration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Migración interrumpida por usuario")
        sys.exit(1)
    except Exception as e:
        print("\n❌ Error fatal en migración: {}".format(e))
        sys.exit(1)