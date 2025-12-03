import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any

def generate_inventory_number(prefix: str, length: int = 6) -> str:
    """Генерация инвентарного номера"""
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{random_part}"

def calculate_uptime(start_date: datetime, issues: int) -> float:
    """Расчет аптайма оборудования"""
    total_days = (datetime.now() - start_date).days
    if total_days == 0:
        return 100.0
    
    uptime_days = total_days - (issues * 0.5)
    uptime_percent = (uptime_days / total_days) * 100
    return max(0.0, min(100.0, uptime_percent))

def format_duration(seconds: int) -> str:
    """Форматирование длительности"""
    if seconds < 60:
        return f"{seconds} сек."
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин."
    
    hours = minutes // 60
    if hours < 24:
        return f"{hours} час."
    
    days = hours // 24
    return f"{days} дн."

def get_status_emoji(status: str) -> str:
    """Получить эмодзи для статуса"""
    emojis = {
        'active': '🟢',
        'активен': '🟢',
        'open': '🔴',
        'resolved': '✅',
        'in_progress': '🟡',
        'maintenance': '🟠',
        'closed': '⚫',
        'high': '🔴',
        'medium': '🟡',
        'low': '🟢',
        'critical': '💀'
    }
    return emojis.get(status.lower(), '⚪')

def generate_password(length: int = 12) -> str:
    """Генерация пароля"""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

def format_date(date_obj: datetime) -> str:
    """Форматирование даты"""
    return date_obj.strftime("%d.%m.%Y")

def generate_ticket_number() -> str:
    """Генерация номера заявки"""
    date_part = datetime.now().strftime("%y%m%d")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"TK{date_part}{random_part}"

def get_department_emoji(department: str) -> str:
    """Получить эмодзи для отдела"""
    dept_lower = department.lower()
    
    emojis = {
        'it': '💻',
        'айти': '💻',
        'техподдержка': '🛠',
        'support': '🛠',
        'продажи': '💰',
        'sales': '💰',
        'hr': '👥',
        'маркетинг': '📢',
        'marketing': '📢',
        'управление': '👔',
        'management': '👔',
        'бухгалтерия': '📊',
        'accounting': '📊',
        'логистика': '🚚',
        'logistics': '🚚',
        'склад': '📦',
        'warehouse': '📦',
        'транспорт': '🚛',
        'transport': '🚛',
        'водитель': '🚚',
        'driver': '🚚'
    }
    
    for key, emoji in emojis.items():
        if key in dept_lower:
            return emoji
    
    return '🏢'

def calculate_average_rating(ratings: list[int]) -> float:
    """Расчет средней оценки"""
    if not ratings:
        return 0.0
    return sum(ratings) / len(ratings)

def get_position_emoji(position: str) -> str:
    """Получить эмодзи для должности"""
    pos_lower = position.lower()
    
    if any(word in pos_lower for word in ['менеджер', 'manager']):
        return '👔'
    elif any(word in pos_lower for word in ['разработ', 'developer', 'программ']):
        return '👨‍💻'
    elif any(word in pos_lower for word in ['админ', 'admin', 'систем']):
        return '🛠'
    elif any(word in pos_lower for word in ['директор', 'director', 'руковод']):
        return '👑'
    elif any(word in pos_lower for word in ['водитель', 'driver']):
        return '🚚'
    elif any(word in pos_lower for word in ['логист', 'logistic']):
        return '📦'
    else:
        return '👤'