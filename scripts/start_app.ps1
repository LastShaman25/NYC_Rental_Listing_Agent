# Rental Listing Agent launcher: starts Docker Desktop if needed, waits for the
# database, then runs the Streamlit workbench. Invoked by start_app.bat.
$ErrorActionPreference = "Continue"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Test-DockerEngine {
    docker info 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Write-Host "[1/4] Checking Docker engine..."
if (-not (Test-DockerEngine)) {
    Write-Host "      Docker engine not running - starting Docker Desktop..."
    $started = $false
    docker desktop start 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $exe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
        if (Test-Path $exe) { Start-Process $exe; $started = $true }
        else {
            Write-Host ""
            Write-Host "ERROR: Docker Desktop is not installed at the expected path." -ForegroundColor Red
            Write-Host "Install/start Docker Desktop manually, then re-run start_app.bat."
            exit 1
        }
    }
    $deadline = (Get-Date).AddSeconds(120)
    while (-not (Test-DockerEngine)) {
        if ((Get-Date) -gt $deadline) {
            Write-Host ""
            Write-Host "ERROR: Docker engine did not become ready within 2 minutes." -ForegroundColor Red
            Write-Host "Open Docker Desktop, wait for the whale icon, then re-run start_app.bat."
            exit 1
        }
        Start-Sleep -Seconds 3
    }
}
Write-Host "      Docker engine ready."

Write-Host "[2/4] Starting the database container..."
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: 'docker compose up -d' failed - see the message above." -ForegroundColor Red
    exit 1
}

Write-Host "[3/4] Waiting for the database to accept connections..."
$deadline = (Get-Date).AddSeconds(60)
while ($true) {
    docker exec rental_agent_db pg_isready -U rental -d rental_dev 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    if ((Get-Date) -gt $deadline) {
        Write-Host "ERROR: database did not become ready within 60s." -ForegroundColor Red
        Write-Host "Check: docker logs rental_agent_db"
        exit 1
    }
    Start-Sleep -Seconds 2
}
Write-Host "      Database ready."

if ($env:STARTAPP_TEST -eq "1") {
    Write-Host "READY (test mode - skipping UI launch)"
    exit 0
}

Write-Host "[4/4] Starting the app at http://127.0.0.1:8600"
Write-Host "      (Close this window or press Ctrl+C to stop the app.)"
Start-Process "http://127.0.0.1:8600"
uv run --no-sync uvicorn rental_agent.webui.app:app --host 127.0.0.1 --port 8600
exit $LASTEXITCODE
