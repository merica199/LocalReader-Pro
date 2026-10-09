@echo off
rem Double-click to install LocalReader Pro. Everything it does is described
rem at the top of installers\windows\install.ps1.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installers\windows\install.ps1" %*
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%
