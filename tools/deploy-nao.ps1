[CmdletBinding()]
param(
    [ValidatePattern('^[0-9a-fA-F:.]+$')]
    [string]$NaoIp = '169.254.186.141',
    [string]$User = 'nao',
    [switch]$StartServices
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$archive = Join-Path ([System.IO.Path]::GetTempPath()) "naoControl-$timestamp.tar.gz"
$remoteArchive = "/tmp/naoControl-$timestamp.tar.gz"
$sshTarget = "$User@$NaoIp"

function Invoke-Checked([scriptblock]$Command, [string]$Description) {
    Write-Host "==> $Description"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed (exit code $LASTEXITCODE)." }
}

try {
    foreach ($required in @('ssh.exe', 'scp.exe')) {
        if (-not (Get-Command $required -ErrorAction SilentlyContinue)) {
            throw "Missing required command: $required"
        }
    }
    foreach ($requiredPath in @('nao', 'config', 'NaoControlReact/build')) {
        if (-not (Test-Path (Join-Path $repoRoot $requiredPath))) {
            throw "Missing required project path: $requiredPath"
        }
    }
    $python = Join-Path $repoRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        throw "Missing project Python runtime: $python"
    }

    Invoke-Checked { & $python (Join-Path $repoRoot 'tools\package_nao.py') $archive $repoRoot } 'Creating NAO deployment archive'

    Invoke-Checked { & scp.exe -o StrictHostKeyChecking=accept-new $archive "${sshTarget}:$remoteArchive" } 'Copying archive to NAO'

    $startFlag = if ($StartServices) { '1' } else { '0' }
    $remoteScript = @'
set -eu
archive="$1"
start_services="$2"
base="/home/nao/naoControl"
stage_root=$(mktemp -d /tmp/naoControl-stage.XXXXXX)
staged="$stage_root/naoControl"
backup="/home/nao/naoControl.backup.$$"
cleanup() { rm -rf "$stage_root" "$archive"; }
trap cleanup EXIT
mkdir -p "$staged"
tar -xzf "$archive" -C "$staged" --no-same-owner --no-same-permissions
test -f "$staged/nao/scripts/runtime/intelligence/gateway_server.py"
test -f "$staged/nao/scripts/runtime/intelligence/pc_gateway_launch.py"
test -f "$staged/nao/scripts/runtime/intelligence/provider_config.py"
test -f "$staged/nao/scripts/runtime/intelligence/led_controller.py"
test -f "$staged/nao/scripts/runtime/interaction_state.py"
test -f "$staged/nao/scripts/runtime/network_admin.py"
test -f "$staged/pc_gateway/src/nao_gateway/launcher_service.py"
test -f "$staged/nao/scripts/runtime/control_server/message_security.py"
test -f "$staged/nao/scripts/runtime/control_server/commands/network_commands.py"
test -f "$staged/nao/scripts/runtime/control_server/commands/nemotron_commands.py"
test -f "$staged/nao/scripts/runtime/start_nemotron.sh"
test -f "$staged/NaoControlReact/build/index.html"
test -f "$staged/config/agent_knowledge.json"
if test -f "$base/config/robot_gateway.secret"; then
    mkdir -p "$staged/config"
    cp "$base/config/robot_gateway.secret" "$staged/config/robot_gateway.secret"
fi
if test -f "$base/config/pc_gateway_target.json"; then
    cp "$base/config/pc_gateway_target.json" "$staged/config/pc_gateway_target.json"
fi
if test -f "$base/config/intelligence_provider.json"; then
    cp "$base/config/intelligence_provider.json" "$staged/config/intelligence_provider.json"
fi
for service in control web camera pc_bundle intelligence; do
    pid_file="/home/nao/run/naoControl/$service.pid"
    if test -f "$pid_file"; then
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then kill "$pid"; fi
        rm -f "$pid_file"
    fi
done
if test -d "$base"; then mv "$base" "$backup"; fi
mv "$staged" "$base"
if ! python -m py_compile "$base/nao/scripts/runtime/intelligence/gateway_server.py" "$base/nao/scripts/runtime/intelligence/pc_gateway_launch.py" "$base/nao/scripts/runtime/intelligence/provider_config.py" "$base/nao/scripts/runtime/intelligence/led_controller.py" "$base/nao/scripts/runtime/interaction_state.py" "$base/nao/scripts/runtime/control_server/server.py" "$base/nao/scripts/runtime/control_server/message_security.py" "$base/nao/scripts/runtime/control_server/commands/network_commands.py" "$base/nao/scripts/runtime/control_server/commands/nemotron_commands.py" "$base/nao/scripts/runtime/network_admin.py"; then
    rm -rf "$base"
    if test -d "$backup"; then mv "$backup" "$base"; fi
    exit 1
fi
if test "$start_services" = "1"; then
    sh "$base/nao/scripts/runtime/start_nemotron.sh"
fi
rm -rf "$backup"
echo "DEPLOY_OK base=$base services_started=$start_services"
'@
    # The NAO's legacy POSIX shell treats CR from Windows CRLF lines as part of
    # the option token (for example, `set -eu<CR>`). Send a Unix shell script.
    $remoteScript = $remoteScript.Replace("`r`n", "`n")
    $encodedScript = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
    # NAO's BusyBox shell rejects the optional `--` separator after `sh -s`.
    # The two positional arguments are already literal, validated values.
    $remoteCommand = "echo '$encodedScript' | base64 -d | sh -s '$remoteArchive' '$startFlag'"
    Invoke-Checked { & ssh.exe -o StrictHostKeyChecking=accept-new $sshTarget $remoteCommand } 'Installing and validating NAO runtime'
    Write-Host "Deployment complete. The tactile launcher remains responsible for normal start/stop."
}
finally {
    if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
    if ((Get-Location).Path -ne $repoRoot) { Pop-Location -ErrorAction SilentlyContinue }
}
