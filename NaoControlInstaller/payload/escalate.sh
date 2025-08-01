#!/bin/bash

# Script de escalada de privilegios para NAO Control
# Este script debe ejecutarse como ROOT desde /data/home/nao/

echo "=== NAO Control - Instalación de Archivos del Sistema ==="
echo "Ejecutándose como usuario: $(whoami)"
echo

# Verificar que se está ejecutando como root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Este script debe ejecutarse como ROOT"
    echo "Por favor ejecute:"
    echo "1. su"
    echo "2. ./escalate.sh"
    exit 1
fi

# Función para verificar si un comando se ejecutó correctamente
check_command() {
    if [ $? -eq 0 ]; then
        echo "  ✓ $1"
        return 0
    else
        echo "  ✗ Error: $1"
        return 1
    fi
}

# Verificar que estamos en el directorio correcto
if [ ! -f "./rc.local" ] || [ ! -f "./nao-launcher.service" ]; then
    echo "Error: No se encuentran los archivos necesarios en el directorio actual"
    echo "Este script debe ejecutarse desde /data/home/nao/"
    echo "Archivos requeridos: rc.local, nao-launcher.service"
    exit 1
fi

echo "Archivos encontrados correctamente"
echo "Iniciando instalación de archivos del sistema..."
echo

# Crear directorios necesarios
echo "Creando directorios del sistema..."
mkdir -p /data/etc 2>/dev/null
check_command "Directorio /data/etc creado"

mkdir -p /data/etc/systemd/system 2>/dev/null
check_command "Directorio /data/etc/systemd/system creado"

# Copiar rc.local
echo "Instalando rc.local..."
cp /data/home/nao/rc.local /data/etc/rc.local 2>/dev/null
if check_command "rc.local copiado a /data/etc/rc.local"; then
    chmod +x /data/etc/rc.local 2>/dev/null
    check_command "Permisos de ejecución asignados a rc.local"
else
    echo "  ✗ Error copiando rc.local"
    exit 1
fi

# Copiar servicio systemd
echo "Instalando servicio systemd..."
cp /data/home/nao/nao-launcher.service /data/etc/systemd/system/nao-launcher.service 2>/dev/null
if check_command "nao-launcher.service copiado"; then
    chmod 644 /data/etc/systemd/system/nao-launcher.service 2>/dev/null
    check_command "Permisos asignados a nao-launcher.service"
else
    echo "  ✗ Error copiando nao-launcher.service"
    exit 1
fi

# Intentar habilitar el servicio (puede fallar en algunos sistemas)
echo "Intentando habilitar servicio para inicio automático..."
systemctl enable nao-launcher.service 2>/dev/null
if [ $? -eq 0 ]; then
    check_command "Servicio nao-launcher habilitado"
else
    echo "  ⚠ Advertencia: No se pudo habilitar automáticamente el servicio"
    echo "    El servicio se iniciará manualmente al reiniciar"
fi

# Verificación final
echo
echo "Verificando instalación..."
if [ -f "/data/etc/rc.local" ] && [ -f "/data/etc/systemd/system/nao-launcher.service" ]; then
    echo
    echo "=== Escalada de privilegios completada exitosamente ==="
    echo "✓ rc.local instalado en /data/etc/rc.local"
    echo "✓ nao-launcher.service instalado en /data/etc/systemd/system/"
    echo "✓ Archivos del sistema instalados correctamente"
    echo
    echo "Puede salir del usuario root ejecutando: exit"
    exit 0
else
    echo
    echo "=== Error en la instalación ==="
    echo "Algunos archivos no se copiaron correctamente"
    exit 1
fi
