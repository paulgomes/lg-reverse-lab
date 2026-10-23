@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 "%~dp0lg_scout.py"
    goto :done
)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python "%~dp0lg_scout.py"
    goto :done
)
echo Python 3 was not found on Windows.
echo Install official Python 3 and select 'Add Python to PATH'.
echo Nothing needs to be installed on the home theater.
:done
if %ERRORLEVEL% NEQ 0 pause
endlocal
