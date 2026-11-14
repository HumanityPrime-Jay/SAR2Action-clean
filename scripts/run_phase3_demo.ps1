param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $root 'docs\phase3_demo_pids.json'
$python = Join-Path $root 'venv\Scripts\python.exe'
$node = (Get-Command node.exe -ErrorAction Stop).Source
if ($Stop) {
    if (Test-Path $pidPath) {
        $owned = Get-Content $pidPath -Raw | ConvertFrom-Json
        foreach ($entry in $owned) {
            $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.pid)" -ErrorAction SilentlyContinue
            if ($process -and $process.ExecutablePath -eq $entry.path -and
                $process.CommandLine.Contains($entry.marker)) { Stop-Process -Id $entry.pid }
        }
        Remove-Item -LiteralPath $pidPath
    }
    Write-Output 'Stopped demo launcher processes.'
    exit 0
}
if (-not (Test-Path $python)) { throw "Python environment missing: $python" }
if (-not (Test-Path (Join-Path $root 'frontend\node_modules\vite'))) { throw 'Frontend dependencies missing. Run npm ci in frontend.' }
$owned = @()
$launchedPorts = @()
function Start-IfNeeded($port, $file, $arguments, $directory) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { Write-Output "Port $port is already listening; using existing service."; return }
    $process = Start-Process -FilePath $file -ArgumentList $arguments -WorkingDirectory $directory -WindowStyle Hidden -PassThru
    $marker = if ($port -eq 8000) { 'uvicorn backend.app.main:app' } else { 'vite.js' }
    $script:owned += @{ pid = $process.Id; path = $file; marker = $marker }
    $script:launchedPorts += $port
}
Start-IfNeeded 8000 $python @('-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000') $root
Start-IfNeeded 5173 $node @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173') (Join-Path $root 'frontend')
foreach ($url in @('http://127.0.0.1:8000/api/health','http://127.0.0.1:5173/')) {
    $ready = $false
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        try { $ready = (Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200; if ($ready) { break } } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "Demo service did not become ready: $url" }
}
foreach ($port in $launchedPorts) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop | Select-Object -First 1
    $service = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    $marker = if ($port -eq 8000) { 'uvicorn backend.app.main:app' } else { 'vite.js' }
    if ($service.CommandLine.Contains($marker) -and $owned.pid -notcontains $service.ProcessId) {
        $owned += @{ pid = $service.ProcessId; path = $service.ExecutablePath; marker = $marker }
    }
}
if ($owned.Count -gt 0) { $owned | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $pidPath -Encoding UTF8 }
Write-Output 'SAR2Action demo ready: http://127.0.0.1:5173/'
Write-Output 'Select Synthetic Demo in the AI Earth Investigator and ask for the top three regions.'
Write-Output 'This deterministic demo does not use Hermes inference; the Phase 4/5 launcher reports the separate Gateway state.'
Write-Output "Stop launched processes with: & '$PSCommandPath' -Stop"
