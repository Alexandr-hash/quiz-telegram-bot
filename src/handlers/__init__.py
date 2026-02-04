"""
Пакет обработчиков (HANDLERS)
=============================
Содержит все обработчики входящих сообщений и команд.

Структура:
    handlers/
    ├── __init__.py      # Этот файл
    └── admin_handlers.py # Обработчики команд администратора
"""

from .admin_handlers import register_admin_handlers

__all__ = ['register_admin_handlers'] 
