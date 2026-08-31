[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]{1,3}(\.[0-9]{1,3}){3}$')]
    [string]$NaoIp,
    [string]$NaoUser = 'nao',
    [string]$RepoRoot,
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA 'naoControlGatewayHost')
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'launcher-task-settings.ps1')

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot '..'
}

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw 'Ejecuta PowerShell como administrador para crear la regla de firewall local.'
}

$route = Test-NetConnection -ComputerName $NaoIp -Port 22 -InformationLevel Detailed
if (-not $route.TcpTestSucceeded) {
    throw "El NAO $NaoIp no acepta SSH desde este PC."
}
$pcAddress = [string]$route.SourceAddress

$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$package = Join-Path $repo 'pc_gateway'
$sourceEnv = Join-Path $repo '.env'
$exampleEnv = Join-Path $repo '.env.example'
$venv = Join-Path $RuntimeRoot '.venv311'
$python = Join-Path $venv 'Scripts\python.exe'
$runtimeEnv = Join-Path $RuntimeRoot '.env'

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

if (-not (Test-Path -LiteralPath $python)) {
    Write-Step 'Creando entorno Python del lanzador'
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        & py -3.11 -m venv $venv
    } else {
        throw 'Para KWS instala Python 3.11 y asegúrate de que el comando py -3.11 esté disponible.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'No fue posible crear el entorno Python 3.11 requerido por KWS.' }
}

Write-Step 'Instalando lanzador, gateway y dependencias opcionales de palabra clave'
& $python -m pip install --disable-pip-version-check "$package[kws]"
if ($LASTEXITCODE -ne 0) { throw 'La instalación del gateway falló.' }

$needsEnvConfiguration = $false
if (-not (Test-Path -LiteralPath $runtimeEnv)) {
    if (Test-Path -LiteralPath $sourceEnv) {
        Copy-Item -LiteralPath $sourceEnv -Destination $runtimeEnv
    } else {
        Copy-Item -LiteralPath $exampleEnv -Destination $runtimeEnv
        $needsEnvConfiguration = $true
    }
}

Write-Step 'Sincronizando el secreto HMAC directamente desde el NAO'
$secretTemp = Join-Path ([System.IO.Path]::GetTempPath()) (
    'nao-gateway-secret-' + [guid]::NewGuid().ToString('N')
)
try {
    $scpArguments = @(
        '-q',
        '-o', 'StrictHostKeyChecking=yes',
        "${NaoUser}@${NaoIp}:/home/nao/naoControl/config/robot_gateway.secret",
        $secretTemp
    )
    & scp.exe @scpArguments
    if ($LASTEXITCODE -ne 0) { throw 'No fue posible obtener el secreto del NAO.' }
    $robotSecret = [System.IO.File]::ReadAllText($secretTemp).Trim()
    if ($robotSecret.Length -lt 32) { throw 'El secreto del NAO no es válido.' }

    $lines = [System.Collections.Generic.List[string]]::new()
    $secretWritten = $false
    foreach ($line in [System.IO.File]::ReadAllLines($runtimeEnv)) {
        if ($line -match '^NAO_GATEWAY_SECRET=') {
            $lines.Add('NAO_GATEWAY_SECRET=' + $robotSecret)
            $secretWritten = $true
        } else {
            $lines.Add($line)
        }
    }
    if (-not $secretWritten) { $lines.Add('NAO_GATEWAY_SECRET=' + $robotSecret) }
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllLines($runtimeEnv, $lines, $utf8NoBom)
} finally {
    if (Test-Path -LiteralPath $secretTemp) {
        Remove-Item -LiteralPath $secretTemp -Force
    }
}

$apiConfigured = [System.IO.File]::ReadAllLines($runtimeEnv) |
    Where-Object { $_ -match '^NVIDIA_API_KEY=.+$' }
if ($needsEnvConfiguration -or -not $apiConfigured) {
    Start-Process notepad.exe -ArgumentList $runtimeEnv
    throw "Completa NVIDIA_API_KEY en $runtimeEnv y vuelve a ejecutar este comando."
}

$taskName = 'NaoControlNemotronLauncher'
$arguments = @(
    '-u', '-m', 'nao_gateway.launcher_service',
    '--env-file', $runtimeEnv,
    '--runtime-root', $RuntimeRoot,
    '--host', '0.0.0.0',
    '--port', '6676'
)
$quotedArguments = ($arguments | ForEach-Object {
    if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
}) -join ' '
Write-Step 'Registrando inicio automático del lanzador'
$taskAction = New-ScheduledTaskAction -Execute $python -Argument $quotedArguments
$taskTrigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
$principalParameters = @{
    UserId    = $identity.Name
    LogonType = 'Interactive'
    RunLevel  = 'Limited'
}
$taskPrincipal = New-ScheduledTaskPrincipal @principalParameters
$taskSettings = New-NaoLauncherTaskSettings
$taskParameters = @{
    TaskName  = $taskName
    Action    = $taskAction
    Trigger   = $taskTrigger
    Principal = $taskPrincipal
    Settings  = $taskSettings
    Force     = $true
}
Register-ScheduledTask @taskParameters | Out-Null

$existingRule = Get-NetFirewallRule -DisplayName $taskName -ErrorAction SilentlyContinue
if ($existingRule) {
    $existingRule | Remove-NetFirewallRule
}
$firewallParameters = @{
    DisplayName   = $taskName
    Direction     = 'Inbound'
    Action        = 'Allow'
    Protocol      = 'TCP'
    LocalPort     = 6676
    LocalAddress  = $pcAddress
    RemoteAddress = $NaoIp
    Profile       = 'Any'
}
New-NetFirewallRule @firewallParameters | Out-Null

Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like '*nao_gateway.launcher_service*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Step 'Iniciando lanzador autenticado en segundo plano'
Start-ScheduledTask -TaskName $taskName

$ready = $false
for ($attempt = 0; $attempt -lt 10; $attempt++) {
    $listener = Get-NetTCPConnection -LocalPort 6676 -State Listen -ErrorAction SilentlyContinue
    if ($listener) { $ready = $true; break }
    Start-Sleep -Milliseconds 300
}
if (-not $ready) {
    throw "El lanzador no abrió el puerto 6676. Revisa $RuntimeRoot\logs."
}

Write-Host 'Lanzador del PC listo. Configura la IP de este PC en el menú Red del NAO.' -ForegroundColor Green
Write-Host ("IP del PC para el panel Red: " + $pcAddress) -ForegroundColor Green
