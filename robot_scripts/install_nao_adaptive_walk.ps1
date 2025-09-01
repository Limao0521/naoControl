# install_nao_adaptive_walk.ps1 - Script de instalación para NAO (Windows PowerShell)

param(
    [string]$NAO_IP = "192.168.1.100",
    [switch]$Help
)

if ($Help) {
    Write-Host "Uso: .\install_nao_adaptive_walk.ps1 [-NAO_IP <IP>]"
    Write-Host "Ejemplo: .\install_nao_adaptive_walk.ps1 -NAO_IP 192.168.1.100"
    exit 0
}

$NAO_USER = "nao"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=====================================================" -ForegroundColor Green
Write-Host "INSTALADOR NAO ADAPTIVE WALK - LIGHTGBM" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "NAO IP: $NAO_IP" -ForegroundColor Yellow
Write-Host "Script dir: $SCRIPT_DIR" -ForegroundColor Yellow
Write-Host ""

function Test-SSHConnection {
    Write-Host "[CHECK] Verificando conexión SSH..." -ForegroundColor Blue
    
    # Verificar si ssh está disponible
    try {
        $sshVersion = ssh -V 2>&1
        Write-Host "SSH disponible: $sshVersion" -ForegroundColor Green
    }
    catch {
        Write-Host "[ERROR] SSH no está disponible. Instala OpenSSH o usa PuTTY/SCP" -ForegroundColor Red
        return $false
    }
    
    # Test de conexión
    try {
        $result = ssh -o ConnectTimeout=5 -o BatchMode=yes "$NAO_USER@$NAO_IP" 'echo "SSH OK"' 2>$null
        if ($result -eq "SSH OK") {
            Write-Host "[OK] Conexión SSH establecida" -ForegroundColor Green
            return $true
        }
        else {
            Write-Host "[ERROR] No se puede conectar por SSH al NAO" -ForegroundColor Red
            Write-Host "Verifica:" -ForegroundColor Yellow
            Write-Host "  - IP del NAO: $NAO_IP" -ForegroundColor Yellow
            Write-Host "  - NAO encendido y conectado a la red" -ForegroundColor Yellow
            Write-Host "  - Autenticación SSH configurada" -ForegroundColor Yellow
            return $false
        }
    }
    catch {
        Write-Host "[ERROR] Error conectando por SSH: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

function New-NAODirectories {
    Write-Host "[SETUP] Creando directorios en el NAO..." -ForegroundColor Blue
    
    $commands = @(
        "mkdir -p /home/nao/scripts",
        "mkdir -p /home/nao/models_npz_automl", 
        "mkdir -p /home/nao/logs",
        "mkdir -p /home/nao/Webs/ControllerWebServer",
        "echo 'Directorios creados'"
    )
    
    $commandString = $commands -join "; "
    ssh "$NAO_USER@$NAO_IP" $commandString
}

function Copy-MainScripts {
    Write-Host "[COPY] Copiando scripts principales..." -ForegroundColor Blue
    
    $files = @(
        "adaptive_walk_lightgbm_nao.py",
        "control_server.py", 
        "launcher.py",
        "data_logger.py",
        "logger.py",
        "test_python2_compatibility.py"
    )
    
    foreach ($file in $files) {
        $filePath = Join-Path $SCRIPT_DIR $file
        if (Test-Path $filePath) {
            Write-Host "  Copiando $file..." -ForegroundColor Gray
            scp "$filePath" "$NAO_USER@$NAO_IP`:/home/nao/scripts/"
        }
        else {
            Write-Host "  [WARN] Archivo no encontrado: $file" -ForegroundColor Yellow
        }
    }
}

function Copy-Models {
    Write-Host "[COPY] Copiando modelos LightGBM..." -ForegroundColor Blue
    
    # Buscar directorio de modelos
    $modelsDir = $null
    $possiblePaths = @(
        (Join-Path (Split-Path $SCRIPT_DIR -Parent) "models_npz_automl"),
        (Join-Path $SCRIPT_DIR "models_npz_automl"),
        (Join-Path $SCRIPT_DIR "..\models_npz_automl")
    )
    
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $modelsDir = $path
            break
        }
    }
    
    if ($modelsDir) {
        Write-Host "  Copiando modelos desde $modelsDir..." -ForegroundColor Gray
        scp -r "$modelsDir\*" "$NAO_USER@$NAO_IP`:/home/nao/models_npz_automl/"
    }
    else {
        Write-Host "  [ERROR] No se encontraron modelos LightGBM" -ForegroundColor Red
        Write-Host "  Buscar en: $($possiblePaths -join ', ')" -ForegroundColor Yellow
    }
}

