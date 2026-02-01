# bot.py — вопросы + факт дня из CSV с конфигурацией из JSON
# Python 3.10+ | aiogram v3

import asyncio
import csv
import json
import logging
import os
import random
import contextlib
from pathlib import Path
from datetime import datetime, time, timedelta
from typing import Optional

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
)
from aiogram.types import FSInputFile

# --------------------- Загрузка .env ---------------------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден в .env")
if not CHANNEL_ID:
    raise RuntimeError("CHANNEL_ID не найден в .env")

# --------------------- Конфигурация ----------------------
QUESTIONS_FILE = Path("data/questions.csv")
FACTS_FILE = Path("data/facts.csv")
STATE_FILE = Path("data/state.json")
CONFIG_FILE = Path("configs/config.json")
ERROR_LOG = Path("logs/error.log")
FACT_IMAGES_DIR = Path("data/fact_images")

# --------------------- Логирование -----------------------
logging.basicConfig(
    filename=str(ERROR_LOG),
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# --------------------- Глобальные объекты ----------------
dp = Dispatcher()

# Вопросы: (question, options, correct_idx, explanation)
questions: list[tuple[str, list[str], int, Optional[str]]] = []
index: int = 0  # индекс следующего вопроса

# Факты: просто готовый текст сообщения
facts: list[str] = []
facts_index: int = 0  # индекс следующего факта

# Расписания (будут загружены из конфига)
SCHEDULE: list[time] = []
FACT_SCHEDULE: list[time] = []
CONFIG: dict = {}

# =========================================================
#                ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def seconds_until(t: time) -> float:
    """Сколько секунд до ближайшего времени t (сегодня/завтра)."""
    now = datetime.now()
    target = datetime.combine(now.date(), t)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


# --------------------- Состояние (индексы) ----------------

def load_state() -> tuple[int, int]:
    """Читаем index и facts_index из state.json."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            idx = int(data.get("index", 0))
            fidx = int(data.get("facts_index", 0))
            return idx, fidx
        except Exception:
            return 0, 0
    return 0, 0


def save_state(idx: int, fidx: int) -> None:
    """Сохраняем index и facts_index в state.json."""
    try:
        data = {
            "index": int(idx),
            "facts_index": int(fidx),
        }
        STATE_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.exception(f"Не удалось сохранить состояние в {STATE_FILE}: {e}")


def get_random_fact_image() -> Optional[Path]:
    """
    Возвращает путь к случайной картинке из папки fact_images
    или None, если папка пуста/не найдена.
    """
    if not FACT_IMAGES_DIR.exists():
        return None

    files = [
        p for p in FACT_IMAGES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    ]

    if not files:
        return None

    return random.choice(files)


# --------------------- Конфигурация -----------------------

def load_config() -> dict:
    """Загружает конфигурацию из JSON файла."""
    default_config = {
        "schedule": {
            "questions": ["10:00", "14:00", "18:00"],
            "facts": ["12:00"]
        },
        "settings": {
            "timezone": "Europe/Moscow",
            "random_delay_minutes": 0,
            "max_questions_per_day": 3,
            "skip_weekends": False
        },
        "messages": {
            "fact_header": "📚 ФАКТ ДНЯ\n\n",
            "question_header": "🧠 ВИКТОРИНА\n\n"
        }
    }
    
    if not CONFIG_FILE.exists():
        print(f"[INFO] Конфиг {CONFIG_FILE} не найден, создаю с настройками по умолчанию")
        CONFIG_FILE.parent.mkdir(exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(default_config, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return default_config
    
    try:
        with CONFIG_FILE.open('r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Глубокое объединение с дефолтными значениями
        def deep_merge(default, custom):
            for key, value in custom.items():
                if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                    deep_merge(default[key], value)
                else:
                    default[key] = value
            return default
        
        return deep_merge(default_config.copy(), config)
        
    except Exception as e:
        logger.exception(f"Ошибка загрузки конфига: {e}")
        print(f"[ERROR] Не удалось загрузить конфиг: {e}")
        return default_config


def format_seconds(seconds: float) -> str:
    """Форматирует секунды в читаемый вид."""
    if seconds < 60:
        return f"{int(seconds)} сек."
    elif seconds < 3600:
        return f"{int(seconds // 60)} мин."
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} ч. {minutes} мин."


# =========================================================
#                     ПАРСИНГ ВОПРОСОВ
# =========================================================

def _parse_csv_row_question(row: list[str]) -> tuple[str, list[str], int, Optional[str]]:
    """
    Формат строки:
      Вопрос, Вариант1, Вариант2, ..., ИндексПравильного[, Пояснение]

    ИндексПравильного может быть:
      - 1..N  (человеческий)
      - 0..N-1 (нуль-индекс)
    Пояснение — последняя колонка, может содержать запятые (Excel обернёт в кавычки).
    """
    row = [c.strip() for c in row]
    if len(row) < 4:
        raise ValueError("Мало колонок: минимум вопрос, ≥2 варианта, индекс.")

    # Если колонок >=5 — есть пояснение
    if len(row) >= 5:
        idx_str = row[-2]
        explanation = row[-1] if row[-1] else None
        opts = row[1:-2]
    else:
        idx_str = row[-1]
        explanation = None
        opts = row[1:-1]

    if len(opts) < 2 or len(opts) > 10:
        raise ValueError("Число вариантов должно быть от 2 до 10.")

    try:
        idx = int(idx_str)
    except Exception:
        raise ValueError("Индекс правильного ответа должен быть числом.")

    # Поддерживаем 1..N и 0..N-1
    if 1 <= idx <= len(opts):
        idx -= 1
    elif not (0 <= idx < len(opts)):
        raise ValueError("Индекс правильного ответа вне диапазона вариантов.")

    question = row[0]
    if not question:
        raise ValueError("Пустой текст вопроса.")

    return question, opts, idx, explanation


def load_questions_from_csv() -> list[tuple[str, list[str], int, Optional[str]]]:
    """Читаем вопросы из questions.csv."""
    if not QUESTIONS_FILE.exists():
        print(f"[WARN] Файл {QUESTIONS_FILE} не найден.")
        return []

    encodings = ["utf-8", "utf-8-sig", "cp1251", "cp1252"]
    last_err: Optional[Exception] = None

    for enc in encodings:
        try:
            with QUESTIONS_FILE.open("r", encoding=enc, newline="") as f:
                sample = f.read(2048)
                f.seek(0)

                # Простейшая эвристика для разделителя:
                first_line = sample.splitlines()[0] if sample else ""
                if ";" in first_line:
                    delimiter = ";"
                else:
                    delimiter = ","

                reader = csv.reader(f, delimiter=delimiter)
                data: list[tuple[str, list[str], int, Optional[str]]] = []
                line_no = 0

                for row in reader:
                    line_no += 1

                    # Пропуск пустых строк
                    if not row or all((c.strip() == "" for c in row)):
                        continue

                    # Пропуск заголовка
                    first_cell = (row[0] or "").strip().lower()
                    if line_no == 1 and first_cell in ("вопрос", "question"):
                        continue

                    try:
                        parsed = _parse_csv_row_question(row)
                        data.append(parsed)
                    except Exception as e:
                        logger.exception(
                            f"Строка {line_no} пропущена: {e}. Данные: {row}"
                        )
                        continue

            print(
                f"[INFO] questions.csv прочитан. Кодировка: {enc}. Строк: {len(data)}"
            )
            return data

        except Exception as e:
            last_err = e
            logger.exception(f"Ошибка чтения {QUESTIONS_FILE} ({enc}): {e}")
            continue

    print(
        f"[ERROR] Не удалось прочитать {QUESTIONS_FILE}. "
        f"Последняя ошибка: {last_err}"
    )
    return []


# =========================================================
#                     ПАРСИНГ ФАКТОВ
# =========================================================

def load_facts_from_csv() -> list[str]:
    """
    Формат facts.csv:
      Факт;Источник
    или:
      Факт,Источник
    Первая строка может быть заголовком: "Факт;Источник" / "Fact,Source".
    """
    if not FACTS_FILE.exists():
        print(f"[WARN] Файл {FACTS_FILE} не найден.")
        return []

    encodings = ["utf-8", "utf-8-sig", "cp1251", "cp1252"]
    last_err: Optional[Exception] = None

    for enc in encodings:
        try:
            with FACTS_FILE.open("r", encoding=enc, newline="") as f:
                sample = f.read(2048)
                f.seek(0)

                first_line = sample.splitlines()[0] if sample else ""
                if ";" in first_line:
                    delimiter = ";"
                elif "," in first_line:
                    delimiter = ","
                else:
                    delimiter = ";"

                reader = csv.reader(f, delimiter=delimiter)
                data: list[str] = []
                first = True

                for row in reader:
                    if not row or all((c.strip() == "" for c in row)):
                        continue

                    if first:
                        first_cell = (row[0] or "").strip().lower()
                        if first_cell.startswith(("факт", "fact")):
                            first = False
                            continue
                        first = False

                    fact_text = row[0].strip() if len(row) >= 1 else ""
                    source = row[1].strip() if len(row) >= 2 else ""

                    if not fact_text:
                        continue

                    if source:
                        text = f"{fact_text}\n\nИсточник: {source}"
                    else:
                        text = fact_text

                    data.append(text)

            print(
                f"[INFO] facts.csv прочитан. Кодировка: {enc}, "
                f"разделитель: '{delimiter}', строк: {len(data)}"
            )
            return data

        except Exception as e:
            last_err = e
            logger.exception(f"Ошибка чтения {FACTS_FILE} ({enc}): {e}")
            continue

    print(
        f"[ERROR] Не удалось прочитать {FACTS_FILE} ни в одной кодировке. "
        f"Последняя ошибка: {last_err}"
    )
    return []


# =========================================================
#                 ОТПРАВКА ВОПРОСОВ И ФАКТОВ
# =========================================================

async def send_quiz(
    bot: Bot,
    q: str,
    opts: list[str],
    correct_idx: int,
    expl: Optional[str] = None,
):
    await bot.send_poll(
        chat_id=CHANNEL_ID,
        question=q,
        options=opts,
        type="quiz",
        correct_option_id=correct_idx,
        explanation=expl if expl else None,
        is_anonymous=True,
    )


async def send_next_question(bot: Bot):
    global index, questions, facts_index
    if not questions:
        raise RuntimeError(
            "Список вопросов пуст. Заполни questions.csv и затем используй /reload."
        )
    q, opts, ci, expl = questions[index]
    await send_quiz(bot, q, opts, ci, expl)
    index = (index + 1) % len(questions)
    save_state(index, facts_index)


async def send_fact(bot: Bot, text: str):
    img_path = get_random_fact_image()

    if img_path is not None:
        try:
            photo = FSInputFile(str(img_path))
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo,
                caption=text,
            )
            return
        except Exception as e:
            logger.exception(f"Не удалось отправить картинку для факта ({img_path}): {e}")

    await bot.send_message(chat_id=CHANNEL_ID, text=text)


async def send_next_fact(bot: Bot):
    global facts, facts_index, index
    if not facts:
        raise RuntimeError(
            "Список фактов пуст. Заполни facts.csv и затем используй /reload."
        )
    text = facts[facts_index]
    await send_fact(bot, text)
    facts_index = (facts_index + 1) % len(facts)
    save_state(index, facts_index)


# =========================================================
#                        КОМАНДЫ
# =========================================================

@dp.message(Command(commands=["start", "help"]))
async def cmd_help(m: types.Message):
    text = (
        "Бот публикует викторины и «факт дня» в канал по расписанию.\n\n"
        "Команды:\n"
        "/reload — перечитать questions.csv и facts.csv\n"
        "/next — отправить следующий вопрос сейчас\n"
        "/nextfact — отправить следующий факт сейчас\n"
        "/status — показать количество и текущие индексы\n"
        "/schedule — показать текущее расписание\n"
        "/nexttime — когда следующая отправка\n"
        "/reloadconfig — перезагрузить конфигурацию\n\n"
        "Формат questions.csv:\n"
        "Вопрос,Вариант1,Вариант2,...,ИндексПравильного[,Пояснение]\n\n"
        "Формат facts.csv:\n"
        "Факт;Источник (источник можно опустить)."
    )
    await m.answer(text, parse_mode=None)


@dp.message(Command(commands=["reload"]))
async def cmd_reload(m: types.Message):
    global questions, index, facts, facts_index
    try:
        questions = load_questions_from_csv()
        facts = load_facts_from_csv()

        idx, fidx = load_state()

        if questions:
            index = min(idx, len(questions) - 1)
        else:
            index = 0

        if facts:
            facts_index = min(fidx, len(facts) - 1)
        else:
            facts_index = 0

        save_state(index, facts_index)

        await m.reply(
            f"Загружено вопросов: {len(questions)} (индекс: {index}). "
            f"Загружено фактов: {len(facts)} (индекс факта: {facts_index}).",
            parse_mode=None,
        )
    except Exception as e:
        logger.exception(f"/reload — ошибка: {e}")
        await m.reply(f"Ошибка: {e}", parse_mode=None)


@dp.message(Command(commands=["next"]))
async def cmd_next(m: types.Message):
    try:
        await send_next_question(m.bot)
        await m.reply("Вопрос отправлен в канал.", parse_mode=None)
    except TelegramForbiddenError:
        await m.reply(
            "Нет прав писать в канал. Проверь право администратора "
            "«Публиковать сообщения».",
            parse_mode=None,
        )
    except (TelegramBadRequest, Exception) as e:
        logger.exception(f"/next — ошибка: {e}")
        await m.reply(f"Ошибка отправки: {e}", parse_mode=None)


@dp.message(Command(commands=["nextfact"]))
async def cmd_nextfact(m: types.Message):
    try:
        await send_next_fact(m.bot)
        await m.reply("Факт отправлен в канал.", parse_mode=None)
    except (TelegramBadRequest, Exception) as e:
        logger.exception(f"/nextfact — ошибка: {e}")
        await m.reply(f"Ошибка отправки факта: {e}", parse_mode=None)


@dp.message(Command(commands=["status"]))
async def cmd_status(m: types.Message):
    await m.reply(
        f"Вопросов: {len(questions)} | Текущий индекс вопроса: {index}\n"
        f"Фактов: {len(facts)} | Текущий индекс факта: {facts_index}\n"
        f"Конфиг загружен: {'Да' if CONFIG else 'Нет'}",
        parse_mode=None,
    )


@dp.message(Command(commands=["schedule", "расписание"]))
async def cmd_schedule(m: types.Message):
    """Показать текущее расписание."""
    if not SCHEDULE and not FACT_SCHEDULE:
        await m.reply("Расписание не загружено или пустое.", parse_mode=None)
        return
    
    text = "📅 Текущее расписание:\n\n"
    
    if SCHEDULE:
        times = [t.strftime("%H:%M") for t in SCHEDULE]
        text += f"• Вопросы: {', '.join(times)}\n"
    
    if FACT_SCHEDULE:
        times = [t.strftime("%H:%M") for t in FACT_SCHEDULE]
        text += f"• Факты: {', '.join(times)}\n"
    
    random_delay = CONFIG.get("settings", {}).get("random_delay_minutes", 0)
    if random_delay > 0:
        text += f"\n⏰ Случайная задержка: до {random_delay} мин."
    
    text += f"\n\nФайл конфигурации: {CONFIG_FILE}"
    await m.reply(text, parse_mode=None)


@dp.message(Command(commands=["nexttime", "nextschedule"]))
async def cmd_next_time(m: types.Message):
    """Показать, когда следующая отправка."""
    if not SCHEDULE and not FACT_SCHEDULE:
        await m.reply("Расписание не настроено.", parse_mode=None)
        return
    
    text = "⏰ Следующая отправка:\n\n"
    
    if SCHEDULE:
        next_q = min(seconds_until(t) for t in SCHEDULE)
        text += f"• Вопрос через: {format_seconds(next_q)}\n"
    
    if FACT_SCHEDULE:
        next_f = min(seconds_until(t) for t in FACT_SCHEDULE)
        text += f"• Факт через: {format_seconds(next_f)}\n"
    
    await m.reply(text, parse_mode=None)


@dp.message(Command(commands=["reloadconfig", "reloadcfg"]))
async def cmd_reload_config(m: types.Message):
    """Перезагрузить конфигурацию из файла."""
    global SCHEDULE, FACT_SCHEDULE, CONFIG
    
    try:
        CONFIG = load_config()
        
        # Очищаем расписания
        SCHEDULE.clear()
        FACT_SCHEDULE.clear()
        
        # Загружаем новые расписания из конфига
        for t_str in CONFIG["schedule"]["questions"]:
            t = datetime.strptime(t_str, "%H:%M").time()
            SCHEDULE.append(t)
        
        for t_str in CONFIG["schedule"]["facts"]:
            t = datetime.strptime(t_str, "%H:%M").time()
            FACT_SCHEDULE.append(t)
        
        await m.reply(
            f"✅ Конфигурация перезагружена.\n"
            f"• Вопросы: {len(SCHEDULE)} времени\n"
            f"• Факты: {len(FACT_SCHEDULE)} времени\n"
            f"• Файл: {CONFIG_FILE}\n"
            f"• Случайная задержка: {CONFIG.get('settings', {}).get('random_delay_minutes', 0)} мин.",
            parse_mode=None,
        )
    except Exception as e:
        logger.exception(f"/reloadconfig — ошибка: {e}")
        await m.reply(f"❌ Ошибка загрузки конфига: {e}", parse_mode=None)


# =========================================================
#                     ПЛАНИРОВЩИКИ
# =========================================================

async def question_scheduler(bot: Bot):
    """Планировщик автопубликации вопросов."""
    while True:
        try:
            if not SCHEDULE:
                await asyncio.sleep(60)
                continue
            
            wait = min(seconds_until(t) for t in SCHEDULE)
            
            # Добавляем случайную задержку если настроено
            random_delay = CONFIG.get("settings", {}).get("random_delay_minutes", 0)
            if random_delay > 0:
                random_seconds = random.randint(0, random_delay * 60)
                wait += random_seconds
                print(f"[SCHEDULE] Добавлена случайная задержка: {random_seconds} сек.")
            
            print(f"[SCHEDULE] Следующий вопрос через: {format_seconds(wait)}")
            await asyncio.sleep(wait)
            
            try:
                await send_next_question(bot)
                print("[SCHEDULE] Автопубликация вопроса: отправлено.")
            except Exception as e:
                logger.exception(f"Автопубликация вопроса — ошибка: {e}")
                print(f"[SCHEDULE] Ошибка автопубликации вопроса: {e}")
                
        except Exception as e:
            logger.exception(f"question_scheduler — критическая ошибка: {e}")
            await asyncio.sleep(5)


async def fact_scheduler(bot: Bot):
    """Планировщик автопубликации факта дня."""
    while True:
        try:
            if not FACT_SCHEDULE:
                await asyncio.sleep(60)
                continue
            
            wait = min(seconds_until(t) for t in FACT_SCHEDULE)
            
            # Добавляем случайную задержку если настроено
            random_delay = CONFIG.get("settings", {}).get("random_delay_minutes", 0)
            if random_delay > 0:
                random_seconds = random.randint(0, random_delay * 60)
                wait += random_seconds
                print(f"[SCHEDULE] Добавлена случайная задержка для факта: {random_seconds} сек.")
            
            print(f"[SCHEDULE] Следующий факт через: {format_seconds(wait)}")
            await asyncio.sleep(wait)
            
            try:
                await send_next_fact(bot)
                print("[SCHEDULE] Автопубликация факта: отправлено.")
            except Exception as e:
                logger.exception(f"Автопубликация факта — ошибка: {e}")
                print(f"[SCHEDULE] Ошибка автопубликации факта: {e}")
                
        except Exception as e:
            logger.exception(f"fact_scheduler — критическая ошибка: {e}")
            await asyncio.sleep(5)


# =========================================================
#                       ТОЧКА ВХОДА
# =========================================================

async def main():
    global questions, index, facts, facts_index, SCHEDULE, FACT_SCHEDULE, CONFIG

    async with Bot(TOKEN) as bot:
        # Проверяем подключение к Telegram
        for attempt in range(5):
            try:
                me = await bot.get_me()
                print(f"Бот авторизован как: {me.username}")
                break
            except TelegramNetworkError as e:
                backoff = min(5 * (2 ** attempt), 60)
                print(f"Сеть не готова ({e}). Повтор через {backoff} с.")
                await asyncio.sleep(backoff)
        else:
            raise RuntimeError("Не удалось соединиться с Telegram API.")

        # Загружаем конфигурацию
        CONFIG = load_config()
        
        # Загружаем расписания из конфига
        for t_str in CONFIG["schedule"]["questions"]:
            t = datetime.strptime(t_str, "%H:%M").time()
            SCHEDULE.append(t)
        
        for t_str in CONFIG["schedule"]["facts"]:
            t = datetime.strptime(t_str, "%H:%M").time()
            FACT_SCHEDULE.append(t)
        
        print(f"[CONFIG] Загружена конфигурация из {CONFIG_FILE}")
        print(f"  Вопросы: {[t.strftime('%H:%M') for t in SCHEDULE]}")
        print(f"  Факты: {[t.strftime('%H:%M') for t in FACT_SCHEDULE]}")
        print(f"  Часовой пояс: {CONFIG.get('settings', {}).get('timezone', 'Europe/Moscow')}")
        print(f"  Случайная задержка: {CONFIG.get('settings', {}).get('random_delay_minutes', 0)} мин.")

        # Загружаем вопросы и факты
        questions = load_questions_from_csv()
        facts = load_facts_from_csv()

        idx, fidx = load_state()

        if questions:
            index = min(idx, len(questions) - 1)
        else:
            index = 0

        if facts:
            facts_index = min(fidx, len(facts) - 1)
        else:
            facts_index = 0

        save_state(index, facts_index)

        print(
            f"Загружено вопросов: {len(questions)} | Индекс: {index}\n"
            f"Загружено фактов: {len(facts)} | Индекс факта: {facts_index}"
        )

        # Запускаем планировщики
        task_questions = asyncio.create_task(question_scheduler(bot))
        task_facts = asyncio.create_task(fact_scheduler(bot))

        try:
            await dp.start_polling(bot)
        finally:
            # Корректно гасим фоновые задачи
            for t in (task_questions, task_facts):
                if t and not t.done():
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await t


if __name__ == "__main__":
    asyncio.run(main())