# install.ps1 - Script de instalación para NAO desde Windows
# Uso: .\install.ps1 -NaoIP "192.168.1.100"

param(
    [Parameter(Mandatory=$true)]
    [string]$NaoIP,
    
    [string]$NaoUser = "nao",
    
    [string]$NaoPass = "nao",
    
    [switch]$Clean
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  NAO Control - Instalación desde Windows"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Robot IP: $NaoIP"
Write-Host ""

# Obtener ruta base del script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NaoDir = Split-Path -Parent $ScriptDir

# Estructura de archivos a copiar
$FilesToCopy = @{
    # Runtime scripts
    "$NaoDir\scripts\runtime\control_server.py" = "/home/nao/scripts/runtime/"
    "$NaoDir\scripts\runtime\launcher.py" = "/home/nao/scripts/runtime/"
    "$NaoDir\scripts\runtime\logger.py" = "/home/nao/scripts/runtime/"
    "$NaoDir\scripts\runtime\data_logger.py" = "/home/nao/scripts/runtime/"
    "$NaoDir\scripts\runtime\record_system.py" = "/home/nao/scripts/runtime/"
    "$NaoDir\scripts\runtime\video_stream.py" = "/home/nao/scripts/runtime/"
    
    # Modular control server
    "$NaoDir\scripts\runtime\control_server\" = "/home/nao/scripts/runtime/"
    
    # Models
    "$NaoDir\models\" = "/home/nao/models/"
}

# Directorios a crear en el robot
$RemoteDirs = @(
    "/home/nao/scripts/runtime/control_server/commands",
    "/home/nao/scripts/runtime/control_server/facades",
    "/home/nao/scripts/runtime/control_server/strategies",
    "/home/nao/scripts/runtime/control_server/libs",
    "/home/nao/models/models_npz_automl",
    "/home/nao/logs",
    "/home/nao/Webs"
)

# Verificar que existe pscp (PuTTY) o usar scp si está disponible
$ScpCommand = $null
if (Get-Command pscp -ErrorAction SilentlyContinue) {
    $ScpCommand = "pscp"
} elseif (Get-Command scp -ErrorAction SilentlyContinue) {
    $ScpCommand = "scp"
} else {
    Write-Host "ERROR: Se requiere 'pscp' (PuTTY) o 'scp' (OpenSSH)" -ForegroundColor Red
    Write-Host "Instalar OpenSSH: Settings > Apps > Optional Features > OpenSSH Client"
    exit 1
}

Write-Host "Usando: $ScpCommand" -ForegroundColor Green

# Función para ejecutar comando SSH
function Invoke-SSHCommand {
    param([string]$Command)
    
    if (Get-Command plink -ErrorAction SilentlyContinue) {
        # Usar PuTTY plink
        $result = & plink -ssh -pw $NaoPass "$NaoUser@$NaoIP" $Command 2>&1
    } else {
        # Usar ssh nativo de Windows
        $result = & ssh -o StrictHostKeyChecking=no "$NaoUser@$NaoIP" $Command 2>&1
    }
    return $result
}

# Función para copiar archivos
function Copy-ToNao {
    param(
        [string]$LocalPath,
        [string]$RemotePath
    )
    
    if ($ScpCommand -eq "pscp") {
        & pscp -pw $NaoPass -r $LocalPath "${NaoUser}@${NaoIP}:${RemotePath}" 2>&1 | Out-Null
    } else {
        & scp -o StrictHostKeyChecking=no -r $LocalPath "${NaoUser}@${NaoIP}:${RemotePath}" 2>&1 | Out-Null
    }
}

try {
    # Paso 1: Crear directorios remotos
    Write-Host "`n1. Creando estructura de directorios..." -ForegroundColor Yellow
    foreach ($dir in $RemoteDirs) {
        Write-Host "   Creando: $dir"
        Invoke-SSHCommand "mkdir -p $dir" | Out-Null
    }
    Write-Host "   ✓ Directorios creados" -ForegroundColor Green
    
    # Paso 2: Limpiar si se especifica
    if ($Clean) {
        Write-Host "`n2. Limpiando instalación previa..." -ForegroundColor Yellow
        Invoke-SSHCommand "rm -rf /home/nao/scripts/runtime/control_server/*" | Out-Null
        Write-Host "   ✓ Instalación limpiada" -ForegroundColor Green
    }
    
    # Paso 3: Copiar archivos
    Write-Host "`n3. Copiando archivos..." -ForegroundColor Yellow
    foreach ($local in $FilesToCopy.Keys) {
        if (Test-Path $local) {
            $remote = $FilesToCopy[$local]
            $name = Split-Path -Leaf $local
            Write-Host "   Copiando: $name -> $remote"
            Copy-ToNao -LocalPath $local -RemotePath $remote
        } else {
            Write-Host "   ⚠ No existe: $local" -ForegroundColor Yellow
        }
    }
    Write-Host "   ✓ Archivos copiados" -ForegroundColor Green
    
    # Paso 4: Configurar permisos
    Write-Host "`n4. Configurando permisos..." -ForegroundColor Yellow
    Invoke-SSHCommand "chmod +x /home/nao/scripts/runtime/*.py" | Out-Null
    Invoke-SSHCommand "chmod +x /home/nao/scripts/runtime/control_server/server.py" | Out-Null
    Write-Host "   ✓ Permisos configurados" -ForegroundColor Green
    
    # Paso 5: Verificar
    Write-Host "`n5. Verificando instalación..." -ForegroundColor Yellow
    $files = Invoke-SSHCommand "ls /home/nao/scripts/runtime/control_server/"
    Write-Host "   Archivos instalados:"
    $files | ForEach-Object { Write-Host "     - $_" }
    Write-Host "   ✓ Verificación completada" -ForegroundColor Green
    
    # Resumen final
    Write-Host "`n==========================================" -ForegroundColor Cyan
    Write-Host "  ✓ INSTALACIÓN COMPLETADA" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Para iniciar el servidor:" -ForegroundColor White
    Write-Host "  ssh nao@$NaoIP 'python /home/nao/scripts/runtime/control_server.py'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "O el servidor modular:" -ForegroundColor White
    Write-Host "  ssh nao@$NaoIP 'python /home/nao/scripts/runtime/control_server/server.py'" -ForegroundColor Gray
    
} catch {
    Write-Host "`nERROR: $_" -ForegroundColor Red
    exit 1
}
