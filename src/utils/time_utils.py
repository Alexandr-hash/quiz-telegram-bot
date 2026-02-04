"""
Утилиты для работы со временем
"""
from datetime import datetime, time, timedelta
from typing import Optional


def seconds_until(target_time: time) -> float:
    """
    Сколько секунд до ближайшего времени t (сегодня/завтра).
    
    Args:
        target_time: Время для расчета
        
    Returns:
        Количество секунд до указанного времени
    """
    now = datetime.now()
    target = datetime.combine(now.date(), target_time)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def format_seconds(seconds: float) -> str:
    """
    Форматирует секунды в читаемый вид.
    
    Args:
        seconds: Количество секунд
        
    Returns:
        Отформатированная строка: "X ч. Y мин. Z сек."
    """
    if seconds < 60:
        return f"{int(seconds)} сек."
    elif seconds < 3600:
        minutes = int(seconds // 60)
        seconds_rem = int(seconds % 60)
        if seconds_rem > 0:
            return f"{minutes} мин. {seconds_rem} сек."
        return f"{minutes} мин."
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if minutes > 0:
            return f"{hours} ч. {minutes} мин."
        return f"{hours} ч."


def parse_time_str(time_str: str) -> Optional[time]:
    """
    Парсит строку времени в формате HH:MM.
    
    Args:
        time_str: Строка времени (например, "10:00")
        
    Returns:
        Объект time или None при ошибке
    """
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return None
