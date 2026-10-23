@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%~dp0iniciar.py"
) else (
  python "%~dp0iniciar.py"
)
if errorlevel 1 pause
endlocal
