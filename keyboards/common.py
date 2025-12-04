# Файл: it_ecosystem_bot/keyboards/common.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_keyboard(role: str) -> ReplyKeyboardMarkup:
    """Генерирует основное меню для пользователя или администратора."""
    buttons = [
        [KeyboardButton(text="🆘 Создать заявку")],
        [KeyboardButton(text="📋 Мои заявки"), KeyboardButton(text="👤 Профиль")]
    ]

    # Добавление кнопок администратора
    if role == 'admin':
        buttons.append(
            [KeyboardButton(text="📋 Все заявки"), KeyboardButton(text="💻 Оборудование")]
        )
        buttons.append(
            [KeyboardButton(text="🏢 Рабочие места"), KeyboardButton(text="🛠️ Админ-панель")]
        )

    # Кнопка Выход
    buttons.append(
        [KeyboardButton(text="🚪 Выход")]
    )

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )


def get_rating_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для оценки заявки."""
    buttons = [
        [
            InlineKeyboardButton(text="1 ⭐️", callback_data=f"rate_{ticket_id}_1"),
            InlineKeyboardButton(text="2 ⭐️", callback_data=f"rate_{ticket_id}_2"),
            InlineKeyboardButton(text="3 ⭐️", callback_data=f"rate_{ticket_id}_3"),
            InlineKeyboardButton(text="4 ⭐️", callback_data=f"rate_{ticket_id}_4"),
            InlineKeyboardButton(text="5 ⭐️", callback_data=f"rate_{ticket_id}_5"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_logout_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для подтверждения выхода."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, выйти", callback_data="logout_confirm"),
            InlineKeyboardButton(text="❌ Нет, остаться", callback_data="logout_cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# !!! ФУНКЦИЯ ДЛЯ КНОПКИ ЗАКРЫТИЯ ЗАЯВКИ (АДМИН)
def get_admin_ticket_actions(ticket_id: int) -> InlineKeyboardMarkup:
    """Кнопка 'Закрыть заявку' для администратора."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Закрыть заявку", callback_data=f"admin_close_{ticket_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)