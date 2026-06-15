@echo off
setlocal
cd /d "%~dp0"

echo.
echo Prism32 Windows Installer
echo =========================
echo.

where powershell >nul 2>nul
if errorlevel 1 goto no_powershell

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Yes
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
  echo Install failed with exit code %RC%.
  echo See README_WINDOWS.md for manual install steps.
) else (
  echo Install complete.
  echo Open a new Command Prompt or PowerShell window, then run: prism32
)
echo.
pause
exit /b %RC%

:no_powershell
echo PowerShell was not found.
echo Use a Windows version with PowerShell installed, or run Python manually:
echo   python prism32.py --setup-runtime
echo   python prism32.py
echo.
pause
exit /b 1
