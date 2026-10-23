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
echo Nao foi encontrado Python 3 no Windows.
echo Instale Python 3 oficial e marque 'Add Python to PATH'.
echo Nao eh necessario instalar qualquer coisa no Home Theater.
:done
if %ERRORLEVEL% NEQ 0 pause
endlocal
