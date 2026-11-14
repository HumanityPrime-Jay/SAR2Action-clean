param(
    [int]$Port = 8000,
    [string]$Model = $env:SAR2ACTION_GEMINI_MODEL
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$credentialPath = Join-Path $root 'GERMINI API.txt'
if (-not (Test-Path -LiteralPath $credentialPath -PathType Leaf)) {
    Write-Error 'GEMINI_CREDENTIAL_MISSING' -ErrorAction Continue
    exit 1
}

try {
    $lines = @(Get-Content -LiteralPath $credentialPath -Encoding UTF8 | Where-Object { $_.Trim().Length -gt 0 })
    if ($lines.Count -ne 1) { throw 'invalid' }
    $key = $lines[0].Trim()
    if ($key.StartsWith('GEMINI_API_KEY=')) { $key = $key.Substring('GEMINI_API_KEY='.Length).Trim() }
    if ($key -notmatch '^[!-~]{20,200}$' -or $key.Contains('=') -or $key.Contains(' ')) { throw 'invalid' }
} catch {
    Write-Error 'GEMINI_CREDENTIAL_FORMAT_INVALID' -ErrorAction Continue
    exit 1
}

if (-not $Model) { $Model = 'gemini-3.1-flash-lite' }
$python = Join-Path $root 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-Error 'PYTHON_VENV_MISSING' -ErrorAction Continue
    exit 1
}
$oldKey = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'Process')
$oldProvider = [Environment]::GetEnvironmentVariable('SAR2ACTION_LLM_PROVIDER', 'Process')
$oldModel = [Environment]::GetEnvironmentVariable('SAR2ACTION_GEMINI_MODEL', 'Process')
try {
    $env:GEMINI_API_KEY = $key
    $env:SAR2ACTION_LLM_PROVIDER = 'gemini'
    $env:SAR2ACTION_GEMINI_MODEL = $Model
    Remove-Variable key -ErrorAction SilentlyContinue
    Push-Location $root
    try {
        & $python -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port
        exit $LASTEXITCODE
    } finally { Pop-Location }
} finally {
    [Environment]::SetEnvironmentVariable('GEMINI_API_KEY', $oldKey, 'Process')
    [Environment]::SetEnvironmentVariable('SAR2ACTION_LLM_PROVIDER', $oldProvider, 'Process')
    [Environment]::SetEnvironmentVariable('SAR2ACTION_GEMINI_MODEL', $oldModel, 'Process')
}
