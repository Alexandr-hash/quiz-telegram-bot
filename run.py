"""
run.py - Основной запуск Quiz Telegram Bot
Запуск: python run.py
"""
import sys
import os
from pathlib import Path

# Добавляем текущую директорию в Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Добавляем папку src в Python path
src_dir = current_dir / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

print("=" * 50)
print("QUIZ TELEGRAM BOT - MAIN LAUNCHER")
print("=" * 50)

try:
    # Проверяем наличие .env файла
    env_file = current_dir / ".env"
    if not env_file.exists():
        print("WARNING: .env file not found!")
        print("Create it from templates/.env.example")
        print("Command: copy templates\\.env.example .env")
    
    # Импортируем и запускаем основную функцию
    from main import main
    
    exit_code = main()
    sys.exit(exit_code)
    
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    print("\nSolutions:")
    print("1. Run from src folder: cd src && python main.py")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Check folder structure")
    sys.exit(1)
except Exception as e:
    print(f"UNEXPECTED ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)