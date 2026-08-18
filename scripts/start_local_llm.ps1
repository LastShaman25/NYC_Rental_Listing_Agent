# Serves the local Qwen model for the RentAgent post Studio.
#
# Reuses the Innerfy/MVP project's llama-cpp-python runtime (already installed,
# server extra included) to expose an OpenAI-compatible endpoint at
# http://127.0.0.1:8601/v1 — nothing leaves the machine.
#
# Run:  powershell -ExecutionPolicy Bypass -File scripts\start_local_llm.ps1
# Stop: Ctrl+C (or close the window). First load takes ~30-60s (4.5 GB model).

$mvpPython = "C:\Users\CJ\OneDrive\Desktop\MVP\.venv\Scripts\python.exe"
$modelPath = "C:\Users\CJ\AppData\Local\Innerfy\ElementizationStudio\models\innerfy-slm-qwen2.5-7b-instruct-q4km-1\Qwen2.5-7B-Instruct-Q4_K_M.gguf"
$port = 8601

if (-not (Test-Path $mvpPython)) {
    Write-Host "ERROR: MVP venv python not found at $mvpPython" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $modelPath)) {
    Write-Host "ERROR: model not found at $modelPath" -ForegroundColor Red
    exit 1
}

Write-Host "Starting local Qwen2.5-7B-Instruct (llama.cpp, pure GPU) on http://127.0.0.1:$port ..."
Write-Host "All layers on the GPU; refuses to start if GPU offload is unavailable."
& $mvpPython "$PSScriptRoot\local_llm_server.py" $modelPath $port
exit $LASTEXITCODE
