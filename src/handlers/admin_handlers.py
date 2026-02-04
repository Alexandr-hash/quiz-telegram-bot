"""
ОБРАБОТЧИКИ: КОМАНДЫ АДМИНИСТРАТОРА
====================================
Все команды управления ботом для администраторов.
Используют dependency injection для доступа к сервисам.

Команды:
    /start, /help    - Справка и руководство
    /reload          - Перезагрузить данные из CSV
    /next            - Отправить следующий вопрос сейчас
    /nextfact        - Отправить следующий факт сейчас
    /status          - Статистика и состояние
    /schedule        - Текущее расписание
    /nexttime        - Время следующей отправки
    /reloadconfig    - Перезагрузить конфигурацию
"""

import logging
from typing import Optional

from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from src.utils.logger import setup_logger
from src.utils.time_utils import format_seconds, seconds_until


# Инициализация логгеров
logger = setup_logger("admin_handlers")
error_logger = setup_logger("admin_handlers_errors", level=logging.ERROR)


def register_admin_handlers(
    router: Router,
    quiz_bot,
    admin_ids: Optional[list] = None
) -> None:
    """
    РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ АДМИНИСТРАТОРА
    ----------------------------------------
    Регистрирует все команды администратора в роутере.
    
    Args:
        router: Роутер aiogram для регистрации handlers
        quiz_bot: Экземпляр QuizBot (источник сервисов)
        admin_ids: Список ID администраторов (None = любой пользователь)
    """
    
    # Фильтр для проверки прав администратора
    def admin_filter(message: types.Message) -> bool:
        """Проверяет, является ли пользователь администратором"""
        if admin_ids is None:
            return True  # Любой пользователь
        return message.from_user.id in admin_ids
    
    # ================== КОМАНДА /start И /help ==================
    
    @router.message(Command(commands=["start", "help"]), admin_filter)
    async def cmd_start_help(message: types.Message):
        """
        ОБРАБОТЧИК: /start И /help
        ---------------------------
        Показывает справку по командам и информацию о боте.
        """
        try:
            user_id = message.from_user.id
            username = message.from_user.username or "без username"
            
            logger.info(f"Команда /help от пользователя {username} (ID: {user_id})")
            
            help_text = (
                "🤖 <b>Quiz Telegram Bot</b>\n\n"
                "📚 <b>Основные команды:</b>\n"
                "/start, /help - Эта справка\n"
                "/reload - Перезагрузить вопросы и факты\n"
                "/next - Отправить следующий вопрос сейчас\n"
                "/nextfact - Отправить следующий факт сейчас\n"
                "/status - Статистика и состояние бота\n"
                "/schedule - Текущее расписание\n"
                "/nexttime - Когда следующая отправка\n"
                "/reloadconfig - Перезагрузить конфигурацию\n\n"
                "⚙️ <b>Управление данными:</b>\n"
                "• Вопросы: data/questions.csv\n"
                "• Факты: data/facts.csv\n"
                "• Конфигурация: configs/config.json\n"
                "• Изображения: data/fact_images/\n\n"
                "📊 <b>Текущее состояние:</b>\n"
            )
            
            # Добавляем статистику если бот инициализирован
            if quiz_bot.data_service.is_loaded:
                stats = quiz_bot.data_service.get_stats()
                help_text += (
                    f"• Вопросов: {stats['questions']['total']}\n"
                    f"• Фактов: {stats['facts']['total']}\n"
                    f"• Изображений: {stats['images']['available']}\n"
                )
            else:
                help_text += "• Данные не загружены\n"
            
            await message.answer(help_text, parse_mode="HTML")
            
        except Exception as e:
            error_logger.error(f"Ошибка в команде /help: {e}")
            await message.answer("❌ Ошибка при выполнении команды")
    
    # ================== КОМАНДА /reload ==================
    
    @router.message(Command(commands=["reload"]), admin_filter)
    async def cmd_reload(message: types.Message):
        """
        ОБРАБОТЧИК: /reload
        --------------------
        Перезагружает все данные из CSV файлов.
        """
        try:
            await message.answer("🔄 Перезагрузка данных...")
            
            # Перезагружаем данные
            questions_count, facts_count = quiz_bot.data_service.reload()
            
            # Перезагружаем изображения
            images_count = quiz_bot.image_service.reload()
            
            response = (
                f"✅ <b>Данные перезагружены</b>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Вопросов: {questions_count}\n"
                f"• Фактов: {facts_count}\n"
                f"• Изображений: {images_count}\n\n"
            )
            
            if questions_count == 0:
                response += "⚠️ <i>Вопросы не загружены. Проверьте файл questions.csv</i>\n"
            if facts_count == 0:
                response += "⚠️ <i>Факты не загружены. Проверьте файл facts.csv</i>\n"
            
            await message.answer(response, parse_mode="HTML")
            logger.info(f"Данные перезагружены: {questions_count} вопросов, {facts_count} фактов")
            
        except Exception as e:
            error_logger.error(f"Ошибка в команде /reload: {e}")
            await message.answer("❌ Ошибка при перезагрузке данных")
    
    # ================== КОМАНДА /next ==================
    
    @router.message(Command(commands=["next"]), admin_filter)
    async def cmd_next(message: types.Message):
        """
        ОБРАБОТЧИК: /next
        ------------------
        Отправляет следующий вопрос в канал немедленно.
        """
        try:
            await message.answer("⏳ Отправка вопроса...")
            
            success = await quiz_bot.send_next_question()
            
            if success:
                stats = quiz_bot.data_service.get_stats()
                response = (
                    f"✅ <b>Вопрос отправлен в канал</b>\n\n"
                    f"📈 <b>Статистика отправок:</b>\n"
                    f"• Сегодня: {stats['questions']['sent_today']}\n"
                    f"• Всего: {stats['questions']['total_sent']}\n"
                    f"• Следующий индекс: {stats['questions']['current_index'] + 1}"
                )
                await message.answer(response, parse_mode="HTML")
            else:
                await message.answer("❌ <b>Не удалось отправить вопрос</b>\n"
                                   "Проверьте:\n"
                                   "1. Доступ к каналу\n"
                                   "2. Загружены ли вопросы\n"
                                   "3. Логи ошибок", parse_mode="HTML")
            
        except Exception as e:
            error_logger.error(f"Ошибка в команде /next: {e}")
            await message.answer("❌ Ошибка при отправке вопроса")
    
    # ================== КОМАНДА /nextfact ==================
    
    @router.message(Command(commands=["nextfact"]), admin_filter)
    async def cmd_nextfact(message: types.Message):
        """
        ОБРАБОТЧИК: /nextfact
        -----------------------
        Отправляет следующий факт в канал немедленно.
        """
        try:
            await message.answer("⏳ Отправка факта...")
            
            success = await quiz_bot.send_next_fact()
            
            if success:
                stats = quiz_bot.data_service.get_stats()
                response = (
                    f"✅ <b>Факт отправлен в канал</b>\n\n"
                    f"📈 <b>Статистика отправок:</b>\n"
                    f"• Сегодня: {stats['facts']['sent_today']}\n"
                    f"• Всего: {stats['facts']['total_sent']}\n"
                    f"• Следующий индекс: {stats['facts']['current_index'] + 1}"
                )
                await message.answer(response, parse_mode="HTML")
            else:
                await message.answer("❌ <b>Не удалось отправить факт</b>\n"
                                   "Проверьте:\n"
                                   "1. Доступ к каналу\n"
                                   "2. Загружены ли факты\n"
                                   "3. Логи ошибок", parse_mode="HTML")
            
        except Exception as e:
            error_logger.error(f"Ошибка в команде /nextfact: {e}")
            await message.answer("❌ Ошибка при отправке факта")
    
    # ================== КОМАНДА /status ==================
    
    @router.message(Command(commands=["status", "stats"]), admin_filter)
    async def cmd_status(message: types.Message):
        """
        ОБРАБОТЧИК: /status
        --------------------
        Показывает детальную статистику и состояние бота.
        """
        try:
            # Получаем статус из бота
            status = quiz_bot.get_status()
            
            response = "📊 <b>СТАТУС БОТА</b>\n\n"
            
            # Общая информация
            response += "🤖 <b>Общее состояние:</b>\n"
            response += f"• Работает: {'✅ Да' if status['bot']['is_running'] else '❌ Нет'}\n"
            response += f"• Канал: {status['bot']['channel_id']}\n"
            response += f"• Данные загружены: {'✅ Да' if status['bot']['initialized'] else '❌ Нет'}\n\n"
            
            # Данные
            if status['bot']['initialized']:
                response += "📚 <b>Данные:</b>\n"
                response += f"• Вопросов: {status['data']['questions']['total']}\n"
                response += f"• Фактов: {status['data']['facts']['total']}\n"
                response += f"• Изображений: {status['data']['images']['available']}\n\n"
                
                response += "📈 <b>Статистика отправок:</b>\n"
                response += f"• Вопросов сегодня: {status['data']['questions']['sent_today']}\n"
                response += f"• Фактов сегодня: {status['data']['facts']['sent_today']}\n"
                response += f"• Всего вопросов: {status['data']['questions']['total_sent']}\n"
                response += f"• Всего фактов: {status['data']['facts']['total_sent']}\n\n"
            
            # Конфигурация
            response += "⏰ <b>Конфигурация:</b>\n"
            response += f"• Загружена: {'✅ Да' if status['config']['loaded'] else '❌ Нет'}\n"
            response += f"• Время вопросов: {status['config']['question_schedule_count']}\n"
            response += f"• Время фактов: {status['config']['fact_schedule_count']}\n\n"
            
            # Планировщик
            if 'scheduler' in status:
                response += "🔄 <b>Планировщик:</b>\n"
                for task_name, task_status in status['scheduler'].items():
                    running = '✅ Работает' if task_status['is_running'] else '❌ Остановлен'
                    response += f"• {task_name}: {running}\n"
            
            await message.answer(response, parse_mode="HTML")
            
        except Exception as e:
            error_logger.error(f"Ошибка в команде /status: {e}")
            await message.answer("❌ Ошибка при получении статуса")
    
    # ================== КОМАНДА /schedule ==================
    
    @router.message(Command(commands=["schedule", "расписание"]), admin_filter)
    async def cmd_schedule(message: types.Message):
        """
        ОБРАБОТЧИК: /schedule
        -----------------------
        Показывает текущее расписание отправки вопросов и фактов.
        """
        try:
            config = quiz_bot.config_service.config
            
            if not config:
                await message.answer("❌ Конфигурация не загружена")
                return
            
            response = "📅 <b>ТЕКУЩЕЕ РАСПИСАНИЕ</b>\n\n"
            
            # Расписание вопросов
            response += "🧠 <b>Вопросы:</b>\n"
            if config.schedule.questions:
                times = config.schedule.questions
                response += f"• {', '.join(times)}\n"
            else:
                response += "• Не настроено\n"
            
            # Расписание фактов
            response += "\n📚 <b>Факты:</b>\n"
            if config.schedule.facts:
                times = config.schedule.facts
                response += f"• {', '.join(times)}\n"
            else:
                response += "• Не настроено\n"
            
            # Настройки
            response += "\n⚙️ <b>Настройки:</b>\n"
            response += f"• Часовой пояс: {config.settings.timezone}\n"
            response += f"• Случайная задержка: {config.settings.random_delay_minutes} мин.\n"
            response += f"• Макс. вопросов в день: {config.settings.max_questions_per_day}\n"
            response += f"• Пропуск выходных: {'✅ Да' if config.settings.skip_weekends else '❌ Нет'}\n"
            
            await message.answer(response, parse_mode="HTML")
            
        except Exception as e:
            error_logger.error(f"Ошибка в команде /schedule: {e}")
            await message.answer("❌ Ошибка при получении расписания")
    
    # ================== КОМАНДА /nexttime ==================
    
    @router.message(Command(commands=["nexttime", "nextschedule"]), admin_filter)
    async def cmd_nexttime(message: types.Message):
        """
        ОБРАБОТЧИК: /nexttime
        -----------------------
        Показывает, когда следующая отправка вопросов и фактов.
        """
        try:
            from datetime import datetime
            
            question_schedule = quiz_bot.config_service.get_question_schedule()
            fact_schedule = quiz_bot.config_service.get_fact_schedule()
            
            response = "⏰ <b>СЛЕДУЮЩАЯ ОТПРАВКА</b>\n\n"
            
            # Следующий вопрос
            if question_schedule:
                next_q_seconds = min(seconds_until(t) for t in question_schedule)
                response += f"🧠 <b>Вопрос:</b> через {format_seconds(next_q_seconds)}\n"
            else:
                response += "🧠 <b>Вопрос:</b> не запланирован\n"
            
            # Следующий факт
            if fact_schedule:
                next_f_seconds = min(seconds_until(t) for t in fact_schedule)
                response += f"📚 <b>Факт:</b> через {format_seconds(next_f_seconds)}\n"
            else:
                response += "📚 <b>Факт:</b> не запланирован\n"
            
            # Текущее время
            current_time = datetime.now().strftime("%H:%M:%S")
            response += f"\n🕐 <b>Текущее время:</b> {current_time}"
            
            await message.answer(response, parse_mode="HTML")
            
        except Exception as e:
            error_logger.error(f"Ошибка в команде /nexttime: {e}")
            await message.answer("❌ Ошибка при расчете следующего времени")
    
    # ================== КОМАНДА /reloadconfig ==================
    
    @router.message(Command(commands=["reloadconfig", "reloadcfg"]), admin_filter)
    async def cmd_reloadconfig(message: types.Message):
        """
        ОБРАБОТЧИК: /reloadconfig
        ---------------------------
        Перезагружает конфигурацию из файла config.json.
        """
        try:
            await message.answer("🔄 Перезагрузка конфигурации...")
            
            # Перезагружаем конфигурацию
            config = quiz_bot.config_service.load()
            
            # Обновляем планировщик если он существует
            if quiz_bot.scheduler:
                quiz_bot.scheduler._apply_config_limits()
            
            response = (
                f"✅ <b>Конфигурация перезагружена</b>\n\n"
                f"📅 <b>Новое расписание:</b>\n"
                f"• Вопросы: {len(config.schedule.questions)} времени\n"
                f"• Факты: {len(config.schedule.facts)} времени\n\n"
                f"⚙️ <b>Настройки:</b>\n"
                f"• Часовой пояс: {config.settings.timezone}\n"
                f"• Случайная задержка: {config.settings.random_delay_minutes} мин.\n"
                f"• Макс. вопросов: {config.settings.max_questions_per_day}/день\n"
            )
            
            await message.answer(response, parse_mode="HTML")
            logger.info("Конфигурация перезагружена")
            
        except Exception as e:
            error_logger.error(f"Ошибка в команде /reloadconfig: {e}")
            await message.answer("❌ Ошибка при перезагрузке конфигурации")
    
    logger.info("Обработчики администратора зарегистрированы") 
