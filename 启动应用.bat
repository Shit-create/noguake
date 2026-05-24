@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set PY=%~dp0venv\Scripts\python.exe
set PORT=8765

if not exist "%PY%" (
    echo [ERROR] venv not found. Run install script first.
    echo Path: %PY%
    pause
    exit /b 1
)

if not exist "%~dp0app\main.py" (
    echo [ERROR] app\main.py not found. Run from project root.
    pause
    exit /b 1
)

echo Stopping old server on port %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ========================================
echo   Quiz App - http://127.0.0.1:%PORT%
echo ========================================
echo.

start "" "http://127.0.0.1:%PORT%"

"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
pause
