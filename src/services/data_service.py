"""
СЕРВИС ДАННЫХ (DATA SERVICE)
=============================
Основной сервис для управления данными викторины:
- Загрузка вопросов и фактов из CSV файлов
- Управление очередностью отправки
- Интеграция с сервисом состояния
- Работа с изображениями фактов

Ответственность:
- Предоставление данных для отправки
- Сохранение и восстановление состояния
- Обработка ошибок загрузки данных
"""

from pathlib import Path
from typing import List, Optional, Tuple
import random

from src.models.question import Question
from src.models.fact import Fact
from src.utils.csv_parser import CSVParser
from src.services.state_service import StateService
from src.config import QUESTIONS_FILE, FACTS_FILE, FACT_IMAGES_DIR
from src.utils.logger import setup_logger


# Инициализация логгера для этого модуля
logger = setup_logger("data_service")


class DataService:
    """
    ГЛАВНЫЙ СЕРВИС ДАННЫХ ДЛЯ ВИКТОРИНЫ
    ===================================
    Координирует работу с вопросами, фактами и изображениями.
    Инкапсулирует логику загрузки, кэширования и предоставления данных.
    
    Атрибуты:
        questions_file: Путь к файлу с вопросами (CSV)
        facts_file: Путь к файлу с фактами (CSV)
        images_dir: Директория с изображениями для фактов
        parser: Парсер CSV файлов
        state_service: Сервис для работы с состоянием бота
        _questions: Кэш загруженных вопросов
        _facts: Кэш загруженных фактов
        _available_images: Список доступных изображений
        _loaded: Флаг успешной загрузки данных
    """
    
    def __init__(
        self,
        questions_file: Path = QUESTIONS_FILE,
        facts_file: Path = FACTS_FILE,
        images_dir: Path = FACT_IMAGES_DIR
    ):
        """
        ИНИЦИАЛИЗАЦИЯ СЕРВИСА ДАННЫХ
        -----------------------------
        Создает экземпляр сервиса с указанными путями к файлам.
        
        Args:
            questions_file: Путь к CSV файлу с вопросами
            facts_file: Путь к CSV файлу с фактами
            images_dir: Путь к директории с изображениями
        """
        self.questions_file = questions_file
        self.facts_file = facts_file
        self.images_dir = images_dir
        
        self.parser = CSVParser()
        self.state_service = StateService()
        
        # Кэшированные данные
        self._questions: List[Question] = []
        self._facts: List[Fact] = []
        self._available_images: List[Path] = []
        
        # Флаг загруженности
        self._loaded = False
    
    def load_all(self) -> Tuple[int, int]:
        """
        ЗАГРУЗКА ВСЕХ ДАННЫХ
        ---------------------
        Основной метод для инициализации данных.
        Загружает вопросы, факты и изображения из файлов.
        
        Returns:
            Кортеж (количество_вопросов, количество_фактов)
            
        Raises:
            FileNotFoundError: Если файлы не найдены
            ValueError: Если данные некорректны
            
        Пример:
            >>> service = DataService()
            >>> q_count, f_count = service.load_all()
            >>> print(f"Загружено: {q_count} вопросов, {f_count} фактов")
        """
        logger.info("Начало загрузки всех данных...")
        
        # Загрузка вопросов
        questions_count = self._load_questions()
        
        # Загрузка фактов
        facts_count = self._load_facts()
        
        # Загрузка изображений
        images_count = self._load_images()
        
        self._loaded = True
        
        logger.info(
            f"Данные загружены: {questions_count} вопросов, "
            f"{facts_count} фактов, {images_count} изображений"
        )
        
        return questions_count, facts_count
    
    def _load_questions(self) -> int:
        """
        ПРИВАТНЫЙ МЕТОД: ЗАГРУЗКА ВОПРОСОВ
        -----------------------------------
        Загружает вопросы из CSV файла, преобразует в объекты Question.
        Обрабатывает ошибки парсинга отдельных строк.
        
        Returns:
            Количество успешно загруженных вопросов
        """
        if not self.questions_file.exists():
            logger.warning(f"Файл вопросов не найден: {self.questions_file}")
            self._questions = []
            return 0
        
        try:
            parsed_data = self.parser.parse_questions_csv(self.questions_file)
            self._questions = []
            
            for item in parsed_data:
                try:
                    question = Question(
                        text=item['text'],
                        options=item['options'],
                        correct_index=item['correct_index'],
                        explanation=item.get('explanation')
                    )
                    self._questions.append(question)
                except Exception as e:
                    logger.warning(f"Ошибка создания вопроса (строка {item['line_number']}): {e}")
                    continue
            
            logger.info(f"Загружено вопросов: {len(self._questions)}")
            return len(self._questions)
            
        except Exception as e:
            logger.error(f"Критическая ошибка загрузки вопросов: {e}")
            self._questions = []
            return 0
    
    def _load_facts(self) -> int:
        """
        ПРИВАТНЫЙ МЕТОД: ЗАГРУЗКА ФАКТОВ
        ---------------------------------
        Загружает факты из CSV файла, преобразует в объекты Fact.
        Обрабатывает ошибки парсинга отдельных строк.
        
        Returns:
            Количество успешно загруженных фактов
        """
        if not self.facts_file.exists():
            logger.warning(f"Файл фактов не найден: {self.facts_file}")
            self._facts = []
            return 0
        
        try:
            parsed_data = self.parser.parse_facts_csv(self.facts_file)
            self._facts = []
            
            for item in parsed_data:
                try:
                    fact = Fact(
                        text=item['text'],
                        source=item.get('source')
                    )
                    self._facts.append(fact)
                except Exception as e:
                    logger.warning(f"Ошибка создания факта (строка {item['line_number']}): {e}")
                    continue
            
            logger.info(f"Загружено фактов: {len(self._facts)}")
            return len(self._facts)
            
        except Exception as e:
            logger.error(f"Критическая ошибка загрузки фактов: {e}")
            self._facts = []
            return 0
    
    def _load_images(self) -> int:
        """
        ПРИВАТНЫЙ МЕТОД: ЗАГРУЗКА ИЗОБРАЖЕНИЙ
        --------------------------------------
        Сканирует директорию и создает список доступных изображений.
        Поддерживает форматы: JPG, JPEG, PNG, WEBP, GIF.
        
        Returns:
            Количество найденных изображений
        """
        if not self.images_dir.exists():
            logger.warning(f"Директория с изображениями не найдена: {self.images_dir}")
            self._available_images = []
            return 0
        
        try:
            # Ищем изображения
            image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
            self._available_images = [
                p for p in self.images_dir.iterdir()
                if p.is_file() and p.suffix.lower() in image_extensions
            ]
            
            logger.info(f"Найдено изображений: {len(self._available_images)}")
            return len(self._available_images)
            
        except Exception as e:
            logger.error(f"Ошибка загрузки изображений: {e}")
            self._available_images = []
            return 0
    
    def get_next_question(self) -> Optional[Question]:
        """
        ПОЛУЧЕНИЕ СЛЕДУЮЩЕГО ВОПРОСА
        -----------------------------
        Возвращает следующий вопрос по порядку с циклическим перебором.
        Автоматически обновляет состояние (индекс вопроса).
        
        Returns:
            Следующий вопрос или None если вопросы не загружены
            
        Пример:
            >>> question = data_service.get_next_question()
            >>> if question:
            >>>     print(f"Вопрос: {question.text}")
        """
        if not self._questions:
            logger.warning("Попытка получить вопрос при пустом списке")
            return None
        
        # Получаем следующий индекс из состояния
        next_index = self.state_service.get_next_question_index(len(self._questions))
        
        # Берем вопрос
        question = self._questions[next_index]
        
        # Обновляем состояние (увеличиваем индекс)
        self.state_service.update_question_sent(next_index + 1)
        
        logger.debug(f"Выдан вопрос #{next_index}: {question.text[:50]}...")
        return question
    
    def get_next_fact(self) -> Optional[Fact]:
        """
        ПОЛУЧЕНИЕ СЛЕДУЮЩЕГО ФАКТА
        ---------------------------
        Возвращает следующий факт по порядку с циклическим перебором.
        С вероятностью 70% добавляет случайное изображение к факту.
        Автоматически обновляет состояние (индекс факта).
        
        Returns:
            Следующий факт или None если факты не загружены
        """
        if not self._facts:
            logger.warning("Попытка получить факт при пустом списке")
            return None
        
        # Получаем следующий индекс из состояния
        next_index = self.state_service.get_next_fact_index(len(self._facts))
        
        # Берем факт
        fact = self._facts[next_index]
        
        # Добавляем случайное изображение если есть доступные (70% шанс)
        if self._available_images and random.random() < 0.7:
            random_image = random.choice(self._available_images)
            fact.image_path = random_image
            logger.debug(f"К факту #{next_index} добавлено изображение: {random_image.name}")
        
        # Обновляем состояние (увеличиваем индекс)
        self.state_service.update_fact_sent(next_index + 1)
        
        logger.debug(f"Выдан факт #{next_index}: {fact.text[:50]}...")
        return fact
    
    def get_random_question(self) -> Optional[Question]:
        """
        ПОЛУЧЕНИЕ СЛУЧАЙНОГО ВОПРОСА
        -----------------------------
        Возвращает случайный вопрос без изменения состояния.
        Полезно для тестирования или дополнительных функций.
        
        Returns:
            Случайный вопрос или None если вопросы не загружены
        """
        if not self._questions:
            return None
        
        return random.choice(self._questions)
    
    def get_random_fact(self) -> Optional[Fact]:
        """
        ПОЛУЧЕНИЕ СЛУЧАЙНОГО ФАКТА
        ---------------------------
        Возвращает случайный факт без изменения состояния.
        С вероятностью 70% добавляет случайное изображение.
        
        Returns:
            Случайный факт или None если факты не загружены
        """
        if not self._facts:
            return None
        
        fact = random.choice(self._facts)
        
        # Добавляем случайное изображение если есть доступные
        if self._available_images and random.random() < 0.7:
            random_image = random.choice(self._available_images)
            fact.image_path = random_image
        
        return fact
    
    def get_question_by_index(self, index: int) -> Optional[Question]:
        """
        ПОЛУЧЕНИЕ ВОПРОСА ПО ИНДЕКСУ
        -----------------------------
        Возвращает вопрос по конкретному индексу.
        Не изменяет состояние бота.
        
        Args:
            index: Индекс вопроса (0-based)
            
        Returns:
            Вопрос или None если индекс вне диапазона
        """
        if not self._questions or not (0 <= index < len(self._questions)):
            return None
        
        return self._questions[index]
    
    def get_fact_by_index(self, index: int) -> Optional[Fact]:
        """
        ПОЛУЧЕНИЕ ФАКТА ПО ИНДЕКСУ
        ---------------------------
        Возвращает факт по конкретному индексу.
        Не изменяет состояние бота.
        
        Args:
            index: Индекс факта (0-based)
            
        Returns:
            Факт или None если индекс вне диапазона
        """
        if not self._facts or not (0 <= index < len(self._facts)):
            return None
        
        return self._facts[index]
    
    def reload(self) -> Tuple[int, int]:
        """
        ПЕРЕЗАГРУЗКА ДАННЫХ
        --------------------
        Полностью перезагружает все данные из файлов.
        Сбрасывает кэш и повторно сканирует изображения.
        
        Returns:
            Кортеж (количество_вопросов, количество_фактов)
            
        Пример:
            >>> # После изменения CSV файлов
            >>> service.reload()
            >>> print(f"Перезагружено: {service.questions_count} вопросов")
        """
        logger.info("Перезагрузка данных...")
        self._loaded = False
        return self.load_all()
    
    @property
    def questions_count(self) -> int:
        """СВОЙСТВО: КОЛИЧЕСТВО ВОПРОСОВ"""
        return len(self._questions)
    
    @property
    def facts_count(self) -> int:
        """СВОЙСТВО: КОЛИЧЕСТВО ФАКТОВ"""
        return len(self._facts)
    
    @property
    def images_count(self) -> int:
        """СВОЙСТВО: КОЛИЧЕСТВО ИЗОБРАЖЕНИЙ"""
        return len(self._available_images)
    
    @property
    def is_loaded(self) -> bool:
        """СВОЙСТВО: ЗАГРУЖЕНЫ ЛИ ДАННЫЕ"""
        return self._loaded
    
    def get_stats(self) -> dict:
        """
        ПОЛУЧЕНИЕ СТАТИСТИКИ
        ---------------------
        Возвращает подробную статистику по всем данным.
        
        Returns:
            Словарь со статистикой:
            {
                "questions": {total, current_index, sent_today, total_sent},
                "facts": {total, current_index, sent_today, total_sent},
                "images": {available}
            }
            
        Пример:
            >>> stats = service.get_stats()
            >>> print(f"Отправлено вопросов сегодня: {stats['questions']['sent_today']}")
        """
        state_stats = self.state_service.get_stats()
        
        return {
            "questions": {
                "total": self.questions_count,
                "current_index": state_stats.get("question_index", 0),
                "sent_today": state_stats.get("questions_sent_today", 0),
                "total_sent": state_stats.get("total_questions_sent", 0)
            },
            "facts": {
                "total": self.facts_count,
                "current_index": state_stats.get("fact_index", 0),
                "sent_today": state_stats.get("facts_sent_today", 0),
                "total_sent": state_stats.get("total_facts_sent", 0)
            },
            "images": {
                "available": self.images_count
            }
        }