param([string]$OutputPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'docs\phase3_environment_diagnostics.json'))
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root 'venv\Scripts\python.exe'
$hermes = Join-Path $root 'venv_hermes\Scripts\hermes.exe'
$registryDns = try { [bool](Resolve-DnsName registry.npmjs.org -ErrorAction Stop) } catch { $false }
$backendHttp = try { (Invoke-WebRequest 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 3).StatusCode } catch { 'unavailable' }
$frontendHttp = try { (Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 3).StatusCode } catch { 'unavailable' }
$result = [ordered]@{
    timestamp_utc = (Get-Date).ToUniversalTime().ToString('o')
    python = if (Test-Path $python) { & $python --version 2>&1 | Out-String } else { 'missing' }
    node = if (Get-Command node -ErrorAction SilentlyContinue) { & node --version 2>&1 | Out-String } else { 'missing' }
    npm = if (Get-Command npm -ErrorAction SilentlyContinue) { & npm --version 2>&1 | Out-String } else { 'missing' }
    hermes = if (Test-Path $hermes) { & $hermes --version 2>&1 | Out-String } else { 'missing' }
    fastapi = if (Test-Path $python) { & $python -c 'import fastapi; print(fastapi.__version__)' 2>&1 | Out-String } else { 'missing' }
    vite = if (Test-Path (Join-Path $root 'frontend\node_modules\vite\package.json')) { (Get-Content (Join-Path $root 'frontend\node_modules\vite\package.json') -Raw | ConvertFrom-Json).version } else { 'missing' }
    playwright = if (Test-Path (Join-Path $root 'frontend\node_modules\@playwright\test\package.json')) { (Get-Content (Join-Path $root 'frontend\node_modules\@playwright\test\package.json') -Raw | ConvertFrom-Json).version } else { 'missing' }
    gpu = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { (& nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1 | Out-String).Trim() } else { 'nvidia-smi unavailable' }
    cuda_torch = if (Test-Path (Join-Path $root 'venv\Lib\site-packages\torch')) { (& $python -c 'import torch; print(torch.cuda.is_available())' 2>&1 | Out-String).Trim() } else { 'torch unavailable in project venv' }
    model_endpoint_configured = [bool]($env:SAR2ACTION_MODEL_URL -and $env:SAR2ACTION_MODEL_NAME)
    model_provider = $env:SAR2ACTION_MODEL_PROVIDER
    model_key_present = [bool]$env:SAR2ACTION_MODEL_KEY
    local_socket = if (Test-Path $python) { (& $python -c 'import socket; a,b=socket.socketpair(); print(1); a.close(); b.close()' 2>&1 | Out-String).Trim() } else { 'unavailable' }
    npm_registry_dns = $registryDns
    backend_http = $backendHttp
    frontend_http = $frontendHttp
}
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output $OutputPath
