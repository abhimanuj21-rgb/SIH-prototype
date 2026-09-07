# Dev launcher — starts backend (:8000) and frontend (:5173) in two windows.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "Starting backend on :8000 ..."
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "cd '$root\backend'; .\.venv\Scripts\Activate.ps1; uvicorn main:app --reload --port 8000"
)

Write-Host "Starting frontend on :5173 ..."
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "cd '$root\frontend'; npm run dev"
)

Write-Host "Backend:  http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:5173"
