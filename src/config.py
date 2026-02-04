"""
Конфигурационные константы и пути
"""
from pathlib import Path

# ---------- Базовые пути ----------
BASE_DIR = Path(__file__).parent.parent

# ---------- Пути к директориям ----------
DATA_DIR = BASE_DIR / "data"
CONFIGS_DIR = BASE_DIR / "configs"
LOGS_DIR = BASE_DIR / "logs"
TEMPLATES_DIR = BASE_DIR / "templates"

# ---------- Файлы ----------
QUESTIONS_FILE = DATA_DIR / "questions.csv"
FACTS_FILE = DATA_DIR / "facts.csv"
STATE_FILE = DATA_DIR / "state.json"
CONFIG_FILE = CONFIGS_DIR / "config.json"
ERROR_LOG = LOGS_DIR / "error.log"
BOT_SCHEDULER_LOG = LOGS_DIR / "bot_scheduler.log"
FACT_IMAGES_DIR = DATA_DIR / "fact_images"

# ---------- Настройки по умолчанию ----------
DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_RANDOM_DELAY_MINUTES = 2
DEFAULT_MAX_QUESTIONS_PER_DAY = 3
DEFAULT_SKIP_WEEKENDS = False

# ---------- Проверка директорий ----------
def ensure_directories():
    """Создает необходимые директории, если их нет"""
    directories = [DATA_DIR, CONFIGS_DIR, LOGS_DIR, FACT_IMAGES_DIR]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)