#!/bin/bash

# Script para instalar y ejecutar el monitor de parámetros en el NAO
# Uso: ./install_monitor_nao.sh IP_DEL_NAO

NAO_IP=$1

if [ -z "$NAO_IP" ]; then
    echo "❌ Error: Debes proporcionar la IP del NAO"
    echo "Uso: $0 <IP_DEL_NAO>"
    echo "Ejemplo: $0 192.168.1.100"
    exit 1
fi

echo "🚀 Instalando monitor de parámetros en NAO $NAO_IP"
echo "=================================================="

# 1. Crear directorio en el NAO
echo "📁 Creando directorio /home/nao/scripts..."
ssh nao@$NAO_IP "mkdir -p /home/nao/scripts"

# 2. Copiar el monitor
echo "📋 Copiando monitor_live_gait_params_local.py..."
scp monitor_live_gait_params_local.py nao@$NAO_IP:/home/nao/scripts/

# 3. Hacer ejecutable
echo "🔧 Configurando permisos..."
ssh nao@$NAO_IP "chmod +x /home/nao/scripts/monitor_live_gait_params_local.py"

# 4. Verificar instalación
echo "✅ Verificando instalación..."
if ssh nao@$NAO_IP "test -f /home/nao/scripts/monitor_live_gait_params_local.py"; then
    echo "✅ Monitor instalado correctamente"
else
    echo "❌ Error en la instalación"
    exit 1
fi

echo ""
echo "🎯 INSTALACIÓN COMPLETADA"
echo "========================"
echo ""
echo "Para ejecutar el monitor:"
echo "1. ssh nao@$NAO_IP"
echo "2. cd /home/nao/scripts"  
echo "3. python monitor_live_gait_params_local.py"
echo ""
echo "Para obtener el CSV generado:"
echo "scp nao@$NAO_IP:/home/nao/scripts/gait_params_log.csv ./datos_nao.csv"
echo ""
echo "¿Quieres ejecutar el monitor ahora? (y/n)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo "🔄 Ejecutando monitor en el NAO..."
    echo "⚠️  Presiona Ctrl+C para detener"
    ssh nao@$NAO_IP "cd /home/nao/scripts && python monitor_live_gait_params_local.py"
fi
