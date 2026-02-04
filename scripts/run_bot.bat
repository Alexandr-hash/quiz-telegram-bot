@echo off
chcp 65001 > nul
cd /d "%~dp0.."

echo ========================================
echo QUIZ TELEGRAM BOT - LAUNCHER
echo ========================================

REM Проверяем наличие run.py
if exist "run.py" (
    echo Starting bot via run.py...
    python run.py
) else (
    echo ERROR: run.py not found!
    echo Trying to start via src/main.py...
    cd src
    python main.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Bot failed to start!
    echo Exit code: %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Bot finished successfully.
pause