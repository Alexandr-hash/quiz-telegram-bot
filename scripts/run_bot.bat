@echo off
setlocal
cd /d "%~dp0"

rem Полный путь к python (ОСТАЁТСЯ БЕЗ ИЗМЕНЕНИЙ)
set "PY=C:\Users\1\AppData\Local\Programs\Python\Python313\python.exe"

rem Безбуферный вывод + корректная кодировка
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8

rem Переходим в корень проекта (из scripts/ поднимаемся на уровень выше)
cd ..

rem Метка старта и запуск
echo [%date% %time%] START >> "logs\bot_scheduler.log"
"%PY%" -u "src\bot.py" >> "logs\bot_scheduler.log" 2>&1

rem Метка завершения
echo [%date% %time%] EXIT CODE %errorlevel% >> "logs\bot_scheduler.log"