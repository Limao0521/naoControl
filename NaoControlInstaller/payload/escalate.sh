#!/bin/bash

# Script de escalada de privilegios para NAO Control
# Este script debe ejecutarse desde /data/home/nao/

echo "=== NAO Control - Escalada de Privilegios ==="
echo "Se requieren privilegios de root para instalar archivos del sistema"
echo

# Función para verificar si un comando se ejecutó correctamente
check_command() {
    if [ $? -eq 0 ]; then
        echo "  ✓ $1"
    else
        echo "  ✗ Error: $1"
        exit 1
    fi
}

# Verificar que estamos en el directorio correcto
if [ ! -f "./rc.local" ] || [ ! -f "./nao-launcher.service" ]; then
    echo "Error: No se encuentran los archivos necesarios en el directorio actual"
    echo "Este script debe ejecutarse desde /data/home/nao/"
    exit 1
fi

echo "Archivos encontrados correctamente"
echo "Iniciando escalada de privilegios..."
echo

# Ejecutar comandos con su (el usuario debe ingresar la contraseña de root)
su -c '
    # Crear directorios necesarios
    mkdir -p /data/etc
    mkdir -p /data/etc/systemd/system
    
    # Copiar rc.local
    cp /data/home/nao/rc.local /data/etc/rc.local
    chmod +x /data/etc/rc.local
    
    # Copiar servicio systemd
    cp /data/home/nao/nao-launcher.service /data/etc/systemd/system/nao-launcher.service
    chmod 644 /data/etc/systemd/system/nao-launcher.service
    
    # Habilitar el servicio (se iniciará en el próximo boot)
    systemctl enable nao-launcher.service
    
    echo "=== Instalación de archivos del sistema completada ==="
    echo "✓ rc.local instalado en /data/etc/rc.local"
    echo "✓ nao-launcher.service instalado en /data/etc/systemd/system/"
    echo "✓ Servicio nao-launcher habilitado para inicio automático"
'

# Verificar si la escalada fue exitosa
if [ $? -eq 0 ]; then
    echo
    echo "=== Escalada de privilegios completada exitosamente ==="
    echo "Los archivos del sistema han sido instalados correctamente"
else
    echo
    echo "=== Error en la escalada de privilegios ==="
    echo "La instalación de archivos del sistema falló"
    echo "Verifique la contraseña de root e intente nuevamente"
    exit 1
fi
