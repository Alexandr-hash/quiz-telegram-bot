"""
Сервис для работы с конфигурацией (Pydantic валидация)
"""
import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import time

from src.config import CONFIG_FILE
from src.utils.logger import setup_logger


logger = setup_logger("config_service")


# ---------- Pydantic модели для валидации ----------
class ScheduleConfig(BaseModel):
    """Конфигурация расписания"""
    questions: List[str] = Field(default=["10:00", "14:00", "18:00"])
    facts: List[str] = Field(default=["12:00"])
    
    @validator('questions', 'facts', each_item=True)
    def validate_time_format(cls, v):
        """Валидация формата времени HH:MM"""
        try:
            hours, minutes = map(int, v.split(':'))
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError
            return v
        except (ValueError, AttributeError):
            raise ValueError(f"Некорректный формат времени: {v}. Ожидается HH:MM")


class BotSettings(BaseModel):
    """Настройки бота"""
    timezone: str = Field(default="Europe/Moscow")
    random_delay_minutes: int = Field(default=0, ge=0, le=60)
    max_questions_per_day: int = Field(default=3, ge=1, le=50)
    skip_weekends: bool = Field(default=False)


class MessagesConfig(BaseModel):
    """Конфигурация сообщений"""
    fact_header: str = Field(default="📚 ФАКТ ДНЯ\n\n")
    question_header: str = Field(default="🧠 ВИКТОРИНА\n\n")


class BotConfig(BaseModel):
    """Полная конфигурация бота"""
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    settings: BotSettings = Field(default_factory=BotSettings)
    messages: MessagesConfig = Field(default_factory=MessagesConfig)


class ConfigService:
    """
    Сервис для управления конфигурацией бота.
    Использует Pydantic для валидации и сериализации.
    """
    
    def __init__(self, config_path: Path = CONFIG_FILE):
        self.config_path = config_path
        self.config: Optional[BotConfig] = None
        self._schedules_cache = {}  # Кэш расписаний в формате time
        
    def load(self) -> BotConfig:
        """
        Загружает и валидирует конфигурацию.
        
        Returns:
            Валидированная конфигурация
            
        Raises:
            ValueError: Если конфигурация некорректна
            FileNotFoundError: Если файл не найден
        """
        try:
            if not self.config_path.exists():
                logger.warning(f"Файл конфигурации не найден: {self.config_path}")
                # Создаем конфиг по умолчанию
                self.config = self._create_default_config()
                self.save()
                return self.config
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
            
            # Валидация через Pydantic
            self.config = BotConfig(**raw_config)
            logger.info(f"Конфигурация загружена из {self.config_path}")
            
            # Кэшируем расписания в формате time
            self._cache_schedules()
            
            return self.config
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            raise ValueError(f"Некорректный JSON в {self.config_path}")
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            raise
    
    def save(self, config: Optional[BotConfig] = None) -> None:
        """
        Сохраняет конфигурацию в файл.
        
        Args:
            config: Конфигурация для сохранения (если None - сохраняет текущую)
        """
        if config:
            self.config = config
        
        if not self.config:
            raise ValueError("Нет конфигурации для сохранения")
        
        try:
            # Создаем директорию если нужно
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Сериализуем через Pydantic
            config_dict = self.config.dict(exclude_unset=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Конфигурация сохранена в {self.config_path}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
            raise
    
    def _create_default_config(self) -> BotConfig:
        """Создает конфигурацию по умолчанию"""
        logger.info("Создание конфигурации по умолчанию")
        return BotConfig()
    
    def _cache_schedules(self) -> None:
        """Кэширует расписания в формате time для быстрого доступа"""
        if not self.config:
            return
        
        from src.utils.time_utils import parse_time_str
        
        self._schedules_cache = {
            'questions': [
                parse_time_str(t) for t in self.config.schedule.questions
                if parse_time_str(t) is not None
            ],
            'facts': [
                parse_time_str(t) for t in self.config.schedule.facts
                if parse_time_str(t) is not None
            ]
        }
    
    def get_question_schedule(self) -> List[time]:
        """Возвращает расписание вопросов в формате time"""
        return self._schedules_cache.get('questions', [])
    
    def get_fact_schedule(self) -> List[time]:
        """Возвращает расписание фактов в формате time"""
        return self._schedules_cache.get('facts', [])
    
    def get_random_delay_seconds(self) -> int:
        """Возвращает максимальную случайную задержку в секундах"""
        if self.config:
            return self.config.settings.random_delay_minutes * 60
        return 0
    
    def validate_and_fix(self) -> List[str]:
        """
        Валидирует конфигурацию и возвращает список проблем.
        
        Returns:
            Список сообщений о проблемах (пустой если все ок)
        """
        problems = []
        
        try:
            config = self.load()
            
            # Проверка дубликатов в расписании
            if len(config.schedule.questions) != len(set(config.schedule.questions)):
                problems.append("Найдены дубликаты во времени отправки вопросов")
            
            if len(config.schedule.facts) != len(set(config.schedule.facts)):
                problems.append("Найдены дубликаты во времени отправки фактов")
            
            # Проверка максимального количества вопросов
            if config.settings.max_questions_per_day < len(config.schedule.questions):
                problems.append(
                    f"max_questions_per_day ({config.settings.max_questions_per_day}) "
                    f"меньше количества запланированных отправок ({len(config.schedule.questions)})"
                )
            
            return problems
            
        except Exception as e:
            problems.append(f"Критическая ошибка валидации: {e}")
            return problems 
