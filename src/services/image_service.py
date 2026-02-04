"""
Сервис для работы с изображениями.
"""
import random
from pathlib import Path
from typing import Optional, List
from aiogram.types import FSInputFile

from src.config import FACT_IMAGES_DIR
from src.utils.logger import setup_logger


logger = setup_logger("image_service")


class ImageService:
    """
    Сервис для управления изображениями фактов.
    """
    
    def __init__(self, images_dir: Path = FACT_IMAGES_DIR):
        self.images_dir = images_dir
        self._available_images: List[Path] = []
        self._load_images()
    
    def _load_images(self) -> None:
        """Загружает список доступных изображений"""
        if not self.images_dir.exists():
            logger.warning(f"Директория с изображениями не найдена: {self.images_dir}")
            self._available_images = []
            return
        
        try:
            # Поддерживаемые форматы
            image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
            
            self._available_images = [
                p for p in self.images_dir.iterdir()
                if p.is_file() and p.suffix.lower() in image_extensions
            ]
            
            logger.info(f"Загружено {len(self._available_images)} изображений")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки изображений: {e}")
            self._available_images = []
    
    def get_random_image(self) -> Optional[FSInputFile]:
        """
        Возвращает случайное изображение как FSInputFile для aiogram.
        
        Returns:
            FSInputFile или None если изображений нет
        """
        if not self._available_images:
            return None
        
        try:
            image_path = random.choice(self._available_images)
            return FSInputFile(str(image_path))
        except Exception as e:
            logger.error(f"Ошибка создания FSInputFile: {e}")
            return None
    
    def get_random_image_path(self) -> Optional[Path]:
        """
        Возвращает путь к случайному изображению.
        
        Returns:
            Path или None если изображений нет
        """
        if not self._available_images:
            return None
        
        return random.choice(self._available_images)
    
    def get_image_by_name(self, filename: str) -> Optional[FSInputFile]:
        """
        Возвращает изображение по имени файла.
        
        Args:
            filename: Имя файла
            
        Returns:
            FSInputFile или None если файл не найден
        """
        try:
            image_path = self.images_dir / filename
            if image_path.exists() and image_path.is_file():
                return FSInputFile(str(image_path))
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска изображения {filename}: {e}")
            return None
    
    def reload(self) -> int:
        """
        Перезагружает список изображений.
        
        Returns:
            Количество загруженных изображений
        """
        self._load_images()
        return len(self._available_images)
    
    @property
    def count(self) -> int:
        """Количество доступных изображений"""
        return len(self._available_images)
    
    @property
    def has_images(self) -> bool:
        """Есть ли доступные изображения"""
        return len(self._available_images) > 0
    
    def get_all_images(self) -> List[Path]:
        """Возвращает список всех изображений"""
        return self._available_images.copy()