function Copy-WebInterface {
    Write-Host "[COPY] Copiando interfaz web..." -ForegroundColor Blue
    
    $webDir = Join-Path (Split-Path $SCRIPT_DIR -Parent) "ControllerWebServer"
    
    if (Test-Path $webDir) {
        Write-Host "  Copiando interfaz web..." -ForegroundColor Gray
        scp -r "$webDir\*" "$NAO_USER@$NAO_IP`:/home/nao/Webs/ControllerWebServer/"
    }
    else {
        Write-Host "  [WARN] Interfaz web no encontrada: $webDir" -ForegroundColor Yellow
    }
}

function Set-NAOPermissions {
    Write-Host "[SETUP] Configurando permisos..." -ForegroundColor Blue
    
    $commands = @(
        "chmod +x /home/nao/scripts/*.py",
        "chmod 644 /home/nao/models_npz_automl/*.npz 2>/dev/null || true",
        "echo 'Permisos configurados'"
    )
    
    $commandString = $commands -join "; "
    ssh "$NAO_USER@$NAO_IP" $commandString
}

function Start-BasicTest {
    Write-Host "[TEST] Ejecutando test de compatibilidad..." -ForegroundColor Blue
    
    ssh "$NAO_USER@$NAO_IP" "cd /home/nao/scripts; python2 test_python2_compatibility.py"
}

function Show-PostInstallInstructions {
    Write-Host ""
    Write-Host "=====================================================" -ForegroundColor Green
    Write-Host "INSTALACIÓN COMPLETADA" -ForegroundColor Green
    Write-Host "=====================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Para usar el sistema:" -ForegroundColor White
    Write-Host ""
    Write-Host "1. LAUNCHER AUTOMÁTICO (recomendado):" -ForegroundColor Cyan
    Write-Host "   ssh $NAO_USER@$NAO_IP" -ForegroundColor Gray
    Write-Host "   cd /home/nao/scripts" -ForegroundColor Gray
    Write-Host "   python2 launcher.py" -ForegroundColor Gray
    Write-Host "   # Presiona cabeza del NAO 3+ segundos para alternar modos" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "2. CONTROL SERVER MANUAL:" -ForegroundColor Cyan
    Write-Host "   ssh $NAO_USER@$NAO_IP" -ForegroundColor Gray
    Write-Host "   cd /home/nao/scripts" -ForegroundColor Gray
    Write-Host "   python2 control_server.py" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. ADAPTIVE WALK DIRECTO:" -ForegroundColor Cyan
    Write-Host "   ssh $NAO_USER@$NAO_IP" -ForegroundColor Gray
    Write-Host "   cd /home/nao/scripts" -ForegroundColor Gray
    Write-Host "   python2 adaptive_walk_lightgbm_nao.py" -ForegroundColor Gray
    Write-Host ""
    Write-Host "4. INTERFAZ WEB:" -ForegroundColor Cyan
    Write-Host "   http://$NAO_IP`:8000" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Archivos instalados en:" -ForegroundColor White
    Write-Host "  - Scripts: /home/nao/scripts/" -ForegroundColor Gray
    Write-Host "  - Modelos: /home/nao/models_npz_automl/" -ForegroundColor Gray  
    Write-Host "  - Logs: /home/nao/logs/" -ForegroundColor Gray
    Write-Host "  - Web: /home/nao/Webs/ControllerWebServer/" -ForegroundColor Gray
    Write-Host ""
}

# Función principal
function Main {
    if (!(Test-SSHConnection)) {
        Write-Host "Abortando instalación..." -ForegroundColor Red
        exit 1
    }
    
    New-NAODirectories
    Copy-MainScripts  
    Copy-Models
    Copy-WebInterface
    Set-NAOPermissions
    Start-BasicTest
    Show-PostInstallInstructions
    
    Write-Host "[SUCCESS] ¡Instalación completada exitosamente!" -ForegroundColor Green
}

# Ejecutar función principal
Main
