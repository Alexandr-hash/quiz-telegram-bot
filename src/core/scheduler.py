"""
ЯДРО: ПЛАНИРОВЩИК ЗАДАЧ (SCHEDULER)
====================================
Отвечает за автоматическую отправку вопросов и фактов по расписанию.
Использует асинхронные задачи с учетом случайных задержек и настроек.

Особенности:
- Поддержка случайных задержек для естественности
- Пропуск выходных дней если настроено
- Обработка ошибок с повторными попытками
- Детальное логирование всех событий
"""

import asyncio
import random
from datetime import datetime, time
from typing import List, Optional, Callable, Awaitable, Any
import logging

from src.services.config_service import ConfigService
from src.utils.time_utils import seconds_until, format_seconds
from src.utils.logger import setup_logger


# Инициализация логгеров
logger = setup_logger("scheduler")
error_logger = setup_logger("scheduler_errors", level=logging.ERROR)


class TaskScheduler:
    """
    УНИВЕРСАЛЬНЫЙ ПЛАНИРОВЩИК ЗАДАЧ
    ===============================
    Управляет выполнением задач по расписанию с поддержкой:
    - Множественных временных слотов
    - Случайных задержек
    - Пропуска выходных
    - Ограничения количества выполнений
    
    Атрибуты:
        config_service: Сервис конфигурации
        task_function: Функция для выполнения (async)
        schedule: Расписание времени выполнения
        task_name: Имя задачи для логирования
        max_executions_per_day: Максимальное количество выполнений в день
        executions_today: Счетчик выполнений сегодня
        last_execution_date: Дата последнего выполнения
        is_running: Флаг работы планировщика
    """
    
    def __init__(
        self,
        config_service: ConfigService,
        task_function: Callable[[], Awaitable[Any]],
        schedule: List[time],
        task_name: str = "unknown_task"
    ):
        """
        ИНИЦИАЛИЗАЦИЯ ПЛАНИРОВЩИКА
        ---------------------------
        Args:
            config_service: Сервис для получения настроек
            task_function: Асинхронная функция для выполнения
            schedule: Список времен выполнения (объекты time)
            task_name: Имя задачи для логирования
        """
        self.config_service = config_service
        self.task_function = task_function
        self.schedule = schedule
        self.task_name = task_name
        
        # Состояние выполнения
        self.max_executions_per_day = 0  # 0 = без ограничений
        self.executions_today = 0
        self.last_execution_date: Optional[datetime] = None
        self.is_running = False
        
        logger.info(f"Создан планировщик для задачи '{task_name}'")
    
    async def start(self) -> None:
        """
        ЗАПУСК ПЛАНИРОВЩИКА
        --------------------
        Запускает бесконечный цикл планирования и выполнения задач.
        Обрабатывает ошибки и продолжает работу после сбоев.
        
        Пример:
            >>> scheduler = TaskScheduler(...)
            >>> await scheduler.start()  # Запускает в фоновом режиме
        """
        self.is_running = True
        logger.info(f"Запуск планировщика задачи '{self.task_name}'")
        
        while self.is_running:
            try:
                await self._run_scheduled_task()
            except asyncio.CancelledError:
                logger.info(f"Планировщик задачи '{self.task_name}' остановлен")
                break
            except Exception as e:
                error_logger.error(
                    f"Критическая ошибка в планировщике '{self.task_name}': {e}"
                )
                await asyncio.sleep(60)  # Пауза после критической ошибки
    
    async def stop(self) -> None:
        """
        ОСТАНОВКА ПЛАНИРОВЩИКА
        -----------------------
        Безопасно останавливает выполнение планировщика.
        """
        self.is_running = False
        logger.info(f"Остановка планировщика задачи '{self.task_name}'")
    
    async def _run_scheduled_task(self) -> None:
        """
        ПРИВАТНЫЙ МЕТОД: ВЫПОЛНЕНИЕ ПО РАСПИСАНИЮ
        ------------------------------------------
        Основной цикл: ждет следующего времени, проверяет условия, выполняет задачу.
        """
        if not self.schedule:
            logger.warning(f"Пустое расписание для задачи '{self.task_name}'")
            await asyncio.sleep(60)
            return
        
        # Проверяем сброс дневного счетчика
        self._reset_daily_counter_if_needed()
        
        # Проверяем ограничение по количеству выполнений
        if self._is_execution_limit_reached():
            logger.debug(f"Достигнут лимит выполнений для '{self.task_name}' сегодня")
            await asyncio.sleep(3600)  # Ждем час перед следующей проверкой
            return
        
        # Проверяем выходные дни если настроено
        if self._should_skip_due_to_weekend():
            logger.debug(f"Пропуск выполнения '{self.task_name}' в выходной день")
            await asyncio.sleep(3600)
            return
        
        # Рассчитываем время до следующего выполнения
        wait_seconds = self._calculate_wait_time()
        
        if wait_seconds > 0:
            logger.debug(
                f"Задача '{self.task_name}': следующее выполнение через {format_seconds(wait_seconds)}"
            )
            await asyncio.sleep(wait_seconds)
        
        # Выполняем задачу
        await self._execute_task()
    
    def _reset_daily_counter_if_needed(self) -> None:
        """
        ПРИВАТНЫЙ МЕТОД: СБРОС ДНЕВНОГО СЧЕТЧИКА
        -----------------------------------------
        Сбрасывает счетчик выполнений если наступил новый день.
        """
        today = datetime.now().date()
        
        if self.last_execution_date is None:
            self.last_execution_date = datetime.now()
            self.executions_today = 0
        elif self.last_execution_date.date() != today:
            logger.debug(f"Сброс дневного счетчика для '{self.task_name}'")
            self.executions_today = 0
            self.last_execution_date = datetime.now()
    
    def _is_execution_limit_reached(self) -> bool:
        """
        ПРИВАТНЫЙ МЕТОД: ПРОВЕРКА ЛИМИТА ВЫПОЛНЕНИЙ
        --------------------------------------------
        Проверяет, достигнуто ли максимальное количество выполнений за день.
        
        Returns:
            True если лимит достигнут, иначе False
        """
        if self.max_executions_per_day <= 0:
            return False
        
        return self.executions_today >= self.max_executions_per_day
    
    def _should_skip_due_to_weekend(self) -> bool:
        """
        ПРИВАТНЫЙ МЕТОД: ПРОВЕРКА ВЫХОДНЫХ ДНЕЙ
        ----------------------------------------
        Проверяет, нужно ли пропустить выполнение в выходной день.
        
        Returns:
            True если сегодня выходной и пропуск включен, иначе False
        """
        try:
            config = self.config_service.config
            if config and config.settings.skip_weekends:
                today_weekday = datetime.now().weekday()  # 0=понедельник, 6=воскресенье
                return today_weekday >= 5  # 5=суббота, 6=воскресенье
        except Exception as e:
            error_logger.error(f"Ошибка проверки выходных дней: {e}")
        
        return False
    
    def _calculate_wait_time(self) -> float:
        """
        ПРИВАТНЫЙ МЕТОД: РАСЧЕТ ВРЕМЕНИ ОЖИДАНИЯ
        -----------------------------------------
        Рассчитывает время до следующего выполнения с учетом случайной задержки.
        
        Returns:
            Количество секунд до следующего выполнения
        """
        if not self.schedule:
            return 3600  # 1 час по умолчанию если расписания нет
        
        # Находим ближайшее время в расписании
        min_wait = min(seconds_until(t) for t in self.schedule)
        
        # Добавляем случайную задержку если настроено
        random_delay = self._get_random_delay_seconds()
        if random_delay > 0:
            wait_with_delay = min_wait + random_delay
            logger.debug(
                f"Добавлена случайная задержка: {random_delay} сек. "
                f"(общее время: {format_seconds(wait_with_delay)})"
            )
            return wait_with_delay
        
        return min_wait
    
    def _get_random_delay_seconds(self) -> int:
        """
        ПРИВАТНЫЙ МЕТОД: ПОЛУЧЕНИЕ СЛУЧАЙНОЙ ЗАДЕРЖКИ
        ----------------------------------------------
        Возвращает случайную задержку в секундах из конфигурации.
        
        Returns:
            Случайное количество секунд задержки (0 если не настроено)
        """
        try:
            config = self.config_service.config
            if config:
                delay_minutes = config.settings.random_delay_minutes
                if delay_minutes > 0:
                    return random.randint(0, delay_minutes * 60)
        except Exception as e:
            error_logger.error(f"Ошибка получения случайной задержки: {e}")
        
        return 0
    
    async def _execute_task(self) -> None:
        """
        ПРИВАТНЫЙ МЕТОД: ВЫПОЛНЕНИЕ ЗАДАЧИ
        -----------------------------------
        Выполняет основную задачу с обработкой ошибок и логированием.
        """
        logger.info(f"Выполнение задачи '{self.task_name}'")
        
        try:
            # Выполняем задачу
            start_time = datetime.now()
            await self.task_function()
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Обновляем статистику
            self.executions_today += 1
            self.last_execution_date = datetime.now()
            
            logger.info(
                f"Задача '{self.task_name}' успешно выполнена "
                f"(время: {execution_time:.2f} сек., "
                f"сегодня: {self.executions_today})"
            )
            
        except asyncio.CancelledError:
            raise  # Пробрасываем выше для корректной остановки
        except Exception as e:
            error_logger.error(f"Ошибка выполнения задачи '{self.task_name}': {e}")
            # Не увеличиваем счетчик при ошибке
    
    def get_status(self) -> dict:
        """
        ПОЛУЧЕНИЕ СТАТУСА ПЛАНИРОВЩИКА
        --------------------------------
        Возвращает текущее состояние планировщика.
        
        Returns:
            Словарь со статусом:
            {
                "task_name": имя задачи,
                "is_running": работает ли,
                "schedule_count": количество временных слотов,
                "executions_today": выполнений сегодня,
                "last_execution": время последнего выполнения,
                "next_execution": время следующего выполнения
            }
        """
        next_execution = "не определено"
        if self.schedule:
            wait_seconds = min(seconds_until(t) for t in self.schedule)
            next_execution = f"через {format_seconds(wait_seconds)}"
        
        return {
            "task_name": self.task_name,
            "is_running": self.is_running,
            "schedule_count": len(self.schedule),
            "executions_today": self.executions_today,
            "last_execution": (
                self.last_execution_date.isoformat()
                if self.last_execution_date else "никогда"
            ),
            "next_execution": next_execution,
            "max_executions_per_day": self.max_executions_per_day
        }


