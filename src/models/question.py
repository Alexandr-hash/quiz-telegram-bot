"""
Модель вопроса викторины
"""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Question:
    """
    Вопрос викторины с вариантами ответов.
    
    Attributes:
        text: Текст вопроса
        options: Список вариантов ответов (2-10 элементов)
        correct_index: Индекс правильного ответа (0-based)
        explanation: Пояснение к правильному ответу (опционально)
        category: Категория вопроса (опционально)
        difficulty: Сложность (1-5, опционально)
    """
    text: str
    options: List[str]
    correct_index: int
    explanation: Optional[str] = None
    category: Optional[str] = None
    difficulty: int = 1
    
    def __post_init__(self):
        """Валидация при создании объекта"""
        if not self.text.strip():
            raise ValueError("Текст вопроса не может быть пустым")
        
        if len(self.options) < 2 or len(self.options) > 10:
            raise ValueError("Количество вариантов должно быть от 2 до 10")
        
        if not (0 <= self.correct_index < len(self.options)):
            raise ValueError("Индекс правильного ответа вне диапазона")
    
    @property
    def correct_answer(self) -> str:
        """Возвращает текст правильного ответа"""
        return self.options[self.correct_index]
    
    def to_dict(self) -> dict:
        """Преобразует вопрос в словарь"""
        return {
            "text": self.text,
            "options": self.options,
            "correct_index": self.correct_index,
            "explanation": self.explanation,
            "category": self.category,
            "difficulty": self.difficulty
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        """Создает вопрос из словаря"""
        return cls(
            text=data["text"],
            options=data["options"],
            correct_index=data["correct_index"],
            explanation=data.get("explanation"),
            category=data.get("category"),
            difficulty=data.get("difficulty", 1)
        ) 
