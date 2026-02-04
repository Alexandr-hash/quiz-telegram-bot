"""
ЯДРО: ГЛАВНЫЙ КЛАСС БОТА (QUIZ BOT)
====================================
Центральный класс, который объединяет все компоненты системы:
- Сервисы данных и конфигурации
- Планировщики задач
- Обработчики команд Telegram
- Логирование и управление состоянием

Архитектура:
    QuizBot
    ├── ConfigService (конфигурация)
    ├── DataService (вопросы и факты)
    ├── StateService (состояние)
    ├── ImageService (изображения)
    ├── QuizScheduler (планирование)
    └── Telegram Bot (aiogram)
"""

import asyncio
import logging
from typing import Optional
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os

from src.services.config_service import ConfigService
from src.services.data_service import DataService
from src.services.state_service import StateService
from src.services.image_service import ImageService
from src.core.scheduler import QuizScheduler
from src.utils.logger import setup_logger
from src.config import ensure_directories


# Загрузка переменных окружения
load_dotenv()

# Инициализация логгеров
logger = setup_logger("quiz_bot")
error_logger = setup_logger("quiz_bot_errors", level=logging.ERROR)


class QuizBot:
    """
    ГЛАВНЫЙ КЛАСС ТЕЛЕГРАМ-БОТА ДЛЯ ВИКТОРИНЫ
    ========================================
    Координирует работу всех компонентов системы.
    Реализует паттерн "Фасад" - предоставляет простой интерфейс
    для сложной системы.
    
    Атрибуты:
        bot: Экземпляр aiogram Bot
        dp: Диспетчер aiogram
        config_service: Сервис конфигурации
        data_service: Сервис данных (вопросы/факты)
        state_service: Сервис состояния
        image_service: Сервис изображений
        scheduler: Главный планировщик задач
        channel_id: ID канала для публикации
        is_running: Флаг работы бота
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        channel_id: Optional[str] = None
    ):
        """
        ИНИЦИАЛИЗАЦИЯ БОТА
        ------------------
        Создает все необходимые сервисы и настраивает зависимости.
        
        Args:
            token: Токен Telegram бота (если None - берется из .env)
            channel_id: ID канала (если None - берется из .env)
            
        Raises:
            RuntimeError: Если не удалось загрузить токен или channel_id
        """
        logger.info("Инициализация QuizBot...")
        
        # Загрузка конфигурации из .env
        self.token = token or os.getenv("BOT_TOKEN")
        self.channel_id = channel_id or os.getenv("CHANNEL_ID")
        
        if not self.token:
            raise RuntimeError("BOT_TOKEN не найден. Укажите в .env или передайте в конструктор")
        
        if not self.channel_id:
            raise RuntimeError("CHANNEL_ID не найден. Укажите в .env или передайте в конструктор")
        
        # Создание необходимых директорий
        ensure_directories()
        
        # Инициализация aiogram (ОТЛОЖЕННО - создадим в start())
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        
        # Инициализация сервисов
        self.config_service = ConfigService()
        self.state_service = StateService()
        self.image_service = ImageService()
        self.data_service = DataService()
        
        # Планировщик будет создан после загрузки конфига
        self.scheduler: Optional[QuizScheduler] = None
        
        # Флаг работы
        self.is_running = False
        
        logger.info("QuizBot инициализирован успешно (aiogram отложен)")
    
    def _register_handlers(self) -> None:
        """
        ПРИВАТНЫЙ МЕТОД: РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
        ------------------------------------------
        Регистрирует все обработчики команд Telegram.
        """
        from src.handlers import register_admin_handlers
        
        # Регистрируем обработчики администратора
        register_admin_handlers(
            router=self.dp,
            quiz_bot=self,
            admin_ids=None  # TODO: Добавить список администраторов из конфига
        )
        
        logger.debug("Все обработчики команд зарегистрированы")
    
    async def _send_quiz_to_channel(self, question) -> bool:
        """
        ПРИВАТНЫЙ МЕТОД: ОТПРАВКА ВОПРОСА В КАНАЛ
        ------------------------------------------
        Отправляет вопрос викторины в Telegram-канал.
        
        Args:
            question: Объект Question для отправки
            
        Returns:
            True если успешно, False при ошибке
        """
        try:
            from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
            
            await self.bot.send_poll(
                chat_id=self.channel_id,
                question=question.text,
                options=question.options,
                type="quiz",
                correct_option_id=question.correct_index,
                explanation=question.explanation,
                is_anonymous=True
            )
            
            logger.info(f"Вопрос отправлен в канал: {question.text[:50]}...")
            return True
            
        except TelegramForbiddenError:
            error_logger.error(f"Нет доступа к каналу {self.channel_id}")
            return False
        except TelegramBadRequest as e:
            error_logger.error(f"Ошибка Telegram API: {e}")
            return False
        except Exception as e:
            error_logger.error(f"Неизвестная ошибка отправки вопроса: {e}")
            return False
    
    async def _send_fact_to_channel(self, fact) -> bool:
        """
        ПРИВАТНЫЙ МЕТОД: ОТПРАВКА ФАКТА В КАНАЛ
        ----------------------------------------
        Отправляет факт дня в Telegram-канал.
        Может отправлять с изображением или без.
        
        Args:
            fact: Объект Fact для отправки
            
        Returns:
            True если успешно, False при ошибке
        """
        try:
            from aiogram.types import FSInputFile
            from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
            
            fact_text = fact.format_text()
            
            # Пытаемся отправить с изображением если есть
            if fact.has_image:
                try:
                    photo = FSInputFile(str(fact.image_path))
                    await self.bot.send_photo(
                        chat_id=self.channel_id,
                        photo=photo,
                        caption=fact_text
                    )
                    logger.info(f"Факт с изображением отправлен: {fact.text[:50]}...")
                    return True
                except Exception as img_error:
                    error_logger.warning(
                        f"Не удалось отправить факт с изображением: {img_error}. "
                        f"Пробуем без изображения..."
                    )
            
            # Отправляем без изображения
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=fact_text
            )
            
            logger.info(f"Факт отправлен: {fact.text[:50]}...")
            return True
            
        except TelegramForbiddenError:
            error_logger.error(f"Нет доступа к каналу {self.channel_id}")
            return False
        except TelegramBadRequest as e:
            error_logger.error(f"Ошибка Telegram API: {e}")
            return False
        except Exception as e:
            error_logger.error(f"Неизвестная ошибка отправки факта: {e}")
            return False
    
    async def send_next_question(self) -> bool:
        """
        ОТПРАВКА СЛЕДУЮЩЕГО ВОПРОСА
        -----------------------------
        Основной метод для отправки вопроса.
        Используется планировщиком и командами администратора.
        
        Returns:
            True если успешно, False при ошибке
        """
        logger.info("Запрос на отправку следующего вопроса")
        
        if not self.data_service.is_loaded:
            logger.warning("Данные не загружены, пытаемся загрузить...")
            self.data_service.load_all()
        
        question = self.data_service.get_next_question()
        if not question:
            error_logger.error("Не удалось получить следующий вопрос")
            return False
        
        return await self._send_quiz_to_channel(question)
    
    async def send_next_fact(self) -> bool:
        """
        ОТПРАВКА СЛЕДУЮЩЕГО ФАКТА
        ---------------------------
        Основной метод для отправки факта.
        Используется планировщиком и командами администратора.
        
        Returns:
            True если успешно, False при ошибке
        """
        logger.info("Запрос на отправку следующего факта")
        
        if not self.data_service.is_loaded:
            logger.warning("Данные не загружены, пытаемся загрузить...")
            self.data_service.load_all()
        
        fact = self.data_service.get_next_fact()
        if not fact:
            error_logger.error("Не удалось получить следующий факт")
            return False
        
        return await self._send_fact_to_channel(fact)
    
    async def initialize(self) -> bool:
        """
        ИНИЦИАЛИЗАЦИЯ И ЗАГРУЗКА ДАННЫХ
        --------------------------------
        Выполняет первоначальную настройку:
        1. Создание aiogram объектов
        2. Загрузка конфигурации
        3. Загрузка данных (вопросы, факты)
        4. Создание планировщика
        5. Регистрация обработчиков
        
        Returns:
            True если успешно, False при ошибке
        """
        logger.info("Начало инициализации бота...")
        
        try:
            # 0. Создание aiogram объектов (теперь здесь)
            # ОБНОВЛЕНО для aiogram 3.7.0+
            from aiogram.client.default import DefaultBotProperties
            
            self.bot = Bot(
                token=self.token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            self.dp = Dispatcher()
            
            # Регистрация обработчиков
            self._register_handlers()
            
            # 1. Загрузка конфигурации
            config = self.config_service.load()
            logger.info(f"Конфигурация загружена: {len(config.schedule.questions)} вопросов, "
                       f"{len(config.schedule.facts)} фактов")
            
            # 2. Загрузка данных
            questions_count, facts_count = self.data_service.load_all()
            
            if questions_count == 0:
                logger.warning("Не загружено ни одного вопроса!")
            if facts_count == 0:
                logger.warning("Не загружено ни одного факта!")
            
            # 3. Создание планировщика
            self.scheduler = QuizScheduler(
                config_service=self.config_service,
                question_task=self.send_next_question,
                fact_task=self.send_next_fact
            )
            
            logger.info(
                f"Инициализация завершена: {questions_count} вопросов, "
                f"{facts_count} фактов, {self.image_service.count} изображений"
            )
            
            return True
            
        except Exception as e:
            error_logger.error(f"Ошибка инициализации бота: {e}")
            return False
    
    async def start(self) -> None:
        """
        ЗАПУСК БОТА
        ------------
        Основной метод запуска. Выполняет:
        1. Инициализацию
        2. Запуск планировщиков
        3. Запуск polling Telegram бота
        
        Raises:
            RuntimeError: Если инициализация не удалась
        """
        logger.info("Запуск QuizBot...")
        
        # Инициализация
        if not await self.initialize():
            raise RuntimeError("Не удалось инициализировать бота")
        
        # Запуск планировщиков
        if self.scheduler:
            await self.scheduler.start_all()
        
        self.is_running = True
        
        # Тестовая отправка (можно убрать в продакшене)
        await self._send_startup_message()
        
        logger.info("Бот запущен и готов к работе")
        
        try:
            # Запуск polling
            await self.dp.start_polling(self.bot)
        except Exception as e:
            error_logger.error(f"Ошибка в работе бота: {e}")
            raise
        finally:
            # Корректное завершение
            await self.stop()
    
    async def stop(self) -> None:
        """
        КОРРЕКТНАЯ ОСТАНОВКА БОТА
        --------------------------
        Останавливает все компоненты системы.
        """
        if not self.is_running:
            return
        
        logger.info("Остановка QuizBot...")
        
        self.is_running = False
        
        # Остановка планировщиков
        if self.scheduler:
            await self.scheduler.stop_all()
        
        # Закрытие сессии aiogram
        try:
            await self.bot.session.close()
        except Exception as e:
            error_logger.warning(f"Ошибка при закрытии сессии бота: {e}")
        
        logger.info("QuizBot остановлен")
    
    async def _send_startup_message(self) -> None:
        """
        ПРИВАТНЫЙ МЕТОД: ОТПРАВКА СООБЩЕНИЯ О ЗАПУСКЕ
        ----------------------------------------------
        Отправляет уведомление администратору о успешном запуске.
        """
        try:
            # Получаем статистику
            stats = self.data_service.get_stats()
            
            message = (
                "🚀 <b>QuizBot успешно запущен!</b>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Вопросов: {stats['questions']['total']}\n"
                f"• Фактов: {stats['facts']['total']}\n"
                f"• Изображений: {stats['images']['available']}\n\n"
                f"⏰ <b>Расписание:</b>\n"
                f"• Вопросы: {len(self.config_service.get_question_schedule())} раз в день\n"
                f"• Факты: {len(self.config_service.get_fact_schedule())} раз в день\n\n"
                "✅ Бот готов к работе!"
            )
            
            # Отправляем сообщение в лог (в реальности можно отправить администратору)
            logger.info("Сообщение о запуске подготовлено")
            
        except Exception as e:
            error_logger.warning(f"Не удалось подготовить сообщение о запуске: {e}")
    
    def get_status(self) -> dict:
        """
        ПОЛУЧЕНИЕ СТАТУСА БОТА
        -----------------------
        Возвращает детальную информацию о состоянии всех компонентов.
        
        Returns:
            Словарь со статусом всех компонентов
        """
        status = {
            "bot": {
                "is_running": self.is_running,
                "channel_id": self.channel_id,
                "initialized": self.data_service.is_loaded
            },
            "data": self.data_service.get_stats() if self.data_service.is_loaded else {},
            "config": {
                "loaded": self.config_service.config is not None,
                "question_schedule_count": len(self.config_service.get_question_schedule()),
                "fact_schedule_count": len(self.config_service.get_fact_schedule())
            },
            "images": {
                "available": self.image_service.count
            }
        }
        
        if self.scheduler:
            status["scheduler"] = self.scheduler.get_status_all()
        
        return status 
