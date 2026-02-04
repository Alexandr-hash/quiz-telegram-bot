"""
Модель факта дня
"""
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class Fact:
    """
    Факт дня.
    
    Attributes:
        text: Текст факта
        source: Источник факта (опционально)
        image_path: Путь к изображению (опционально)
        is_true: Факт является правдой (True/False/None для обычных фактов)
    """
    text: str
    source: Optional[str] = None
    image_path: Optional[Path] = None
    is_true: Optional[bool] = None
    
    def __post_init__(self):
        """Валидация при создании объекта"""
        if not self.text.strip():
            raise ValueError("Текст факта не может быть пустым")
    
    def format_text(self) -> str:
        """
        Форматирует текст факта для отправки.
        
        Returns:
            Отформатированная строка
        """
        result = "📚 ФАКТ ДНЯ\n\n"
        
        # Добавляем префикс "Правда или ложь?" если указано
        if self.is_true is not None:
            result = "🤔 ПРАВДА ИЛИ ЛОЖЬ?\n\n"
            result += self.text
            
            # Добавляем ответ (можно скрыть для интерактива)
            # result += f"\n\nОтвет: {'✅ ПРАВДА' if self.is_true else '❌ ЛОЖЬ'}"
        else:
            result += self.text
        
        # Добавляем источник если есть
        if self.source:
            result += f"\n\n📖 Источник: {self.source}"
        
        return result
    
    @property
    def has_image(self) -> bool:
        """Проверяет, есть ли у факта изображение"""
        return self.image_path is not None and self.image_path.exists()
    
    def to_dict(self) -> dict:
        """Преобразует факт в словарь"""
        return {
            "text": self.text,
            "source": self.source,
            "image_path": str(self.image_path) if self.image_path else None,
            "is_true": self.is_true
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Fact":
        """Создает факт из словаря"""
        image_path = None
        if data.get("image_path"):
            image_path = Path(data["image_path"])
        
        return cls(
            text=data["text"],
            source=data.get("source"),
            image_path=image_path,
            is_true=data.get("is_true")
        ) 
