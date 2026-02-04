"""
Структурированное логирование
"""
import logging
import sys
from pathlib import Path
from typing import Optional

# Импортируем константы путей
from src.config import LOGS_DIR, ERROR_LOG, BOT_SCHEDULER_LOG


def setup_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: int = logging.INFO
) -> logging.Logger:
    """
    Настраивает структурированный логгер.
    
    Args:
        name: Имя логгера
        log_file: Путь к файлу логов (если None - только консоль)
        level: Уровень логирования
        
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Форматтер с структурированным выводом
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Обработчик для файла (если указан)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Глобальные логгеры
error_logger = setup_logger("error", ERROR_LOG, logging.ERROR)
scheduler_logger = setup_logger("scheduler", BOT_SCHEDULER_LOG, logging.INFO)
bot_logger = setup_logger("bot", level=logging.INFO)


def log_command(user_id: int, command: str, success: bool = True):
    """
    Логирует выполнение команды.
    
    Args:
        user_id: ID пользователя
        command: Команда
        success: Успешно ли выполнена
    """
    bot_logger.info(
        f"command_executed user_id={user_id} command={command} success={success}"
    )


def log_question_sent(question_id: int, scheduled_time: str, actual_time: str):
    """
    Логирует отправку вопроса.
    
    Args:
        question_id: ID вопроса (индекс)
        scheduled_time: Запланированное время
        actual_time: Фактическое время отправки
    """
    scheduler_logger.info(
        f"question_sent id={question_id} scheduled={scheduled_time} actual={actual_time}"
    )


def log_fact_sent(fact_id: int, has_image: bool):
    """
    Логирует отправку факта.
    
    Args:
        fact_id: ID факта (индекс)
        has_image: Был ли отправлен с изображением
    """
    scheduler_logger.info(
        f"fact_sent id={fact_id} has_image={has_image}"
    ) 
