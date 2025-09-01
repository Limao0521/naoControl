#!/bin/bash
# install_nao_adaptive_walk.sh - Script de instalación para NAO

# Configuración
NAO_IP="192.168.1.100"  # Cambiar por la IP de tu NAO
NAO_USER="nao"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "====================================================="
echo "INSTALADOR NAO ADAPTIVE WALK - LIGHTGBM"
echo "====================================================="
echo "NAO IP: $NAO_IP"
echo "Script dir: $SCRIPT_DIR"
echo ""

# Función para verificar conexión SSH
check_ssh_connection() {
    echo "[CHECK] Verificando conexión SSH..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes $NAO_USER@$NAO_IP 'echo "SSH OK"' >/dev/null 2>&1; then
        echo "[OK] Conexión SSH establecida"
        return 0
    else
        echo "[ERROR] No se puede conectar por SSH al NAO"
        echo "Verifica:"
        echo "  - IP del NAO: $NAO_IP"
        echo "  - NAO encendido y conectado a la red"
        echo "  - Autenticación SSH configurada"
        return 1
    fi
}

# Función para crear directorios en el NAO
create_nao_directories() {
    echo "[SETUP] Creando directorios en el NAO..."
    ssh $NAO_USER@$NAO_IP "
        mkdir -p /home/nao/scripts
        mkdir -p /home/nao/models_npz_automl
        mkdir -p /home/nao/logs
        mkdir -p /home/nao/Webs/ControllerWebServer
        echo 'Directorios creados'
    "
}

# Función para copiar archivos principales
copy_main_scripts() {
    echo "[COPY] Copiando scripts principales..."
    
    local files=(
        "adaptive_walk_lightgbm_nao.py"
        "control_server.py"
        "launcher.py"
        "data_logger.py"
        "logger.py"
        "test_python2_compatibility.py"
    )
    
    for file in "${files[@]}"; do
        if [ -f "$SCRIPT_DIR/$file" ]; then
            echo "  Copiando $file..."
            scp "$SCRIPT_DIR/$file" $NAO_USER@$NAO_IP:/home/nao/scripts/
        else
            echo "  [WARN] Archivo no encontrado: $file"
        fi
    done
}

# Función para copiar modelos
copy_models() {
    echo "[COPY] Copiando modelos LightGBM..."
    
    local models_dir="../models_npz_automl"
    if [ -d "$SCRIPT_DIR/$models_dir" ]; then
        echo "  Copiando modelos desde $models_dir..."
        scp -r "$SCRIPT_DIR/$models_dir"/* $NAO_USER@$NAO_IP:/home/nao/models_npz_automl/
    else
        echo "  [WARN] Directorio de modelos no encontrado: $models_dir"
        echo "  [INFO] Buscando en directorio actual..."
        if [ -d "$SCRIPT_DIR/models_npz_automl" ]; then
            scp -r "$SCRIPT_DIR/models_npz_automl"/* $NAO_USER@$NAO_IP:/home/nao/models_npz_automl/
        else
            echo "  [ERROR] No se encontraron modelos LightGBM"
        fi
    fi
}

# Función para copiar interfaz web
copy_web_interface() {
    echo "[COPY] Copiando interfaz web..."
    
    local web_dir="../ControllerWebServer"
    if [ -d "$SCRIPT_DIR/$web_dir" ]; then
        echo "  Copiando interfaz web..."
        scp -r "$SCRIPT_DIR/$web_dir"/* $NAO_USER@$NAO_IP:/home/nao/Webs/ControllerWebServer/
    else
        echo "  [WARN] Interfaz web no encontrada: $web_dir"
    fi
}

# Función para configurar permisos
set_permissions() {
    echo "[SETUP] Configurando permisos..."
    ssh $NAO_USER@$NAO_IP "
        chmod +x /home/nao/scripts/*.py
        chmod 644 /home/nao/models_npz_automl/*.npz 2>/dev/null || true
        echo 'Permisos configurados'
    "
}

# Función para realizar test básico
run_basic_test() {
    echo "[TEST] Ejecutando test de compatibilidad..."
    ssh $NAO_USER@$NAO_IP "
        cd /home/nao/scripts
        python2 test_python2_compatibility.py
    "
}

# Función para mostrar instrucciones post-instalación
show_post_install_instructions() {
    echo ""
    echo "====================================================="
    echo "INSTALACIÓN COMPLETADA"
    echo "====================================================="
    echo ""
    echo "Para usar el sistema:"
    echo ""
    echo "1. LAUNCHER AUTOMÁTICO (recomendado):"
    echo "   ssh $NAO_USER@$NAO_IP"
    echo "   cd /home/nao/scripts"
    echo "   python2 launcher.py"
    echo "   # Presiona cabeza del NAO 3+ segundos para alternar modos"
    echo ""
    echo "2. CONTROL SERVER MANUAL:"
    echo "   ssh $NAO_USER@$NAO_IP"
    echo "   cd /home/nao/scripts"
    echo "   python2 control_server.py"
    echo ""
    echo "3. ADAPTIVE WALK DIRECTO:"
    echo "   ssh $NAO_USER@$NAO_IP"
    echo "   cd /home/nao/scripts"
    echo "   python2 adaptive_walk_lightgbm_nao.py"
    echo ""
    echo "4. INTERFAZ WEB:"
    echo "   http://$NAO_IP:8000"
    echo ""
    echo "Archivos instalados en:"
    echo "  - Scripts: /home/nao/scripts/"
    echo "  - Modelos: /home/nao/models_npz_automl/"
    echo "  - Logs: /home/nao/logs/"
    echo "  - Web: /home/nao/Webs/ControllerWebServer/"
    echo ""
}

# Función principal
main() {
    # Verificar argumentos
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        echo "Uso: $0 [NAO_IP]"
        echo "Ejemplo: $0 192.168.1.100"
        exit 0
    fi
    
    # Sobrescribir IP si se proporciona
    if [ ! -z "$1" ]; then
        NAO_IP="$1"
        echo "Usando IP del NAO: $NAO_IP"
    fi
    
    # Ejecutar pasos de instalación
    if ! check_ssh_connection; then
        echo "Abortando instalación..."
        exit 1
    fi
    
    create_nao_directories
    copy_main_scripts
    copy_models
    copy_web_interface
    set_permissions
    run_basic_test
    show_post_install_instructions
    
    echo "[SUCCESS] ¡Instalación completada exitosamente!"
}

# Ejecutar función principal
main "$@"
