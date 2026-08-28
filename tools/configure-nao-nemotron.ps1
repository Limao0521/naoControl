[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F:.]+$')]
    [string]$NaoIp,
    [string]$NaoUser = 'nao',
    [string]$EnvFile = ''
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $env:LOCALAPPDATA 'naoControlGatewayHost\.env'
}

$apiKey = ''
if (Test-Path -LiteralPath $EnvFile) {
    foreach ($line in [System.IO.File]::ReadAllLines($EnvFile)) {
        if ($line -match '^\s*NVIDIA_API_KEY\s*=\s*(.+?)\s*$') {
            $apiKey = $Matches[1].Trim('"').Trim("'")
            break
        }
    }
}

$secureValue = $null
$secretPointer = [IntPtr]::Zero
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    $secureValue = Read-Host 'Pega la NVIDIA API key (no se mostrará)' -AsSecureString
    $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
}

if ($apiKey -notmatch '^[A-Za-z0-9._-]{20,1024}$') {
    if ($secretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    }
    throw 'La NVIDIA API key no tiene un formato válido.'
}

$temporary = [System.IO.Path]::GetTempFileName()
try {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($temporary, $apiKey, $utf8)
    Write-Host '==> Guardando la credencial de Nemotron dentro del NAO'
    & scp.exe $temporary "${NaoUser}@${NaoIp}:/tmp/naoControl-nvidia-api-key"
    if ($LASTEXITCODE -ne 0) { throw 'No fue posible copiar la credencial al NAO.' }
    & ssh.exe "${NaoUser}@${NaoIp}" "umask 077 && mkdir -p /home/nao/naoControl/config && mv /tmp/naoControl-nvidia-api-key /home/nao/naoControl/config/nvidia_api_key && chmod 600 /home/nao/naoControl/config/nvidia_api_key && test -s /home/nao/naoControl/config/nvidia_api_key"
    if ($LASTEXITCODE -ne 0) {
        throw 'La credencial se copió, pero el NAO no pudo validarla localmente.'
    }
    Write-Host 'Nemotron quedó configurado en el NAO. No necesita el launcher del PC.'
}
finally {
    $apiKey = $null
    if ($secretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    }
    if (Test-Path -LiteralPath $temporary) {
        $length = (Get-Item -LiteralPath $temporary).Length
        if ($length -gt 0) {
            [System.IO.File]::WriteAllBytes($temporary, (New-Object byte[] $length))
        }
        Remove-Item -LiteralPath $temporary -Force
    }
}
