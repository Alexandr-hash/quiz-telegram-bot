"""
Сервис для управления состоянием бота (state.json)
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from src.config import STATE_FILE
from src.utils.logger import setup_logger


logger = setup_logger("state_service")


@dataclass
class BotState:
    """Состояние бота"""
    question_index: int = 0
    fact_index: int = 0
    last_question_sent: Optional[str] = None
    last_fact_sent: Optional[str] = None
    questions_sent_today: int = 0
    facts_sent_today: int = 0
    total_questions_sent: int = 0
    total_facts_sent: int = 0
    
    def reset_daily_counts(self):
        """Сбрасывает дневные счетчики"""
        self.questions_sent_today = 0
        self.facts_sent_today = 0


class StateService:
    """
    Сервис для работы с состоянием бота.
    Использует датакласс для типизации.
    """
    
    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file
        self.state: Optional[BotState] = None
    
    def load(self) -> BotState:
        """
        Загружает состояние из файла.
        
        Returns:
            Загруженное состояние
            
        Raises:
            FileNotFoundError: Если файл не существует
            ValueError: Если данные некорректны
        """
        try:
            if not self.state_file.exists():
                logger.info(f"Файл состояния не найден: {self.state_file}")
                self.state = BotState()
                self.save()
                return self.state
            
            with open(self.state_file, 'r', encoding='utf-8') as f:
                raw_state = json.load(f)
            
            # КОНВЕРТАЦИЯ СТАРЫХ КЛЮЧЕЙ В НОВЫЕ
            # Старые ключи: 'index', 'facts_index'
            # Новые ключи: 'question_index', 'fact_index'
            converted_state = {}
            for key, value in raw_state.items():
                if key == 'index':
                    converted_state['question_index'] = value
                elif key == 'facts_index':
                    converted_state['fact_index'] = value
                else:
                    converted_state[key] = value
            
            # Десериализация с проверкой полей
            self.state = BotState(**converted_state)
            logger.info(f"Состояние загружено из {self.state_file}")
            
            return self.state
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON состояния: {e}")
            self.state = BotState()
            return self.state
        except Exception as e:
            logger.error(f"Ошибка загрузки состояния: {e}")
            self.state = BotState()
            return self.state
    
    def save(self, state: Optional[BotState] = None) -> None:
        """
        Сохраняет состояние в файл.
        
        Args:
            state: Состояние для сохранения (если None - сохраняет текущее)
        """
        if state:
            self.state = state
        
        if not self.state:
            raise ValueError("Нет состояния для сохранения")
        
        try:
            # Создаем директорию если нужно
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Сериализуем через датакласс
            state_dict = asdict(self.state)
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_dict, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Состояние сохранено в {self.state_file}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}")
            raise
    
    def update_question_sent(self, question_index: int) -> None:
        """Обновляет состояние после отправки вопроса"""
        if not self.state:
            self.load()
        
        self.state.question_index = question_index
        self.state.last_question_sent = self._current_timestamp()
        self.state.questions_sent_today += 1
        self.state.total_questions_sent += 1
        
        self.save()
    
    def update_fact_sent(self, fact_index: int) -> None:
        """Обновляет состояние после отправки факта"""
        if not self.state:
            self.load()
        
        self.state.fact_index = fact_index
        self.state.last_fact_sent = self._current_timestamp()
        self.state.facts_sent_today += 1
        self.state.total_facts_sent += 1
        
        self.save()
    
    def get_next_question_index(self, total_questions: int) -> int:
        """
        Возвращает следующий индекс вопроса с учетом цикличности.
        
        Args:
            total_questions: Общее количество вопросов
            
        Returns:
            Следующий индекс вопроса
        """
        if not self.state:
            self.load()
        
        if total_questions == 0:
            return 0
        
        return self.state.question_index % total_questions
    
    def get_next_fact_index(self, total_facts: int) -> int:
        """
        Возвращает следующий индекс факта с учетом цикличности.
        
        Args:
            total_facts: Общее количество фактов
            
        Returns:
            Следующий индекс факта
        """
        if not self.state:
            self.load()
        
        if total_facts == 0:
            return 0
        
        return self.state.fact_index % total_facts
    
    def _current_timestamp(self) -> str:
        """Возвращает текущую метку времени"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику"""
        if not self.state:
            self.load()
        
        return {
            "question_index": self.state.question_index,
            "fact_index": self.state.fact_index,
            "questions_sent_today": self.state.questions_sent_today,
            "facts_sent_today": self.state.facts_sent_today,
            "total_questions_sent": self.state.total_questions_sent,
            "total_facts_sent": self.state.total_facts_sent,
            "last_question_sent": self.state.last_question_sent,
            "last_fact_sent": self.state.last_fact_sent
        }
