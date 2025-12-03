# Файл: it_ecosystem_bot/utils/inventory_generator.py
import sqlite3
import time
from datetime import datetime

DB_PATH = 'it_ecosystem.db'

# Категории оборудования и их коды
CATEGORY_CODES = {
    'laptop': 'LT',
    'desktop': 'DT',
    'monitor': 'MN',
    'printer': 'PR',
    'router': 'RT',
    'phone': 'PH',
    'keyboard': 'KB',
    'mouse': 'MS',
    'headset': 'HS',
    'usb_device': 'USB',
    'other': 'OT'
}


def generate_inventory_number(category: str) -> str:
    """
    Генерирует уникальный инвентарный номер вида: [CATEGORY_CODE]-YYYY-NNNN
    Например: LT-2025-0001, DT-2025-0042
    
    Args:
        category: Категория оборудования (например, 'laptop', 'desktop')
        
    Returns:
        Уникальный инвентарный номер
    """
    
    # Получаем код категории
    category_code = CATEGORY_CODES.get(category.lower(), 'OT')
    
    # Текущий год
    year = datetime.now().year
    
    # Получаем последний номер для этой категории в текущем году
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    pattern = f"{category_code}-{year}-%"
    cursor.execute(
        "SELECT MAX(inv_number) FROM equipment WHERE inv_number LIKE ?",
        (pattern,)
    )
    last_result = cursor.fetchone()[0]
    conn.close()
    
    # Определяем следующий номер последовательности
    if last_result:
        # Извлекаем номер из последнего инвентарного номера
        last_seq = int(last_result.split('-')[-1])
        next_seq = last_seq + 1
    else:
        next_seq = 1
    
    # Форматируем номер
    inventory_number = f"{category_code}-{year}-{next_seq:04d}"
    
    return inventory_number


def generate_next_inventory_for_batch(category: str, count: int = 1) -> list[str]:
    """
    Генерирует несколько инвентарных номеров подряд.
    
    Args:
        category: Категория оборудования
        count: Количество номеров для генерации
        
    Returns:
        Список сгенерированных инвентарных номеров
    """
    
    numbers = []
    for _ in range(count):
        numbers.append(generate_inventory_number(category))
    
    return numbers


def get_available_categories() -> dict:
    """Возвращает словарь доступных категорий оборудования."""
    return CATEGORY_CODES
