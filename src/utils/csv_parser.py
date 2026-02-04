"""
Улучшенный парсер CSV файлов с автоопределением кодировки и разделителя.
"""
import csv
import chardet
from pathlib import Path
from typing import List, Tuple, Optional, Union, Dict, Any
import logging

from src.utils.logger import setup_logger


logger = setup_logger("csv_parser")


class CSVParser:
    """
    Умный парсер CSV файлов с автоопределением:
    - Кодировки (UTF-8, UTF-8-BOM, CP1251, CP1252)
    - Разделителя (запятая, точка с запятой, табуляция)
    - Формата данных (с заголовком/без)
    """
    
    # Поддерживаемые кодировки (в порядке приоритета)
    ENCODINGS = ['utf-8-sig', 'utf-8', 'cp1251', 'cp1252', 'iso-8859-1']
    
    # Возможные разделители
    DELIMITERS = [',', ';', '\t', '|']
    
    def __init__(self):
        self.detected_encoding = None
        self.detected_delimiter = None
    
    def detect_encoding(self, file_path: Path) -> Optional[str]:
        """
        Определяет кодировку файла.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Определенная кодировка или None
        """
        try:
            # Читаем первые 10KB для определения
            with open(file_path, 'rb') as f:
                raw_data = f.read(10240)
            
            result = chardet.detect(raw_data)
            confidence = result.get('confidence', 0)
            encoding = result.get('encoding', '').lower()
            
            if confidence > 0.7:
                # Нормализуем названия кодировок
                encoding_map = {
                    'windows-1251': 'cp1251',
                    'windows-1252': 'cp1252',
                    'ascii': 'utf-8'
                }
                encoding = encoding_map.get(encoding, encoding)
                logger.debug(f"Определена кодировка: {encoding} (уверенность: {confidence:.2%})")
                return encoding
            
        except Exception as e:
            logger.warning(f"Ошибка определения кодировки: {e}")
        
        return None
    
    def detect_delimiter(self, first_line: str) -> str:
        """
        Определяет разделитель по первой строке.
        
        Args:
            first_line: Первая строка файла
            
        Returns:
            Определенный разделитель (по умолчанию ',')
        """
        delimiter_scores = {}
        
        for delimiter in self.DELIMITERS:
            count = first_line.count(delimiter)
            if count > 0:
                delimiter_scores[delimiter] = count
        
        if delimiter_scores:
            # Выбираем разделитель с максимальным количеством
            detected = max(delimiter_scores.items(), key=lambda x: x[1])[0]
            logger.debug(f"Определен разделитель: '{detected}'")
            return detected
        
        logger.debug("Разделитель не определен, используется ',' по умолчанию")
        return ','
    
    def read_csv(
        self,
        file_path: Path,
        has_header: bool = False,
        encoding: Optional[str] = None,
        delimiter: Optional[str] = None
    ) -> List[List[str]]:
        """
        Читает CSV файл с автоопределением параметров.
        
        Args:
            file_path: Путь к CSV файлу
            has_header: Есть ли заголовок (автоопределяется если False)
            encoding: Кодировка (определяется автоматически если None)
            delimiter: Разделитель (определяется автоматически если None)
            
        Returns:
            Список строк (каждая строка - список ячеек)
            
        Raises:
            FileNotFoundError: Если файл не существует
            ValueError: Если файл пустой или поврежден
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        # Определяем кодировку
        if encoding is None:
            encoding = self.detect_encoding(file_path)
            if encoding is None:
                encoding = 'utf-8'  # fallback
            self.detected_encoding = encoding
        
        # Читаем первую строку для определения разделителя
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                first_line = f.readline().strip()
        except UnicodeDecodeError:
            # Пробуем следующую кодировку из списка
            for enc in self.ENCODINGS:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        first_line = f.readline().strip()
                    encoding = enc
                    self.detected_encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Не удалось определить кодировку файла: {file_path}")
        
        if not first_line:
            raise ValueError(f"Файл пустой: {file_path}")
        
        # Определяем разделитель
        if delimiter is None:
            delimiter = self.detect_delimiter(first_line)
            self.detected_delimiter = delimiter
        
        # Определяем наличие заголовка (эвристика)
        if not has_header:
            first_cell = first_line.split(delimiter)[0].strip().lower()
            common_headers = ['вопрос', 'question', 'факт', 'fact', 'id', 'номер']
            has_header = any(header in first_cell for header in common_headers)
        
        # Читаем весь файл
        rows = []
        with open(file_path, 'r', encoding=encoding, newline='') as f:
            csv_reader = csv.reader(f, delimiter=delimiter)
            
            for i, row in enumerate(csv_reader):
                # Пропускаем пустые строки
                if not row or all(cell.strip() == '' for cell in row):
                    continue
                
                # Пропускаем заголовок если есть
                if has_header and i == 0:
                    logger.debug(f"Пропущен заголовок: {row}")
                    continue
                
                rows.append([cell.strip() for cell in row])
        
        if not rows:
            raise ValueError(f"Нет данных в файле (после обработки): {file_path}")
        
        logger.info(
            f"Прочитан CSV: {file_path.name}, "
            f"строк: {len(rows)}, "
            f"кодировка: {encoding}, "
            f"разделитель: '{delimiter}'"
        )
        
        return rows
    
    def parse_questions_csv(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Парсит CSV файл с вопросами викторины.
        
        Формат:
        Вопрос,Вариант1,Вариант2,...,ИндексПравильного[,Пояснение]
        
        Args:
            file_path: Путь к CSV файлу
            
        Returns:
            Список словарей с данными вопросов
        """
        rows = self.read_csv(file_path, has_header=False)
        questions = []
        
        for i, row in enumerate(rows, start=1):
            try:
                if len(row) < 4:
                    logger.warning(f"Строка {i}: пропущена, мало колонок ({len(row)})")
                    continue
                
                # Определяем структуру строки
                has_explanation = len(row) >= 5
                
                if has_explanation:
                    question_text = row[0]
                    options = row[1:-2]
                    correct_idx_str = row[-2]
                    explanation = row[-1] if row[-1] else None
                else:
                    question_text = row[0]
                    options = row[1:-1]
                    correct_idx_str = row[-1]
                    explanation = None
                
                # Преобразуем индекс правильного ответа
                try:
                    correct_idx = int(correct_idx_str)
                    # Поддерживаем 1-based и 0-based индексы
                    if 1 <= correct_idx <= len(options):
                        correct_idx -= 1
                    elif not (0 <= correct_idx < len(options)):
                        raise ValueError(f"Индекс {correct_idx} вне диапазона [0, {len(options)-1}]")
                except ValueError as e:
                    logger.warning(f"Строка {i}: некорректный индекс ответа '{correct_idx_str}': {e}")
                    continue
                
                # Валидация
                if not question_text.strip():
                    logger.warning(f"Строка {i}: пустой текст вопроса")
                    continue
                
                if len(options) < 2:
                    logger.warning(f"Строка {i}: недостаточно вариантов ({len(options)})")
                    continue
                
                if len(options) > 10:
                    logger.warning(f"Строка {i}: слишком много вариантов ({len(options)})")
                    continue
                
                questions.append({
                    'text': question_text,
                    'options': options,
                    'correct_index': correct_idx,
                    'explanation': explanation,
                    'line_number': i
                })
                
            except Exception as e:
                logger.error(f"Строка {i}: ошибка парсинга: {e}, данные: {row}")
                continue
        
        return questions
    
    def parse_facts_csv(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Парсит CSV файл с фактами.
        
        Формат:
        Факт;Источник
        
        Args:
            file_path: Путь к CSV файлу
            
        Returns:
            Список словарей с данными фактов
        """
        rows = self.read_csv(file_path, has_header=False)
        facts = []
        
        for i, row in enumerate(rows, start=1):
            try:
                if not row or len(row) < 1:
                    continue
                
                fact_text = row[0].strip()
                if not fact_text:
                    logger.warning(f"Строка {i}: пустой текст факта")
                    continue
                
                source = row[1].strip() if len(row) > 1 and row[1].strip() else None
                
                facts.append({
                    'text': fact_text,
                    'source': source,
                    'line_number': i
                })
                
            except Exception as e:
                logger.error(f"Строка {i}: ошибка парсинга: {e}, данные: {row}")
                continue
        
        return facts 