class QuizScheduler:
    """
    ГЛАВНЫЙ ПЛАНИРОВЩИК ВИКТОРИНЫ
    ==============================
    Координирует работу нескольких планировщиков:
    - Планировщик вопросов
    - Планировщик фактов
    
    Предоставляет единый интерфейс для управления всеми задачами.
    """
    
    def __init__(
        self,
        config_service: ConfigService,
        question_task: Callable[[], Awaitable[Any]],
        fact_task: Callable[[], Awaitable[Any]]
    ):
        """
        ИНИЦИАЛИЗАЦИЯ ГЛАВНОГО ПЛАНИРОВЩИКА
        ------------------------------------
        Args:
            config_service: Сервис конфигурации
            question_task: Функция отправки вопроса
            fact_task: Функция отправки факта
        """
        self.config_service = config_service
        
        # Получаем расписания из конфигурации
        question_schedule = config_service.get_question_schedule()
        fact_schedule = config_service.get_fact_schedule()
        
        # Создаем планировщики для каждой задачи
        self.question_scheduler = TaskScheduler(
            config_service=config_service,
            task_function=question_task,
            schedule=question_schedule,
            task_name="question_sender"
        )
        
        self.fact_scheduler = TaskScheduler(
            config_service=config_service,
            task_function=fact_task,
            schedule=fact_schedule,
            task_name="fact_sender"
        )
        
        # Устанавливаем ограничения из конфигурации
        self._apply_config_limits()
        
        logger.info(
            f"Создан главный планировщик: "
            f"{len(question_schedule)} времен вопросов, "
            f"{len(fact_schedule)} времен фактов"
        )
    
    def _apply_config_limits(self) -> None:
        """Применяет ограничения из конфигурации к планировщикам"""
        try:
            config = self.config_service.config
            if config:
                self.question_scheduler.max_executions_per_day = (
                    config.settings.max_questions_per_day
                )
        except Exception as e:
            error_logger.error(f"Ошибка применения ограничений конфигурации: {e}")
    
    async def start_all(self) -> None:
        """
        ЗАПУСК ВСЕХ ПЛАНИРОВЩИКОВ
        --------------------------
        Запускает все задачи планировщиков параллельно.
        """
        logger.info("Запуск всех планировщиков...")
        
        # Запускаем оба планировщика параллельно
        self.question_task = asyncio.create_task(self.question_scheduler.start())
        self.fact_task = asyncio.create_task(self.fact_scheduler.start())
        
        logger.info("Все планировщики запущены")
    
    async def stop_all(self) -> None:
        """
        ОСТАНОВКА ВСЕХ ПЛАНИРОВЩИКОВ
        -----------------------------
        Безопасно останавливает все задачи.
        """
        logger.info("Остановка всех планировщиков...")
        
        await self.question_scheduler.stop()
        await self.fact_scheduler.stop()
        
        # Отменяем задачи
        if hasattr(self, 'question_task'):
            self.question_task.cancel()
        if hasattr(self, 'fact_task'):
            self.fact_task.cancel()
        
        logger.info("Все планировщики остановлены")
    
    def get_status_all(self) -> dict:
        """
        ПОЛУЧЕНИЕ СТАТУСА ВСЕХ ПЛАНИРОВЩИКОВ
        -------------------------------------
        Возвращает статус всех задач.
        
        Returns:
            Словарь со статусами всех планировщиков
        """
        return {
            "question_scheduler": self.question_scheduler.get_status(),
            "fact_scheduler": self.fact_scheduler.get_status()
        }
    
    async def trigger_question_now(self) -> bool:
        """
        НЕМЕДЛЕННЫЙ ЗАПУСК ОТПРАВКИ ВОПРОСА
        ------------------------------------
        Выполняет отправку вопроса немедленно, вне расписания.
        
        Returns:
            True если успешно, False при ошибке
        """
        logger.info("Ручной запуск отправки вопроса")
        try:
            await self.question_scheduler.task_function()
            return True
        except Exception as e:
            error_logger.error(f"Ошибка ручного запуска вопроса: {e}")
            return False
    
    async def trigger_fact_now(self) -> bool:
        """
        НЕМЕДЛЕННЫЙ ЗАПУСК ОТПРАВКИ ФАКТА
        ----------------------------------
        Выполняет отправку факта немедленно, вне расписания.
        
        Returns:
            True если успешно, False при ошибке
        """
        logger.info("Ручной запуск отправки факта")
        try:
            await self.fact_scheduler.task_function()
            return True
        except Exception as e:
            error_logger.error(f"Ошибка ручного запуска факта: {e}")
            return False 
