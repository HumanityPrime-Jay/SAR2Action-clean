param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$servicePids = Join-Path $root 'docs\phase4_service_pids.json'
$phase3 = Join-Path $root 'scripts\run_phase3_demo.ps1'
$modelExe = 'C:\Users\User\Downloads\llama-b11095-bin-win-cuda-13.4-x64\llama-server.exe'
$modelFile = 'D:\models\gemma4-26b-qat\gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf'
$hermesExe = Join-Path $root 'venv_hermes\Scripts\hermes.exe'
if ($Stop) {
    if (Test-Path (Join-Path $root 'docs\phase3_demo_pids.json')) {
        & $phase3 -Stop
    }
    if (Test-Path $servicePids) {
        $owned = Get-Content $servicePids -Raw | ConvertFrom-Json
        foreach ($entry in $owned) {
            $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.pid)" -ErrorAction SilentlyContinue
            if ($process -and $process.CommandLine.Contains($entry.marker)) {
                Stop-Process -Id $entry.pid -ErrorAction SilentlyContinue
            }
        }
        Remove-Item -LiteralPath $servicePids
    }
    Write-Output 'Stopped Phase 4 launcher-owned services.'
    exit 0
}
$owned = @()
if (-not (Test-Path $modelExe) -or -not (Test-Path $modelFile)) {
    throw 'Existing llama-server executable or model file is missing; real mode cannot start.'
}
$listener = Get-NetTCPConnection -LocalPort 8086 -State Listen -ErrorAction SilentlyContinue
if ($listener -and $listener.LocalAddress -ne '127.0.0.1') { throw 'Model server port 8086 is not localhost-only.' }
if (-not $listener) {
    $p = Start-Process -FilePath $modelExe -ArgumentList '-m',$modelFile,'-c','4096','-ngl','99','--host','127.0.0.1','--port','8086' `
        -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'docs\phase4_llama.out.log') `
        -RedirectStandardError (Join-Path $root 'docs\phase4_llama.err.log') -PassThru
    $owned += @{ pid = $p.Id; marker = 'llama-server' }
}
$modelReady = $false
for ($i=0; $i -lt 90; $i++) {
    try { $modelReady = (Invoke-RestMethod 'http://127.0.0.1:8086/health' -TimeoutSec 2).status -eq 'ok'; if ($modelReady) { break } } catch {}
    Start-Sleep -Milliseconds 500
}
if (-not $modelReady) { throw 'Local model did not pass /health.' }
$models = Invoke-RestMethod 'http://127.0.0.1:8086/v1/models' -TimeoutSec 5
$modelName = $models.data[0].id
$env:SAR2ACTION_MODEL_URL = 'http://127.0.0.1:8086/v1/chat/completions'
$env:SAR2ACTION_MODEL_NAME = $modelName
$env:SAR2ACTION_MODEL_PROVIDER = 'openai_compatible'

& (Join-Path $root 'scripts\setup_phase4_hermes.ps1')
$env:HERMES_HOME = Join-Path $root '.phase4_hermes'
$gateway = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue
if ($gateway -and $gateway.LocalAddress -ne '127.0.0.1') { throw 'Hermes Gateway port 8642 is not localhost-only.' }
if (-not $gateway) {
    $p = Start-Process -FilePath $hermesExe -ArgumentList 'gateway','run' -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $root '.phase4_hermes\gateway.out.log') `
        -RedirectStandardError (Join-Path $root '.phase4_hermes\gateway.err.log') -PassThru
    $owned += @{ pid = $p.Id; marker = 'hermes' }
}
$gatewayReady = $false
for ($i=0; $i -lt 30; $i++) {
    try { $gatewayReady = (Invoke-RestMethod 'http://127.0.0.1:8642/health' -TimeoutSec 2).status -eq 'ok'; if ($gatewayReady) { break } } catch {}
    Start-Sleep -Milliseconds 500
}
if (-not $gatewayReady) { Write-Warning 'Hermes Gateway health unavailable; direct model mode remains available.' }

# Restart only launcher-owned Phase 3 services so the backend inherits model settings.
if (Test-Path (Join-Path $root 'docs\phase3_demo_pids.json')) { & $phase3 -Stop }
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    $status = Invoke-RestMethod 'http://127.0.0.1:8000/api/agent/status' -TimeoutSec 8
    if ($status.agent.status -ne 'online') { throw 'Port 8000 is occupied by an offline backend not owned by this launcher.' }
}
& $phase3
$status = Invoke-RestMethod 'http://127.0.0.1:8000/api/agent/status' -TimeoutSec 15
if ($status.agent.status -ne 'online') { throw 'Backend model provider health failed.' }
if ($owned.Count -gt 0) { $owned | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $servicePids -Encoding UTF8 }
Write-Output "Real model ready on 127.0.0.1:8086: $modelName"
Write-Output 'Hermes Gateway is localhost-only with zero built-in tools; chat inference requires a true 64K context and is currently blocked.'
Write-Output 'Demo UI: http://127.0.0.1:5173/ - choose Real AI Analysis and Synthetic Demo.'
