$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root 'venv\Scripts\python.exe'
$frontend = Join-Path $root 'frontend'
$results = [ordered]@{}
$failed = $false

function Invoke-ReleaseGate([string]$Name, [scriptblock]$Action) {
    try {
        & $Action
        if ($LASTEXITCODE -ne 0) { throw "exit code $LASTEXITCODE" }
        $script:results[$Name] = 'PASS'
    } catch {
        $script:results[$Name] = "FAIL: $($_.Exception.Message)"
        $script:failed = $true
        Write-Warning "$Name failed; continuing remaining release gates"
    }
}

try {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Project Python venv is missing' }
    Push-Location $root
    try {
        Invoke-ReleaseGate 'science_cache' { & $python 'scripts\validate_science_cache.py' --cache-dir 'data\cache' --output 'docs\final_cache_integrity.json' }
        Invoke-ReleaseGate 'scientific_claim_audit' { & $python 'scripts\audit_final_science.py' }
        Invoke-ReleaseGate 'python_pytest' { & $python -m pytest -q }
        Push-Location $frontend
        try {
            Invoke-ReleaseGate 'frontend_tests' { & npm.cmd test -- --run }
            Invoke-ReleaseGate 'typescript' { & npx.cmd tsc -b --pretty false }
            Invoke-ReleaseGate 'vite_build' { & npm.cmd run build }
        } finally { Pop-Location }
        Invoke-ReleaseGate 'local_services' { & (Join-Path $PSScriptRoot 'start_release_demo.ps1') -Demo A -NoBrowser }
        Invoke-ReleaseGate 'http_e2e' { & $python 'scripts\final_http_e2e.py' }
        Push-Location $frontend
        try {
            Invoke-ReleaseGate 'chrome_e2e' { & npx.cmd playwright test --config=playwright.config.ts --project=chrome }
        } finally { Pop-Location }
        Invoke-ReleaseGate 'real_gemini_science' { & (Join-Path $PSScriptRoot 'run_gemini_science_eval.ps1') }
        Invoke-ReleaseGate 'credential_scan' { & $python 'scripts\audit_final_security.py' }
        $sourceReport = Join-Path $root 'docs\nisar_source_reproducibility.json'
        $results['source_provenance'] = if (Test-Path -LiteralPath $sourceReport -PathType Leaf) {
            'REPORT_PRESENT_REQUIRES_REVIEW'
        } else { 'PROVENANCE_PENDING_REPORT_NOT_DELIVERED' }
    } finally { Pop-Location }
} catch {
    Write-Error "Release acceptance failed: $($_.Exception.Message)" -ErrorAction Continue
    $failed = $true
} finally {
    $report = [ordered]@{ status = $(if ($failed) { 'FAIL' } else { 'PASS' }); gates = $results }
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root 'docs\RELEASE_ACCEPTANCE_RESULTS.json') -Encoding UTF8
}
if ($failed) { exit 1 }
Write-Output 'Release acceptance PASS. See docs/RELEASE_ACCEPTANCE_RESULTS.json.'
