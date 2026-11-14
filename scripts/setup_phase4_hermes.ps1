$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$profile = Join-Path $root '.phase4_hermes'
$envPath = Join-Path $profile '.env'
if (-not (Test-Path (Join-Path $root 'venv_hermes\Scripts\hermes.exe'))) { throw 'Hermes venv missing.' }
if (-not (Test-Path $envPath)) {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $key = [BitConverter]::ToString($bytes).Replace('-', '')
    @("API_SERVER_ENABLED=true", "API_SERVER_HOST=127.0.0.1", "API_SERVER_PORT=8642", "API_SERVER_KEY=$key") |
        Set-Content -LiteralPath $envPath -Encoding UTF8
}
$env:HERMES_HOME = $profile
& (Join-Path $root 'venv_hermes\Scripts\python.exe') (Join-Path $root 'scripts\check_hermes_profile.py')
if ($LASTEXITCODE -ne 0) { throw 'Hermes profile validation failed; refusing startup.' }
