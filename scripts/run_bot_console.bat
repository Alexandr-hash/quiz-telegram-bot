@echo off
chcp 65001 > nul
cd /d "%~dp0.."

echo ========================================
echo QUIZ TELEGRAM BOT - CONSOLE LAUNCHER
echo ========================================

if exist "run.py" (
    python run.py
) else (
    cd src
    python main.py
)