@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0"
set "START_SCRIPT=%PROJECT_ROOT%scripts\start_platform.ps1"

if not exist "%START_SCRIPT%" (
  echo ERROR: scripts\start_platform.ps1 was not found.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%START_SCRIPT%"
if errorlevel 1 (
  echo.
  echo ERROR: PIANXI failed to start. Check data\server-error.log.
  pause
  exit /b 1
)

powershell.exe -NoProfile -Command "Start-Sleep -Seconds 2"
start "" "http://localhost:8765"
exit /b 0
