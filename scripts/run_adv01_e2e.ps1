param(
    [switch]$SkipMigration
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repoRoot ".env.e2e.local"
if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Ignored .env.e2e.local is missing. Run scripts\setup_adv01_e2e_local.ps1 locally first."
}

foreach ($line in [IO.File]::ReadAllLines($configPath)) {
    if ($line -match "^(BHASHALEARN_[^=]+)=(.*)$") {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process")
    }
}

$env:BHASHALEARN_E2E_START_SERVERS = "1"
$env:BHASHALEARN_DATABASE_URL = $env:BHASHALEARN_E2E_DATABASE_URL
$env:BHASHALEARN_DOCUMENT_STORAGE_DIR = Join-Path $repoRoot "test-data\private-documents"
$env:BHASHALEARN_JWT_SECRET_KEY = "e2e-only-local-secret-not-for-production"
$env:BHASHALEARN_API_PROXY_TARGET = "http://127.0.0.1:8012"
$env:BHASHALEARN_E2E_BACKEND_PORT = "8012"
$env:BHASHALEARN_E2E_FRONTEND_PORT = "5184"

if (-not $env:BHASHALEARN_E2E_DATABASE_URL -or -not $env:BHASHALEARN_E2E_EMAIL -or -not $env:BHASHALEARN_E2E_PASSWORD -or -not $env:BHASHALEARN_E2E_SECOND_EMAIL -or -not $env:BHASHALEARN_E2E_SECOND_PASSWORD) {
    throw "Required local E2E database and synthetic-student settings are incomplete."
}
if (-not (Test-Path -LiteralPath $env:BHASHALEARN_E2E_PYTHON)) {
    throw "The configured isolated E2E Python executable does not exist."
}
if (-not (Test-Path -LiteralPath $env:BHASHALEARN_E2E_ENCRYPTED_PDF)) {
    throw "The ignored encrypted E2E PDF fixture is missing."
}

function Invoke-IsolationCheck {
    Push-Location $repoRoot
    try {
        & $env:BHASHALEARN_E2E_PYTHON scripts\verify_adv01_e2e_isolation.py
        if ($LASTEXITCODE -ne 0) {
            throw "E2E database/storage verification failed; aborting before migrations or mutations."
        }
    }
    finally {
        Pop-Location
    }
}

function Assert-PortFree([int]$Port) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync("127.0.0.1", $Port)
        if ($connect.Wait(700) -and $client.Connected) {
            throw "Port $Port is already in use; no existing process was stopped."
        }
    }
    finally {
        $client.Dispose()
    }
}

function Wait-ForHttp([string]$Url, [int]$ExpectedStatus, [Diagnostics.Process]$Process) {
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) {
            throw "A temporary E2E service exited before becoming healthy. Check its ignored log under test-data."
        }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ([int]$response.StatusCode -eq $ExpectedStatus) { return }
        }
        catch {
            $status = $null
            try { $status = [int]$_.Exception.Response.StatusCode } catch { }
            if ($status -eq $ExpectedStatus) { return }
        }
        Start-Sleep -Milliseconds 400
    }
    throw "Timed out waiting for an expected HTTP $ExpectedStatus response from an isolated E2E service."
}

function Stop-OwnedProcess([Diagnostics.Process]$Process) {
    if ($null -ne $Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -ErrorAction SilentlyContinue
        if (-not $Process.WaitForExit(5000)) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

$backendProcess = $null
$viteProcess = $null
$logsRoot = Join-Path $repoRoot "test-data"
$runId = [Guid]::NewGuid().ToString("N")
$backendOut = Join-Path $logsRoot "adv01-backend-$runId.out.log"
$backendErr = Join-Path $logsRoot "adv01-backend-$runId.err.log"
$viteOut = Join-Path $logsRoot "adv01-vite-$runId.out.log"
$viteErr = Join-Path $logsRoot "adv01-vite-$runId.err.log"
$testExitCode = 1

try {
    Invoke-IsolationCheck

    if (-not $SkipMigration) {
        Push-Location $repoRoot
        try {
            & $env:BHASHALEARN_E2E_PYTHON -m alembic -c backend\alembic.ini upgrade head
            if ($LASTEXITCODE -ne 0) { throw "Alembic failed for the verified E2E database." }
        }
        finally {
            Pop-Location
        }
    }

    Invoke-IsolationCheck
    New-Item -ItemType Directory -Force -Path $env:BHASHALEARN_DOCUMENT_STORAGE_DIR | Out-Null
    Assert-PortFree 8012
    Assert-PortFree 5184

    $backendProcess = Start-Process -FilePath $env:BHASHALEARN_E2E_PYTHON `
        -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8012") `
        -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr

    $nodePath = (Get-Command node -ErrorAction Stop).Source
    $viteEntry = Join-Path $repoRoot "frontend\node_modules\vite\bin\vite.js"
    if (-not (Test-Path -LiteralPath $viteEntry)) { throw "Vite executable is missing from frontend/node_modules." }
    $viteProcess = Start-Process -FilePath $nodePath `
        -ArgumentList @($viteEntry, "--host", "127.0.0.1", "--port", "5184", "--strictPort") `
        -WorkingDirectory (Join-Path $repoRoot "frontend") -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $viteOut -RedirectStandardError $viteErr

    Wait-ForHttp "http://127.0.0.1:8012/health" 200 $backendProcess
    Wait-ForHttp "http://127.0.0.1:5184/health" 200 $viteProcess
    Write-Output "Direct backend health: HTTP 200"
    Write-Output "Vite proxy health: HTTP 200"

    $protectedStatus = 0
    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:5184/api/v1/documents" -TimeoutSec 10
        $protectedStatus = 200
    }
    catch {
        try { $protectedStatus = [int]$_.Exception.Response.StatusCode } catch { }
    }
    if ($protectedStatus -ne 401) { throw "Vite proxy protected-route check expected HTTP 401; received $protectedStatus." }
    Write-Output "Vite protected API proxy: HTTP 401 without credentials"

    $env:BHASHALEARN_E2E_FRONTEND_URL = "http://127.0.0.1:5184"
    Push-Location $repoRoot
    try {
        & $nodePath scripts\register_adv01_e2e_students.mjs
        if ($LASTEXITCODE -ne 0) { throw "Synthetic students could not be registered through the app UI." }
    }
    finally {
        Pop-Location
    }

    Invoke-IsolationCheck
    Stop-OwnedProcess $viteProcess
    Stop-OwnedProcess $backendProcess
    $viteProcess = $null
    $backendProcess = $null

    Remove-Item Env:\BHASHALEARN_DATABASE_URL -ErrorAction SilentlyContinue
    Push-Location (Join-Path $repoRoot "frontend")
    try {
        npm.cmd run test:e2e -- --reporter=line
        $testExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    Stop-OwnedProcess $viteProcess
    Stop-OwnedProcess $backendProcess
}

exit $testExitCode
