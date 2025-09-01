#!/bin/bash
# copy_models_to_nao.sh - Script para copiar modelos al NAO

# Configuración
NAO_IP="${1:-192.168.1.100}"  # IP del NAO (usar primer argumento o default)
NAO_USER="nao"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================="
echo "COPIADOR DE MODELOS LIGHTGBM AL NAO"
echo "=============================================="
echo "NAO IP: $NAO_IP"
echo "Directorio local: $SCRIPT_DIR"
echo ""

# Función para verificar conexión SSH
check_connection() {
    echo "[CHECK] Verificando conexión..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes $NAO_USER@$NAO_IP 'echo "OK"' >/dev/null 2>&1; then
        echo "[OK] Conexión SSH establecida"
        return 0
    else
        echo "[ERROR] No se puede conectar al NAO"
        echo "Verifica:"
        echo "  - IP: $NAO_IP"
        echo "  - NAO encendido"
        echo "  - Red conectada"
        return 1
    fi
}

# Función para encontrar modelos
find_models() {
    echo "[SEARCH] Buscando modelos LightGBM..."
    
    # Posibles ubicaciones de modelos
    local search_paths=(
        "$SCRIPT_DIR/../models_npz_automl"
        "$SCRIPT_DIR/models_npz_automl"
        "$SCRIPT_DIR/../models_npz_automl"
        "$(dirname "$SCRIPT_DIR")/models_npz_automl"
    )
    
    for path in "${search_paths[@]}"; do
        if [ -d "$path" ]; then
            echo "[FOUND] Modelos encontrados en: $path"
            
            # Verificar archivos requeridos
            local required_files=(
                "feature_scaler.npz"
                "lightgbm_model_StepHeight.npz"
                "lightgbm_model_MaxStepX.npz"
                "lightgbm_model_MaxStepY.npz"
                "lightgbm_model_MaxStepTheta.npz"
                "lightgbm_model_Frequency.npz"
            )
            
            local missing_files=0
            echo "[CHECK] Verificando archivos requeridos..."
            
            for file in "${required_files[@]}"; do
                if [ -f "$path/$file" ]; then
                    echo "  ✓ $file"
                else
                    echo "  ✗ $file (FALTA)"
                    missing_files=$((missing_files + 1))
                fi
            done
            
            if [ $missing_files -eq 0 ]; then
                echo "[OK] Todos los archivos requeridos están presentes"
                MODELS_PATH="$path"
                return 0
            else
                echo "[WARN] Faltan $missing_files archivos en $path"
            fi
        fi
    done
    
    echo "[ERROR] No se encontraron modelos LightGBM completos"
    echo ""
    echo "Buscar modelos en estas ubicaciones:"
    for path in "${search_paths[@]}"; do
        echo "  - $path"
    done
    echo ""
    echo "Archivos requeridos:"
    echo "  - feature_scaler.npz"
    echo "  - lightgbm_model_*.npz (5 archivos)"
    
    return 1
}

# Función para copiar modelos
copy_models() {
    echo "[COPY] Copiando modelos al NAO..."
    
    # Crear directorio en el NAO
    ssh $NAO_USER@$NAO_IP "mkdir -p /home/nao/models_npz_automl"
    
    # Copiar todos los archivos .npz
    echo "  Copiando archivos desde: $MODELS_PATH"
    scp "$MODELS_PATH"/*.npz "$NAO_USER@$NAO_IP:/home/nao/models_npz_automl/"
    
    if [ $? -eq 0 ]; then
        echo "[SUCCESS] Modelos copiados exitosamente"
        
        # Verificar en el NAO
        echo "[VERIFY] Verificando archivos en el NAO..."
        ssh $NAO_USER@$NAO_IP "ls -la /home/nao/models_npz_automl/*.npz"
        
        return 0
    else
        echo "[ERROR] Error copiando modelos"
        return 1
    fi
}

# Función para probar los modelos
test_models() {
    echo "[TEST] Probando modelos en el NAO..."
    
    ssh $NAO_USER@$NAO_IP "
        cd /home/nao/scripts
        python2 -c \"
from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
try:
    walker = AdaptiveWalkLightGBM('models_npz_automl')
    if walker.models:
        print('[SUCCESS] Modelos cargados correctamente: {} modelos'.format(len(walker.models)))
        params = walker.predict_gait_parameters()
        print('[TEST] Predicción de prueba: {}'.format(params))
    else:
        print('[ERROR] No se pudieron cargar los modelos')
except Exception as e:
    print('[ERROR] Error probando modelos: {}'.format(e))
\"
    "
}

# Función principal
main() {
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        echo "Uso: $0 [NAO_IP]"
        echo ""
        echo "Copia modelos LightGBM al NAO y los prueba"
        echo ""
        echo "Ejemplo:"
        echo "  $0 192.168.1.100"
        echo ""
        exit 0
    fi
    
    # Verificar conexión
    if ! check_connection; then
        exit 1
    fi
    
    # Buscar modelos
    if ! find_models; then
        exit 1
    fi
    
    # Copiar modelos
    if ! copy_models; then
        exit 1
    fi
    
    # Probar modelos
    test_models
    
    echo ""
    echo "=============================================="
    echo "COPIA COMPLETADA"
    echo "=============================================="
    echo ""
    echo "Ahora puedes probar el adaptive walk:"
    echo ""
    echo "1. Conectar al NAO:"
    echo "   ssh $NAO_USER@$NAO_IP"
    echo ""
    echo "2. Ejecutar adaptive walk:"
    echo "   cd /home/nao/scripts"
    echo "   python2 adaptive_walk_lightgbm_nao.py"
    echo ""
    echo "3. O usar el launcher:"
    echo "   python2 launcher.py"
    echo ""
}

# Ejecutar función principal
main "$@"
