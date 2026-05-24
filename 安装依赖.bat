@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0\scripts\install.ps1"
if errorlevel 1 pause
exit /b %errorlevel%
