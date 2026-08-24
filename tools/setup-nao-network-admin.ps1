[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F:.]+$')]
    [string]$NaoIp,

    [ValidatePattern('^[A-Za-z_][A-Za-z0-9_-]{0,31}$')]
    [string]$User = 'nao',

    [string]$KeyPath = (Join-Path $env:USERPROFILE '.ssh\nao_control_ed25519'),
    [string]$EnvFile = '',
    [string]$SshCommand = 'ssh.exe',
    [string]$SshKeygenCommand = 'ssh-keygen.exe'
)

$ErrorActionPreference = 'Stop'
$scriptDirectory = Split-Path -Parent $PSCommandPath
if ([string]::IsNullOrWhiteSpace($scriptDirectory)) {
    $scriptDirectory = $PSScriptRoot
}
if ([string]::IsNullOrWhiteSpace($scriptDirectory)) {
    throw 'Unable to resolve the setup script directory.'
}
$repoRoot = (Resolve-Path (Join-Path $scriptDirectory '..')).Path
if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $repoRoot '.env'
}
$resolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
$resolvedEnvFile = [System.IO.Path]::GetFullPath($EnvFile)
$keyDirectory = Split-Path -Parent $resolvedKeyPath
$sshTarget = "$User@$NaoIp"

function Assert-CommandSucceeded([string]$Description) {
    if (-not $?) { throw "$Description failed." }
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "$Description failed (exit code $LASTEXITCODE)."
    }
}

function Set-EnvValue([string]$Path, [string]$Name, [string]$Value) {
    $lines = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $Path) {
        foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
            $lines.Add($line)
        }
    }
    $replacement = "$Name=$Value"
    $found = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^$([regex]::Escape($Name))=") {
            $lines[$index] = $replacement
            $found = $true
        }
    }
    if (-not $found) { $lines.Add($replacement) }
    [System.IO.File]::WriteAllLines(
        $Path,
        $lines,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Remove-EnvValue([string]$Path, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $remaining = [System.IO.File]::ReadAllLines($Path) | Where-Object {
        $_ -notmatch "^$([regex]::Escape($Name))="
    }
    [System.IO.File]::WriteAllLines(
        $Path,
        [string[]]$remaining,
        [System.Text.UTF8Encoding]::new($false)
    )
}

if (-not (Get-Command $SshCommand -ErrorAction SilentlyContinue)) {
    throw "Missing SSH command: $SshCommand"
}

if (-not (Test-Path -LiteralPath $resolvedKeyPath)) {
    if (-not (Get-Command $SshKeygenCommand -ErrorAction SilentlyContinue)) {
        throw "Missing SSH key generator: $SshKeygenCommand"
    }
    New-Item -ItemType Directory -Force -Path $keyDirectory | Out-Null
    # Windows PowerShell otherwise drops an empty native argument after -N.
    & $SshKeygenCommand -t ed25519 -f $resolvedKeyPath -N '""' -C 'naoControl-network-admin'
    Assert-CommandSucceeded 'SSH key generation'
}

$publicKeyPath = "$resolvedKeyPath.pub"
if (-not (Test-Path -LiteralPath $publicKeyPath)) {
    throw "Missing public key: $publicKeyPath"
}
$publicKey = [System.IO.File]::ReadAllText($publicKeyPath).Trim()
if ($publicKey -notmatch '^ssh-ed25519 [A-Za-z0-9+/=]+(?: .*)?$') {
    throw 'Public key is not a valid Ed25519 OpenSSH key.'
}

$installCommand = @'
set -eu
umask 077
mkdir -p "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
IFS= read -r incoming_key
case "$incoming_key" in
  "ssh-ed25519 "*) ;;
  *) exit 2 ;;
esac
grep -qxF "$incoming_key" "$HOME/.ssh/authorized_keys" || printf '%s\n' "$incoming_key" >> "$HOME/.ssh/authorized_keys"
chmod 700 "$HOME/.ssh"
chmod 600 "$HOME/.ssh/authorized_keys"
'@

$publicKey | & $SshCommand -o StrictHostKeyChecking=accept-new $sshTarget $installCommand
Assert-CommandSucceeded 'Installing public key on NAO'

& $SshCommand -i $resolvedKeyPath -o BatchMode=yes -o StrictHostKeyChecking=yes $sshTarget 'true'
Assert-CommandSucceeded 'Verifying key-only NAO connection'

$envDirectory = Split-Path -Parent $resolvedEnvFile
if (-not (Test-Path -LiteralPath $envDirectory)) {
    New-Item -ItemType Directory -Force -Path $envDirectory | Out-Null
}
if (-not (Test-Path -LiteralPath $resolvedEnvFile)) {
    $example = Join-Path $repoRoot '.env.example'
    if (Test-Path -LiteralPath $example) {
        [System.IO.File]::WriteAllText(
            $resolvedEnvFile,
            [System.IO.File]::ReadAllText($example),
            [System.Text.UTF8Encoding]::new($false)
        )
    }
}

Remove-EnvValue $resolvedEnvFile 'NAO_NETWORK_BROKER_ENABLED'
Set-EnvValue $resolvedEnvFile 'NAO_NETWORK_HOST' $NaoIp
Set-EnvValue $resolvedEnvFile 'NAO_NETWORK_BROKER_PORT' '6675'
Set-EnvValue $resolvedEnvFile 'NAO_SSH_USER' $User
Set-EnvValue $resolvedEnvFile 'NAO_SSH_KEY' $resolvedKeyPath
Set-EnvValue $resolvedEnvFile 'NAO_NETWORK_ALLOWED_ORIGINS' "http://$NaoIp`:3000"

Write-Host "Network administration configured for $sshTarget."
Write-Host "Environment updated at $resolvedEnvFile (no private key material copied)."
