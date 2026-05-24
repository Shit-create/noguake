@echo off
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
    echo venv not found. Run install bat first.
    pause
    exit /b 1
)
venv\Scripts\python.exe build_index.py
if errorlevel 1 pause
exit /b %errorlevel%
