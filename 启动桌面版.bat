@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set PY=%~dp0venv\Scripts\python.exe

if not exist "%PY%" (
    echo [ERROR] Run install script first.
    pause
    exit /b 1
)

echo Installing pywebview if needed...
"%PY%" -m pip install pywebview -q

echo Starting desktop app...
"%PY%" app_desktop.py
pause
