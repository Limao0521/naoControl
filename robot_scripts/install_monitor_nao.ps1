# Script PowerShell para instalar y ejecutar el monitor de parámetros en el NAO
# Uso: .\install_monitor_nao.ps1 IP_DEL_NAO

param(
    [Parameter(Mandatory=$true)]
    [string]$NAO_IP
)

Write-Host "🚀 Instalando monitor de parámetros en NAO $NAO_IP" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green

# 1. Crear directorio en el NAO
Write-Host "📁 Creando directorio /home/nao/scripts..." -ForegroundColor Yellow
ssh nao@$NAO_IP "mkdir -p /home/nao/scripts"

# 2. Copiar el monitor
Write-Host "📋 Copiando monitor_live_gait_params_local.py..." -ForegroundColor Yellow
scp monitor_live_gait_params_local.py nao@${NAO_IP}:/home/nao/scripts/

# 3. Hacer ejecutable
Write-Host "🔧 Configurando permisos..." -ForegroundColor Yellow
ssh nao@$NAO_IP "chmod +x /home/nao/scripts/monitor_live_gait_params_local.py"

# 4. Verificar instalación
Write-Host "✅ Verificando instalación..." -ForegroundColor Yellow
$result = ssh nao@$NAO_IP "test -f /home/nao/scripts/monitor_live_gait_params_local.py && echo 'EXISTS'"

if ($result -eq "EXISTS") {
    Write-Host "✅ Monitor instalado correctamente" -ForegroundColor Green
} else {
    Write-Host "❌ Error en la instalación" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎯 INSTALACIÓN COMPLETADA" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green
Write-Host ""
Write-Host "Para ejecutar el monitor:" -ForegroundColor Cyan
Write-Host "1. ssh nao@$NAO_IP" -ForegroundColor White
Write-Host "2. cd /home/nao/scripts" -ForegroundColor White
Write-Host "3. python monitor_live_gait_params_local.py" -ForegroundColor White
Write-Host ""
Write-Host "Para obtener el CSV generado:" -ForegroundColor Cyan
Write-Host "scp nao@${NAO_IP}:/home/nao/scripts/gait_params_log.csv ./datos_nao.csv" -ForegroundColor White
Write-Host ""

$response = Read-Host "¿Quieres ejecutar el monitor ahora? (y/n)"

if ($response -eq "y" -or $response -eq "Y") {
    Write-Host "🔄 Ejecutando monitor en el NAO..." -ForegroundColor Green
    Write-Host "⚠️  Presiona Ctrl+C para detener" -ForegroundColor Yellow
    ssh nao@$NAO_IP "cd /home/nao/scripts && python monitor_live_gait_params_local.py"
}
