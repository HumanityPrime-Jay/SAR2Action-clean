param(
    [ValidateSet('A', 'B')][string]$Demo = 'A',
    [switch]$NoBrowser,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendUrl = 'http://127.0.0.1:8000'
$frontendUrl = 'http://127.0.0.1:5173'

function Test-LocalHealth([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch { return $false }
}

function Wait-LocalHealth([string]$Url, [int]$Seconds) {
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (Test-LocalHealth $Url) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

if (-not (Test-LocalHealth "$backendUrl/api/health")) {
    if ($CheckOnly) { throw 'Backend health unavailable on 127.0.0.1:8000' }
    if ($Demo -eq 'B' -and -not (Test-Path -LiteralPath (Join-Path $root 'GERMINI API.txt') -PathType Leaf)) {
        $python = Join-Path $root 'venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Project Python venv is missing' }
        Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $root -WindowStyle Hidden
    } else {
        $launcher = Join-Path $PSScriptRoot 'start_gemini_backend.ps1'
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$launcher`"", '-Port', '8000') -WorkingDirectory $root -WindowStyle Hidden
    }
    if (-not (Wait-LocalHealth "$backendUrl/api/health" 30)) { throw 'Backend did not become healthy' }
}

if (-not (Test-LocalHealth $frontendUrl)) {
    if ($CheckOnly) { throw 'Frontend unavailable on 127.0.0.1:5173' }
    Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1') -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden
    if (-not (Wait-LocalHealth $frontendUrl 30)) { throw 'Frontend did not become healthy' }
}

$status = Invoke-RestMethod -Uri "$backendUrl/api/agent/status" -TimeoutSec 10
if ($Demo -eq 'A') {
    if ($status.agent.status -ne 'online' -or $status.agent.provider -ne 'gemini') {
        throw 'Demo A requires a real online Gemini backend; no synthetic substitution is allowed'
    }
    if ($status.cached_evidence.status -eq 'blocked') { throw 'Demo A cached evidence is blocked' }
    $url = "$frontendUrl/?demo=A"
    Write-Output 'Demo A: NISAR CACHED EVIDENCE - PROVENANCE PENDING'
} else {
    $url = "$frontendUrl/?demo=B"
    Write-Output 'Demo B: SIMULATED DATA - NOT NASA OBSERVATIONS'
}
Write-Output "Backend: $backendUrl/api/health (200)"
Write-Output "Frontend: $frontendUrl (200)"
Write-Output "Open: $url"
if (-not $NoBrowser) { Start-Process -FilePath $url }
