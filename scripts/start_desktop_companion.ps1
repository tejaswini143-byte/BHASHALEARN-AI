param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 18765
)
Set-Location (Split-Path -Parent $PSScriptRoot)
$candidatePython = @(
    (Join-Path (Get-Location) '.venv\Scripts\python.exe'),
    (Join-Path $env:USERPROFILE 'bhashalearn-safe-venv\Scripts\python.exe')
)
$python = $null
foreach ($candidate in $candidatePython) {
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $companionReady = & $candidate -c "import importlib.util; raise SystemExit(0 if all(importlib.util.find_spec(name) for name in ('numpy','sounddevice','pyautogui','pygetwindow','pywinauto')) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
}
if (-not $python) { throw 'Desktop control and microphone support need numpy, sounddevice, pyautogui, pygetwindow, and pywinauto in the project .venv or approved bhashalearn-safe-venv. System Python is not supported.' }
Write-Host 'BHASHALEARN desktop companion is temporary and loopback-only. Keep this window open; Ctrl+C stops it.'
Write-Host "Using isolated interpreter: $python"
$env:BHASHALEARN_COMPANION_PORT = [string]$Port
& $python scripts/desktop_companion.py
