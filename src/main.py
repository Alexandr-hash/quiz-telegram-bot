"""
ТОЧКА ВХОДА: ОСНОВНОЙ ЗАПУСК БОТА
==================================
Главный файл для запуска бота. Содержит:
- Обработку аргументов командной строки
- Настройку логирования
- Запуск и обработку исключений
- Graceful shutdown
"""

import asyncio
import signal
import sys
from pathlib import Path

from src.core.bot import QuizBot
from src.utils.logger import setup_logger


# Настройка логгера
logger = setup_logger("main")


def setup_signal_handlers(bot: QuizBot):
    """
    НАСТРОЙКА ОБРАБОТКИ СИГНАЛОВ
    -----------------------------
    Обрабатывает сигналы завершения (Ctrl+C, системный shutdown).
    """
    def signal_handler(signum, frame):
        logger.info(f"Получен сигнал {signum}, остановка бота...")
        asyncio.create_task(bot.stop())
    
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main_async():
    """
    АСИНХРОННАЯ ОСНОВНАЯ ФУНКЦИЯ
    -----------------------------
    Основная логика запуска бота.
    """
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК QUIZ TELEGRAM BOT")
    logger.info("=" * 50)
    
    # Проверка наличия .env файла
    env_file = Path(".env")
    if not env_file.exists():
        logger.warning("Файл .env не найден!")
        logger.info("Создайте .env файл на основе templates/.env.example")
    
    try:
        # Создание экземпляра бота
        bot = QuizBot()
        logger.info("✅ Бот создан успешно")
         
         # Запуск health-check сервера в отдельном потоке
        try:
            import threading
            from src.health import start_health_server
            
            health_thread = threading.Thread(
                target=start_health_server,
                args=(8080,),  # Порт можно изменить
                daemon=True  # Демон-поток, завершается с главным
            )
            health_thread.start()
            logger.info("✅ Health-check сервер запущен на порту 8080")
        except ImportError:
            logger.warning("Модуль health не найден, health-check сервер не запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска health-check сервера: {e}")
        # Настройка обработки сигналов
        setup_signal_handlers(bot)
        
        # Запуск бота
        logger.info("Запуск основного цикла бота...")
        await bot.start()
        
    except RuntimeError as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Остановка по запросу пользователя (Ctrl+C)")
        return 0
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    logger.info("Бот завершил работу")
    return 0


def main():
    """
    ГЛАВНАЯ ФУНКЦИЯ ТОЧКИ ВХОДА
    ----------------------------
    Точка входа для синхронного вызова.
    """
    try:
        # Запуск асинхронной главной функции
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Приложение остановлено")
        return 0
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        return 1


if __name__ == "__main__":
    # Запуск приложения
    exit_code = main()
    sys.exit(exit_code)
