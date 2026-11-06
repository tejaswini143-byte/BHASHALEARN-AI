$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repoRoot ".env.e2e.local"
if (Test-Path -LiteralPath $configPath) {
    throw "Local E2E config already exists; preserving it. Inspect it locally and move it aside yourself before regenerating."
}
$securePassword = Read-Host "Enter the password for PostgreSQL role bhashalearn_e2e (local prompt; do not paste it into chat)" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$random = [Security.Cryptography.RandomNumberGenerator]::Create()

try {
    $databasePassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    if ([string]::IsNullOrWhiteSpace($databasePassword)) {
        throw "A non-empty E2E database password is required."
    }
    $encodedPassword = [Uri]::EscapeDataString($databasePassword)

    function New-TestPassword {
        param([Security.Cryptography.RandomNumberGenerator]$Generator)
        $bytes = New-Object byte[] 32
        $Generator.GetBytes($bytes)
        try {
            return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
        }
        finally {
            [Array]::Clear($bytes, 0, $bytes.Length)
        }
    }

    $studentA = "adv01-e2e-a-$([Guid]::NewGuid().ToString('N'))@example.com"
    $studentB = "adv01-e2e-b-$([Guid]::NewGuid().ToString('N'))@example.com"
    $studentPasswordA = New-TestPassword -Generator $random
    $studentPasswordB = New-TestPassword -Generator $random
    $databaseUrl = "postgresql+psycopg://bhashalearn_e2e:$encodedPassword@127.0.0.1:5432/bhashalearn_e2e_test"

    $lines = @(
        "BHASHALEARN_E2E_DATABASE_URL=$databaseUrl"
        "BHASHALEARN_E2E_EMAIL=$studentA"
        "BHASHALEARN_E2E_PASSWORD=$studentPasswordA"
        "BHASHALEARN_E2E_SECOND_EMAIL=$studentB"
        "BHASHALEARN_E2E_SECOND_PASSWORD=$studentPasswordB"
        "BHASHALEARN_E2E_ALLOW_AUTHENTICATED_READS=1"
        "BHASHALEARN_E2E_ALLOW_MUTATIONS=1"
        "BHASHALEARN_E2E_START_SERVERS=1"
        "BHASHALEARN_E2E_BACKEND_PORT=8012"
        "BHASHALEARN_E2E_FRONTEND_PORT=5184"
        "BHASHALEARN_E2E_PYTHON=$($repoRoot)\.venv-e2e\Scripts\python.exe"
        "BHASHALEARN_E2E_ENCRYPTED_PDF=$($repoRoot)\test-data\adv01-encrypted.pdf"
    )

    [IO.File]::WriteAllLines($configPath, $lines, [Text.UTF8Encoding]::new($false))
    Write-Output "Created ignored local E2E configuration at .env.e2e.local."
    Write-Output "Two unique synthetic student accounts were generated; credentials were not displayed."
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    if ($null -ne $databasePassword) {
        $databasePassword = $null
    }
    if ($null -ne $encodedPassword) {
        $encodedPassword = $null
    }
    $random.Dispose()
    $securePassword.Dispose()
}
