# RentAgent all-in-one shutdown: web app + local Qwen model server + database
# container. Invoked by stop_app.bat. Mirrors start_app.ps1.
#
#   stop_app.bat                  -> stops app, model server, DB container
#   stop_app.ps1 -IncludeDocker   -> additionally quits Docker Desktop
#
# Data is never touched: the database container is stopped, not removed.

param(
    [switch]$IncludeDocker
)

$ErrorActionPreference = "Continue"

function Stop-PortListener([int]$Port, [string]$Label) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-Host "      $Label - not running."
        return
    }
    $stopped = @()
    foreach ($conn in $connections) {
        if ($stopped -contains $conn.OwningProcess) { continue }
        try {
            Stop-Process -Id $conn.OwningProcess -Force -Confirm:$false -ErrorAction Stop
            $stopped += $conn.OwningProcess
        } catch {}
    }
    Write-Host "      $Label - stopped."
}

Write-Host "[1/3] Stopping the RentAgent web app (port 8600)..."
Stop-PortListener -Port 8600 -Label "web app"

Write-Host "[2/3] Stopping the local Qwen model server (port 8601, frees GPU)..."
Stop-PortListener -Port 8601 -Label "model server"

Write-Host "[3/3] Stopping the database container..."
docker compose --project-directory (Split-Path -Parent $PSScriptRoot) stop 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "      Database container stopped (data kept; start_app.bat restores it)."
} else {
    Write-Host "      Docker engine not reachable - container already down."
}

if ($IncludeDocker) {
    Write-Host "[+] Quitting Docker Desktop..."
    docker desktop stop 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Get-Process "Docker Desktop" -ErrorAction SilentlyContinue |
            Stop-Process -Force -Confirm:$false -ErrorAction SilentlyContinue
    }
    Write-Host "      Docker Desktop closed."
}

Write-Host ""
Write-Host "All stopped. Double-click start_app.bat to bring everything back." -ForegroundColor Green
