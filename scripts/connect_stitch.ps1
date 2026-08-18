# Registers Google Stitch's official MCP server (https://stitch.googleapis.com/mcp)
# with Claude Code.
#
# Two auth paths, tried in this order:
#   A) -ApiKey <key>  : a key created at stitch.withgoogle.com Settings > API keys.
#      The script tests it BOTH as "Authorization: Bearer <key>" and as
#      "X-Goog-Api-Key: <key>" and registers whichever the server accepts.
#   B) gcloud OAuth   : requires the Google Cloud SDK and `gcloud auth login`.
#      Tokens expire ~1 hour; re-run this script to refresh.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\connect_stitch.ps1 -ApiKey YOUR_KEY
#   powershell -ExecutionPolicy Bypass -File scripts\connect_stitch.ps1            # gcloud route
#
# The MCP server appears in NEW Claude Code sessions after registration.

param(
    [string]$ApiKey = "",
    # Optional: your GCP project id (only needed on the gcloud route).
    [string]$Project = ""
)

$ErrorActionPreference = "Stop"
$mcpUrl = "https://stitch.googleapis.com/mcp"
# list_projects is read-only: proves auth works without creating anything.
$probeBody = '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_projects","arguments":{}}}'

function Test-StitchAuth([hashtable]$headers) {
    try {
        $r = Invoke-WebRequest -Uri $mcpUrl -Method POST -ContentType "application/json" `
            -Headers $headers -Body $probeBody -UseBasicParsing -TimeoutSec 30
        if ($r.Content -match '"isError":true') { return $r.Content }
        return $true
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            $reader = New-Object IO.StreamReader($resp.GetResponseStream())
            return $reader.ReadToEnd()
        }
        return $_.Exception.Message
    }
}

function Register-Stitch([string[]]$headerArgs) {
    claude mcp remove stitch -s user 2>$null | Out-Null
    $args = @("mcp", "add", "--transport", "http", "stitch", $mcpUrl, "-s", "user") + $headerArgs
    & claude @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "claude mcp add failed - is the Claude Code CLI on PATH?" -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    Write-Host "Done. Start a NEW Claude Code session and the 'stitch' tools will be available." -ForegroundColor Green
}

if ($ApiKey -ne "") {
    Write-Host "[1/2] Testing the Stitch API key as a Bearer token..."
    $result = Test-StitchAuth @{ "Authorization" = "Bearer $ApiKey" }
    if ($result -eq $true) {
        Write-Host "      Accepted as Bearer token."
        Write-Host "[2/2] Registering with Claude Code..."
        Register-Stitch @("--header", "Authorization: Bearer $ApiKey")
        exit 0
    }
    Write-Host "      Rejected as Bearer. Response: $($result.ToString().Substring(0, [Math]::Min(200, $result.ToString().Length)))"
    Write-Host "[1/2] Testing the key as X-Goog-Api-Key..."
    $result = Test-StitchAuth @{ "X-Goog-Api-Key" = $ApiKey }
    if ($result -eq $true) {
        Write-Host "      Accepted as X-Goog-Api-Key."
        Write-Host "[2/2] Registering with Claude Code..."
        Register-Stitch @("--header", "X-Goog-Api-Key: $ApiKey")
        exit 0
    }
    Write-Host "      Rejected as API key too. Response: $($result.ToString().Substring(0, [Math]::Min(200, $result.ToString().Length)))" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "The key was not accepted in either form - falling back to the gcloud route." -ForegroundColor Yellow
    Write-Host ""
}

$gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
if (-not $gcloud) {
    Write-Host "gcloud is not installed. Run:  winget install Google.CloudSDK" -ForegroundColor Red
    Write-Host "then:  gcloud auth login   and re-run this script."
    exit 1
}

Write-Host "[1/3] Getting a fresh access token from gcloud..."
$token = (gcloud auth print-access-token 2>$null | Select-Object -First 1)
if (-not $token) {
    Write-Host "No token - sign in first with:  gcloud auth login" -ForegroundColor Red
    exit 1
}

Write-Host "[2/3] Verifying the token against the Stitch MCP endpoint..."
$headers = @{ "Authorization" = "Bearer $token" }
$headerArgs = @("--header", "Authorization: Bearer $token")
if ($Project -ne "") {
    $headers["X-Goog-User-Project"] = $Project
    $headerArgs += @("--header", "X-Goog-User-Project: $Project")
}
$result = Test-StitchAuth $headers
if ($result -ne $true) {
    Write-Host "Token rejected:" -ForegroundColor Yellow
    Write-Host $result
    Write-Host "If the error mentions a project, enable the API and pass your project id:"
    Write-Host "  gcloud services enable stitch.googleapis.com"
    Write-Host "  powershell -File scripts\connect_stitch.ps1 -Project <your-gcp-project-id>"
    exit 1
}
Write-Host "      Token accepted."

Write-Host "[3/3] Registering with Claude Code (user scope)..."
Register-Stitch $headerArgs
Write-Host "Note: gcloud tokens expire in ~1 hour; re-run this script to refresh."
