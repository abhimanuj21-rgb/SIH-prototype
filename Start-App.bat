@echo off
rem Double-click to start the platform (runs start.ps1 without changing any system policy).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
