# RentAgent launcher: starts Docker Desktop if needed, waits for the database,
# launches the local Qwen model server (Studio), then runs the web app.
# Invoked by start_app.bat.
$ErrorActionPreference = "Continue"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Test-DockerEngine {
    docker info 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Write-Host "[1/5] Checking Docker engine..."
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

Write-Host "[2/5] Starting the database container..."
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: 'docker compose up -d' failed - see the message above." -ForegroundColor Red
    exit 1
}

Write-Host "[3/5] Waiting for the database to accept connections..."
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
    Write-Host "READY (test mode - skipping model + UI launch)"
    exit 0
}

Write-Host "[4/5] Starting the local Qwen model server (post Studio, GPU)..."
$llmUp = $false
try {
    $probe = Invoke-WebRequest -Uri "http://127.0.0.1:8601/v1/models" -UseBasicParsing -TimeoutSec 2
    $llmUp = ($probe.StatusCode -eq 200)
} catch {}
if ($llmUp) {
    Write-Host "      Already running on port 8601."
} else {
    Start-Process powershell -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSScriptRoot\start_local_llm.ps1`""
    ) -WindowStyle Minimized
    Write-Host "      Launched in a minimized window (model loads ~30-60s;"
    Write-Host "      the Studio works as soon as it finishes - no need to wait)."
}

Write-Host "[5/5] Starting the app at http://127.0.0.1:8600"
Write-Host "      (Close this window or press Ctrl+C to stop the app;"
Write-Host "      the model server keeps its own minimized window.)"
Start-Process "http://127.0.0.1:8600"
uv run --no-sync uvicorn rental_agent.webui.app:app --host 127.0.0.1 --port 8600
exit $LASTEXITCODE
