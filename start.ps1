# One-command launcher for anyone running the platform on their own laptop.
# Needs Python 3.12+ and Node.js 18+ installed. First run installs everything
# (a few minutes); later runs start in seconds. Then open http://localhost:8000
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "First run: creating the Python environment..." -ForegroundColor Cyan
    python -m venv (Join-Path $root "backend\.venv")
}
Write-Host "Installing / checking Python packages..." -ForegroundColor Cyan
& $py -m pip install --quiet -r (Join-Path $root "backend\requirements.txt")

Push-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules")) {
    Write-Host "First run: installing website packages..." -ForegroundColor Cyan
    npm ci
}
Write-Host "Building the website..." -ForegroundColor Cyan
npm run build
Pop-Location

Write-Host ""
Write-Host "Platform running at  http://localhost:8000   (Ctrl+C to stop)" -ForegroundColor Green
Write-Host "Others on the same Wi-Fi can open  http://<this-laptop's-IP>:8000" -ForegroundColor Green
Write-Host "Public link: in ANOTHER window run" -ForegroundColor Green
Write-Host "  cloudflared tunnel --url http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "KEEP THIS WINDOW OPEN - closing it stops the platform (and any shared link)." -ForegroundColor Red
Write-Host "First start downloads map layers in the background (a few minutes)." -ForegroundColor DarkGray
Start-Process "http://localhost:8000"
Push-Location (Join-Path $root "backend")
& $py -m uvicorn main:app --host 0.0.0.0 --port 8000
Pop-Location
