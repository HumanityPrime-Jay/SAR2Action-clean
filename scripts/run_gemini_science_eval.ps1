$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$credentialPath = Join-Path $root 'GERMINI API.txt'
$python = Join-Path $root 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $credentialPath -PathType Leaf)) { throw 'GEMINI_CREDENTIAL_MISSING' }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'PYTHON_VENV_MISSING' }
$secretLine = (Get-Content -LiteralPath $credentialPath -Raw -Encoding UTF8).Trim()
if ($secretLine.StartsWith('GEMINI_API_KEY=')) { $secretLine = $secretLine.Substring('GEMINI_API_KEY='.Length).Trim() }
if ($secretLine -notmatch '^[!-~]{20,200}$' -or $secretLine.Contains(' ')) { throw 'GEMINI_CREDENTIAL_FORMAT_INVALID' }
$oldKey = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY', 'Process')
$oldProvider = [Environment]::GetEnvironmentVariable('SAR2ACTION_LLM_PROVIDER', 'Process')
try {
    $env:GEMINI_API_KEY = $secretLine
    $env:SAR2ACTION_LLM_PROVIDER = 'gemini'
    Remove-Variable secretLine -ErrorAction SilentlyContinue
    Push-Location $root
    try {
        & $python 'scripts\evaluate_final_science.py'
        if ($LASTEXITCODE -ne 0) { throw 'REAL_GEMINI_SCIENCE_EVAL_FAILED' }
    } finally { Pop-Location }
} finally {
    [Environment]::SetEnvironmentVariable('GEMINI_API_KEY', $oldKey, 'Process')
    [Environment]::SetEnvironmentVariable('SAR2ACTION_LLM_PROVIDER', $oldProvider, 'Process')
}
