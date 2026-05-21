import re
from datetime import datetime

def validate_login(login: str) -> bool:
    """Простая валидация логина (например, только буквы, цифры, _)."""
    pattern = r'^[a-zA-Z0-9_]+$'
    return bool(re.match(pattern, login))

def validate_datetime_format(dt_str: str, fmt: str = '%Y-%m-%d %H:%M:%S') -> bool:
    """Проверяет, соответствует ли строка формату даты/времени."""
    try:
        datetime.strptime(dt_str, fmt)
        return True
    except ValueError:
        return False

# ... другие вспомогательные функции, не связанные с БД ...