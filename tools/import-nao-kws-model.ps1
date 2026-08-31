[CmdletBinding()]
param(
    [string]$SourceRoot = 'C:\Users\limao\Workspace\02\_Research\nao-kws-openwakeword\.worktrees\feature-nao-kws\models',
    [string]$RepoRoot = ''
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PSScriptRoot '..'
}
$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$source = (Resolve-Path -LiteralPath $SourceRoot).Path
$model = Join-Path $source 'nao_classifier.onnx'
$encoder = Join-Path $source 'openwakeword_encoder'
$destination = Join-Path $repo 'pc_gateway\models\kws'

if (-not (Test-Path -LiteralPath $model -PathType Leaf)) {
    throw "No se encontró el clasificador ONNX: $model"
}
if (-not (Test-Path -LiteralPath $encoder -PathType Container)) {
    throw "No se encontró el encoder openWakeWord: $encoder"
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -LiteralPath $model -Destination (Join-Path $destination 'nao_classifier.onnx') -Force
Copy-Item -LiteralPath $encoder -Destination (Join-Path $destination 'openwakeword_encoder') -Recurse -Force

Write-Host 'Modelo KWS importado en pc_gateway\models\kws.' -ForegroundColor Green
Write-Host 'Ahora ejecuta el despliegue del NAO y vuelve a preparar el PC gateway.' -ForegroundColor Green
