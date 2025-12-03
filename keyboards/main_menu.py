from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_user_menu() -> ReplyKeyboardMarkup:
    """Меню для обычного пользователя"""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="👤 Мой профиль"),
        KeyboardButton(text="📋 Мои заявки")
    )
    
    builder.row(
        KeyboardButton(text="🆘 Создать заявку"),
        KeyboardButton(text="💻 Мое оборудование")
    )
    
    builder.row(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="🏢 Мое рабочее место")
    )
    
    builder.row(
        KeyboardButton(text="🔄 Обновить"),
        KeyboardButton(text="🚪 Выйти")
    )
    
    return builder.as_markup(resize_keyboard=True)

def get_admin_menu() -> ReplyKeyboardMarkup:
    """Меню для администратора"""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="👤 Профиль"),
        KeyboardButton(text="📋 Все заявки")
    )
    
    builder.row(
        KeyboardButton(text="👥 Сотрудники"),
        KeyboardButton(text="📊 Аналитика")
    )
    
    builder.row(
        KeyboardButton(text="⚙️ Настройки"),
        KeyboardButton(text="📈 Отчеты")
    )
    
    builder.row(
        KeyboardButton(text="🔄 Обновить"),
        KeyboardButton(text="🚪 Выйти")
    )
    
    return builder.as_markup(resize_keyboard=True)

def get_ticket_categories_keyboard() -> InlineKeyboardMarkup:
    """Категории для заявок"""
    builder = InlineKeyboardBuilder()
    
    categories = [
        ("💻 Проблема с ПО", "software"),
        ("🖥 Проблема с оборудованием", "hardware"),
        ("🌐 Проблема с сетью", "network"),
        ("🖨 Проблема с принтером", "printer"),
        ("📱 Проблема с телефоном", "phone"),
        ("🔧 Другое", "other")
    ]
    
    for text, callback_data in categories:
        builder.button(text=text, callback_data=f"category_{callback_data}")
    
    builder.adjust(2)
    return builder.as_markup()

def get_ticket_priority_keyboard() -> InlineKeyboardMarkup:
    """Приоритеты заявок"""
    builder = InlineKeyboardBuilder()
    
    priorities = [
        ("🔴 Высокий", "high"),
        ("🟡 Средний", "medium"),
        ("🟢 Низкий", "low")
    ]
    
    for text, callback_data in priorities:
        builder.button(text=text, callback_data=f"priority_{callback_data}")
    
    builder.adjust(3)
    return builder.as_markup()