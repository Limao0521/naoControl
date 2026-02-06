#!/bin/bash
# install.sh - Script de instalación rápida para NAO
# Uso: ./install.sh <NAO_IP>

NAO_IP=${1:-"192.168.1.100"}
NAO_USER="nao"
NAO_PASS="nao"

echo "=========================================="
echo "  NAO Control - Instalación Rápida"
echo "=========================================="
echo ""
echo "Robot IP: $NAO_IP"
echo ""

# Verificar sshpass
if ! command -v sshpass &> /dev/null; then
    echo "ERROR: sshpass no está instalado"
    echo "Instalar con: sudo apt-get install sshpass"
    exit 1
fi

# Función para ejecutar SSH
ssh_cmd() {
    sshpass -p "$NAO_PASS" ssh -o StrictHostKeyChecking=no "$NAO_USER@$NAO_IP" "$1"
}

# Función para SCP
scp_cmd() {
    sshpass -p "$NAO_PASS" scp -o StrictHostKeyChecking=no -r "$1" "$NAO_USER@$NAO_IP:$2"
}

echo "1. Creando estructura de directorios..."
ssh_cmd "mkdir -p /home/nao/scripts/runtime/control_server/{commands,facades,strategies,libs}"
ssh_cmd "mkdir -p /home/nao/models/models_npz_automl"
ssh_cmd "mkdir -p /home/nao/logs"
ssh_cmd "mkdir -p /home/nao/Webs"

echo "2. Copiando archivos de runtime..."
scp_cmd "../scripts/runtime/*.py" "/home/nao/scripts/runtime/"

echo "3. Copiando módulo control_server..."
scp_cmd "../scripts/runtime/control_server/" "/home/nao/scripts/runtime/"

echo "4. Copiando modelos..."
scp_cmd "../models/*" "/home/nao/models/"

echo "5. Configurando permisos..."
ssh_cmd "chmod +x /home/nao/scripts/runtime/*.py"
ssh_cmd "chmod +x /home/nao/scripts/runtime/control_server/server.py"

echo "6. Verificando instalación..."
ssh_cmd "ls -la /home/nao/scripts/runtime/control_server/"

echo ""
echo "=========================================="
echo "  ✓ Instalación completada"
echo "=========================================="
echo ""
echo "Para iniciar el servidor:"
echo "  ssh nao@$NAO_IP 'python /home/nao/scripts/runtime/control_server.py'"
echo ""
echo "O el servidor modular:"
echo "  ssh nao@$NAO_IP 'python /home/nao/scripts/runtime/control_server/server.py'"
