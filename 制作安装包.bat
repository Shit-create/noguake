@echo off
cd /d "%~dp0"

set PY=%~dp0venv\Scripts\python.exe
if not exist "%PY%" (
    echo [ERROR] venv not found. Run install_deps.bat first.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Noguake - Build installer package
echo ========================================
echo   This may take 5-15 minutes. Please wait...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_release.ps1"
if errorlevel 1 (
    echo.
    echo [FAILED] See errors above.
    pause
    exit /b 1
)

echo.
echo Done. Output:
echo   release\NoguakeSetup\     run install.ps1 inside
echo   installer\Output\         NoguakeSetup.exe if Inno Setup is installed
echo.
pause
