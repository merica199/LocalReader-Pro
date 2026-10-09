@echo off
rem Double-click to install LocalReader Pro. Everything it does is described
rem at the top of installers\windows\install.ps1.
rem Opened from inside the ZIP, Windows runs this file alone from a temporary
rem folder, without the rest of the installer next to it.
if not exist "%~dp0installers\windows\install.ps1" (
    echo This file was opened from inside the ZIP, so the rest of the installer is missing.
    echo Right-click the downloaded ZIP and choose Extract All. Then open the extracted
    echo folder and double-click "Install on Windows" there.
    echo.
    pause
    exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installers\windows\install.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%
