param(
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501,
    [switch]$NoUi
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$EnvFile = Join-Path $Root "backend\.env"

if (-not (Test-Path $EnvFile)) {
    Write-Warning "backend\.env is missing. Copy backend\.env.example to backend\.env and fill it in."
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python was not found on PATH. Activate the project virtual environment first."
}

Write-Host "Starting merged API on http://localhost:$ApiPort ..."
$Api = Start-Process -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "app.merged_main:app", "--reload", "--port", "$ApiPort") `
    -WorkingDirectory (Join-Path $Root "backend") `
    -PassThru

if (-not $NoUi) {
    if (-not (Get-Command streamlit -ErrorAction SilentlyContinue)) {
        throw "streamlit was not found on PATH. Run: pip install -r requirements-ui.txt"
    }
    $env:API_URL = "http://localhost:$ApiPort"
    Write-Host "Starting merged UI on http://localhost:$UiPort ..."
    $Ui = Start-Process -FilePath "streamlit" `
        -ArgumentList @("run", "ui/merged_app.py", "--server.port", "$UiPort") `
        -WorkingDirectory $Root `
        -PassThru
    Write-Host "API PID: $($Api.Id)  UI PID: $($Ui.Id)"
} else {
    Write-Host "API PID: $($Api.Id)"
}

Write-Host "Press Ctrl+C in each process window to stop. This script does not daemonize them."
