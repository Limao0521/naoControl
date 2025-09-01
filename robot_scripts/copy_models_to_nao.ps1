# copy_models_to_nao.ps1 - Script para copiar modelos al NAO (PowerShell)

param(
    [string]$NAO_IP = "192.168.1.100",
    [switch]$Help
)

if ($Help) {
    Write-Host "Uso: .\copy_models_to_nao.ps1 [-NAO_IP <IP>]" -ForegroundColor Green
    Write-Host ""
    Write-Host "Copia modelos LightGBM al NAO y los prueba" -ForegroundColor White
    Write-Host ""
    Write-Host "Ejemplo:" -ForegroundColor Yellow
    Write-Host "  .\copy_models_to_nao.ps1 -NAO_IP 192.168.1.100" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

$NAO_USER = "nao"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==============================================" -ForegroundColor Green
Write-Host "COPIADOR DE MODELOS LIGHTGBM AL NAO" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host "NAO IP: $NAO_IP" -ForegroundColor Yellow
Write-Host "Directorio local: $SCRIPT_DIR" -ForegroundColor Yellow
Write-Host ""

function Test-NAOConnection {
    Write-Host "[CHECK] Verificando conexión..." -ForegroundColor Blue
    
    try {
        $result = ssh -o ConnectTimeout=5 -o BatchMode=yes "$NAO_USER@$NAO_IP" 'echo "OK"' 2>$null
        if ($result -eq "OK") {
            Write-Host "[OK] Conexión SSH establecida" -ForegroundColor Green
            return $true
        }
        else {
            Write-Host "[ERROR] No se puede conectar al NAO" -ForegroundColor Red
            Write-Host "Verifica:" -ForegroundColor Yellow
            Write-Host "  - IP: $NAO_IP" -ForegroundColor Yellow
            Write-Host "  - NAO encendido" -ForegroundColor Yellow
            Write-Host "  - Red conectada" -ForegroundColor Yellow
            return $false
        }
    }
    catch {
        Write-Host "[ERROR] Error de conexión: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function Find-Models {
    Write-Host "[SEARCH] Buscando modelos LightGBM..." -ForegroundColor Blue
    
    # Posibles ubicaciones de modelos
    $searchPaths = @(
        (Join-Path (Split-Path $SCRIPT_DIR -Parent) "models_npz_automl"),
        (Join-Path $SCRIPT_DIR "models_npz_automl"),
        (Join-Path $SCRIPT_DIR "..\models_npz_automl")
    )
    
    foreach ($path in $searchPaths) {
        if (Test-Path $path) {
            Write-Host "[FOUND] Modelos encontrados en: $path" -ForegroundColor Green
            
            # Verificar archivos requeridos
            $requiredFiles = @(
                "feature_scaler.npz",
                "lightgbm_model_StepHeight.npz",
                "lightgbm_model_MaxStepX.npz",
                "lightgbm_model_MaxStepY.npz",
                "lightgbm_model_MaxStepTheta.npz",
                "lightgbm_model_Frequency.npz"
            )
            
            $missingFiles = 0
            Write-Host "[CHECK] Verificando archivos requeridos..." -ForegroundColor Blue
            
            foreach ($file in $requiredFiles) {
                $filePath = Join-Path $path $file
                if (Test-Path $filePath) {
                    Write-Host "  ✓ $file" -ForegroundColor Green
                }
                else {
                    Write-Host "  ✗ $file (FALTA)" -ForegroundColor Red
                    $missingFiles++
                }
            }
            
            if ($missingFiles -eq 0) {
                Write-Host "[OK] Todos los archivos requeridos están presentes" -ForegroundColor Green
                return $path
            }
            else {
                Write-Host "[WARN] Faltan $missingFiles archivos en $path" -ForegroundColor Yellow
            }
        }
    }
    
    Write-Host "[ERROR] No se encontraron modelos LightGBM completos" -ForegroundColor Red
    Write-Host ""
    Write-Host "Buscar modelos en estas ubicaciones:" -ForegroundColor Yellow
    foreach ($path in $searchPaths) {
        Write-Host "  - $path" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "Archivos requeridos:" -ForegroundColor Yellow
    Write-Host "  - feature_scaler.npz" -ForegroundColor Gray
    Write-Host "  - lightgbm_model_*.npz (5 archivos)" -ForegroundColor Gray
    
    return $null
}

function Copy-ModelsToNAO {
    param([string]$ModelsPath)
    
    Write-Host "[COPY] Copiando modelos al NAO..." -ForegroundColor Blue
    
    # Crear directorio en el NAO
    ssh "$NAO_USER@$NAO_IP" "mkdir -p /home/nao/models_npz_automl"
    
    # Copiar todos los archivos .npz
    Write-Host "  Copiando archivos desde: $ModelsPath" -ForegroundColor Gray
    scp "$ModelsPath\*.npz" "$NAO_USER@$NAO_IP`:/home/nao/models_npz_automl/"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] Modelos copiados exitosamente" -ForegroundColor Green
        
        # Verificar en el NAO
        Write-Host "[VERIFY] Verificando archivos en el NAO..." -ForegroundColor Blue
        ssh "$NAO_USER@$NAO_IP" "ls -la /home/nao/models_npz_automl/*.npz"
        
        return $true
    }
    else {
        Write-Host "[ERROR] Error copiando modelos" -ForegroundColor Red
        return $false
    }
}

function Test-ModelsOnNAO {
    Write-Host "[TEST] Probando modelos en el NAO..." -ForegroundColor Blue
    
    $testScript = @"
cd /home/nao/scripts
python2 -c "
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
"
"@
    
    ssh "$NAO_USER@$NAO_IP" $testScript
}

function Show-Instructions {
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host "COPIA COMPLETADA" -ForegroundColor Green
    Write-Host "==============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Ahora puedes probar el adaptive walk:" -ForegroundColor White
    Write-Host ""
    Write-Host "1. Conectar al NAO:" -ForegroundColor Cyan
    Write-Host "   ssh $NAO_USER@$NAO_IP" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Ejecutar adaptive walk:" -ForegroundColor Cyan
    Write-Host "   cd /home/nao/scripts" -ForegroundColor Gray
    Write-Host "   python2 adaptive_walk_lightgbm_nao.py" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. O usar el launcher:" -ForegroundColor Cyan
    Write-Host "   python2 launcher.py" -ForegroundColor Gray
    Write-Host ""
}

# Función principal
function Main {
    # Verificar conexión
    if (!(Test-NAOConnection)) {
        exit 1
    }
    
    # Buscar modelos
    $modelsPath = Find-Models
    if (-not $modelsPath) {
        exit 1
    }
    
    # Copiar modelos
    if (!(Copy-ModelsToNAO -ModelsPath $modelsPath)) {
        exit 1
    }
    
    # Probar modelos
    Test-ModelsOnNAO
    
    # Mostrar instrucciones
    Show-Instructions
}

# Ejecutar función principal
Main
