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
    # A discoverable module may still fail at import time (for example, blocked native DLLs).
    # Import the actual modules before selecting the interpreter.
    $importCheck = & $candidate -c "import numpy, sounddevice, pyautogui, pygetwindow, pywinauto" 2>&1
    if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
    Write-Warning "Desktop dependencies failed to import in $candidate. Verify the approved environment and Windows application-control policy."
    if ($importCheck) { Write-Verbose ($importCheck | Out-String) }
}
if (-not $python) { throw 'Desktop control and microphone support need numpy, sounddevice, pyautogui, pygetwindow, and pywinauto in the project .venv or approved bhashalearn-safe-venv. System Python is not supported.' }
Write-Host 'BHASHALEARN desktop companion is temporary and loopback-only. Keep this window open; Ctrl+C stops it.'
Write-Host "Using isolated interpreter: $python"
$env:BHASHALEARN_COMPANION_PORT = [string]$Port
& $python scripts/desktop_companion.py
