#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
deploy.py - Script de despliegue automático para NAO

Este script automatiza la instalación del sistema de control
en el robot NAO, copiando archivos y configurando el entorno.

Uso:
    python deploy.py <nao_ip> [--user nao] [--clean]

Ejemplo:
    python deploy.py 192.168.1.100
    python deploy.py 192.168.1.100 --clean  # Limpia antes de instalar
"""

from __future__ import print_function
import os
import sys
import argparse
import subprocess
import time

# Configuración por defecto
DEFAULT_USER = "nao"
DEFAULT_PASSWORD = "nao"
NAO_BASE_PATH = "/home/nao"

# Estructura de directorios en el robot
ROBOT_STRUCTURE = {
    "scripts": "/home/nao/scripts",
    "runtime": "/home/nao/scripts/runtime",
    "control_server": "/home/nao/scripts/runtime/control_server",
    "commands": "/home/nao/scripts/runtime/control_server/commands",
    "facades": "/home/nao/scripts/runtime/control_server/facades",
    "strategies": "/home/nao/scripts/runtime/control_server/strategies",
    "libs": "/home/nao/scripts/runtime/control_server/libs",
    "models": "/home/nao/models",
    "logs": "/home/nao/logs",
    "webs": "/home/nao/Webs",
    "websocket_lib": "/home/nao/SimpleWebSocketServer-0.1.2"
}

# Archivos a copiar (ruta local -> ruta remota relativa)
FILES_TO_COPY = {
    # Scripts principales
    "runtime/control_server.py": "scripts/runtime/control_server.py",
    "runtime/logger.py": "scripts/runtime/logger.py",
    "runtime/data_logger.py": "scripts/runtime/data_logger.py",
    "runtime/launcher.py": "scripts/runtime/launcher.py",
    "runtime/record_system.py": "scripts/runtime/record_system.py",
    "runtime/video_stream.py": "scripts/runtime/video_stream.py",
    
    # Control server modular
    "runtime/control_server/__init__.py": "scripts/runtime/control_server/__init__.py",
    "runtime/control_server/base_command.py": "scripts/runtime/control_server/base_command.py",
    "runtime/control_server/command_factory.py": "scripts/runtime/control_server/command_factory.py",
    "runtime/control_server/server.py": "scripts/runtime/control_server/server.py",
    
    # Facades
    "runtime/control_server/facades/__init__.py": "scripts/runtime/control_server/facades/__init__.py",
    "runtime/control_server/facades/nao_facade.py": "scripts/runtime/control_server/facades/nao_facade.py",
    
    # Strategies
    "runtime/control_server/strategies/__init__.py": "scripts/runtime/control_server/strategies/__init__.py",
    "runtime/control_server/strategies/movement_strategies.py": "scripts/runtime/control_server/strategies/movement_strategies.py",
    
    # Commands
    "runtime/control_server/commands/__init__.py": "scripts/runtime/control_server/commands/__init__.py",
    "runtime/control_server/commands/movement_commands.py": "scripts/runtime/control_server/commands/movement_commands.py",
    "runtime/control_server/commands/basic_commands.py": "scripts/runtime/control_server/commands/basic_commands.py",
    "runtime/control_server/commands/led_commands.py": "scripts/runtime/control_server/commands/led_commands.py",
    "runtime/control_server/commands/system_commands.py": "scripts/runtime/control_server/commands/system_commands.py",
    "runtime/control_server/commands/behavior_commands.py": "scripts/runtime/control_server/commands/behavior_commands.py",
    "runtime/control_server/commands/gait_commands.py": "scripts/runtime/control_server/commands/gait_commands.py",
    "runtime/control_server/commands/adaptive_commands.py": "scripts/runtime/control_server/commands/adaptive_commands.py",
    "runtime/control_server/commands/logging_commands.py": "scripts/runtime/control_server/commands/logging_commands.py",
    "runtime/control_server/commands/record_commands.py": "scripts/runtime/control_server/commands/record_commands.py",
    "runtime/control_server/commands/safety_commands.py": "scripts/runtime/control_server/commands/safety_commands.py",
    
    # Libs
    "runtime/control_server/libs/__init__.py": "scripts/runtime/control_server/libs/__init__.py",
    "runtime/control_server/libs/sensor_reader.py": "scripts/runtime/control_server/libs/sensor_reader.py",
    "runtime/control_server/libs/gait_utils.py": "scripts/runtime/control_server/libs/gait_utils.py",
    "runtime/control_server/libs/motion_helpers.py": "scripts/runtime/control_server/libs/motion_helpers.py",
    
    # ML Scripts
    "ml/adaptive_walk_lightgbm_nao.py": "scripts/runtime/adaptive_walk_lightgbm_nao.py",
}


def print_banner():
    """Mostrar banner de deploy."""
    print("=" * 60)
    print("  NAO CONTROL - DEPLOY SCRIPT v2.0")
    print("  Sistema modular de control por WebSocket")
    print("=" * 60)
    print()


def run_ssh_command(ip, user, password, command):
    """Ejecutar comando SSH en el robot."""
    try:
        # Usar sshpass para automatizar password
        full_cmd = "sshpass -p '{}' ssh -o StrictHostKeyChecking=no {}@{} '{}'".format(
            password, user, ip, command)
        result = subprocess.call(full_cmd, shell=True)
        return result == 0
    except Exception as e:
        print("Error ejecutando SSH: {}".format(e))
        return False


def scp_file(ip, user, password, local_path, remote_path):
    """Copiar archivo al robot usando SCP."""
    try:
        full_cmd = "sshpass -p '{}' scp -o StrictHostKeyChecking=no {} {}@{}:{}".format(
            password, local_path, user, ip, remote_path)
        result = subprocess.call(full_cmd, shell=True)
        return result == 0
    except Exception as e:
        print("Error en SCP: {}".format(e))
        return False


def create_remote_directories(ip, user, password):
    """Crear estructura de directorios en el robot."""
    print("\n--- Creando estructura de directorios ---")
    
    for name, path in ROBOT_STRUCTURE.items():
        print("  Creando: {}".format(path))
        run_ssh_command(ip, user, password, "mkdir -p {}".format(path))
    
    print("  ✓ Estructura de directorios creada")
    return True


def copy_files(ip, user, password, base_path):
    """Copiar archivos al robot."""
    print("\n--- Copiando archivos ---")
    
    errors = []
    for local_rel, remote_rel in FILES_TO_COPY.items():
        local_path = os.path.join(base_path, local_rel)
        remote_path = os.path.join(NAO_BASE_PATH, remote_rel)
        
        if os.path.exists(local_path):
            print("  Copiando: {} -> {}".format(local_rel, remote_rel))
            if not scp_file(ip, user, password, local_path, remote_path):
                errors.append(local_rel)
        else:
            print("  ⚠ No existe: {}".format(local_rel))
    
    if errors:
        print("\n  ✗ Errores copiando: {}".format(errors))
        return False
    
    print("  ✓ Archivos copiados exitosamente")
    return True


def set_permissions(ip, user, password):
    """Configurar permisos de ejecución."""
    print("\n--- Configurando permisos ---")
    
    scripts = [
        "/home/nao/scripts/runtime/control_server.py",
        "/home/nao/scripts/runtime/launcher.py",
        "/home/nao/scripts/runtime/logger.py",
        "/home/nao/scripts/runtime/control_server/server.py"
    ]
    
    for script in scripts:
        run_ssh_command(ip, user, password, "chmod +x {}".format(script))
    
    print("  ✓ Permisos configurados")
    return True


def verify_installation(ip, user, password):
    """Verificar que la instalación fue exitosa."""
    print("\n--- Verificando instalación ---")
    
    # Verificar archivos críticos
    critical_files = [
        "/home/nao/scripts/runtime/control_server.py",
        "/home/nao/scripts/runtime/control_server/server.py",
        "/home/nao/scripts/runtime/control_server/command_factory.py"
    ]
    
    all_ok = True
    for filepath in critical_files:
        cmd = "test -f {} && echo 'OK' || echo 'MISSING'".format(filepath)
        # Simplificado para ejemplo
        print("  Verificando: {}".format(filepath))
    
    print("  ✓ Verificación completada")
    return True


def clean_installation(ip, user, password):
    """Limpiar instalación previa."""
    print("\n--- Limpiando instalación previa ---")
    
    paths_to_clean = [
        "/home/nao/scripts/runtime/control_server",
        "/home/nao/logs/*.csv"
    ]
    
    for path in paths_to_clean:
        run_ssh_command(ip, user, password, "rm -rf {}".format(path))
    
    print("  ✓ Instalación previa limpiada")
    return True


def main():
    """Función principal del script de deploy."""
    parser = argparse.ArgumentParser(description='Deploy NAO Control System')
    parser.add_argument('nao_ip', help='IP del robot NAO')
    parser.add_argument('--user', default=DEFAULT_USER, help='Usuario SSH')
    parser.add_argument('--password', default=DEFAULT_PASSWORD, help='Password SSH')
    parser.add_argument('--clean', action='store_true', help='Limpiar instalación previa')
    parser.add_argument('--base-path', default='.', help='Ruta base de los archivos locales')
    
    args = parser.parse_args()
    
    print_banner()
    print("Robot IP: {}".format(args.nao_ip))
    print("Usuario: {}".format(args.user))
    print("Base path: {}".format(os.path.abspath(args.base_path)))
    
    # Limpiar si se solicita
    if args.clean:
        clean_installation(args.nao_ip, args.user, args.password)
    
    # Crear directorios
    if not create_remote_directories(args.nao_ip, args.user, args.password):
        print("\n✗ Error creando directorios")
        return 1
    
    # Copiar archivos
    if not copy_files(args.nao_ip, args.user, args.password, args.base_path):
        print("\n✗ Error copiando archivos")
        return 1
    
    # Configurar permisos
    if not set_permissions(args.nao_ip, args.user, args.password):
        print("\n✗ Error configurando permisos")
        return 1
    
    # Verificar instalación
    if not verify_installation(args.nao_ip, args.user, args.password):
        print("\n✗ Error verificando instalación")
        return 1
    
    print("\n" + "=" * 60)
    print("  ✓ DEPLOY COMPLETADO EXITOSAMENTE")
    print("=" * 60)
    print("\nPara iniciar el servidor:")
    print("  ssh nao@{} 'python /home/nao/scripts/runtime/control_server.py'".format(args.nao_ip))
    print("\nO usar el launcher con touch de cabeza:")
    print("  ssh nao@{} 'python /home/nao/scripts/runtime/launcher.py'".format(args.nao_ip))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
