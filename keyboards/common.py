# Файл: it_ecosystem_bot/keyboards/common.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict

# --- Инлайн главное меню ---
def inline_main_menu(role: str = "user") -> InlineKeyboardMarkup:
    """
    Инлайн-меню для быстрых действий в боте.
    Используем callback_data, чтобы хендлеры могли обрабатывать без команд.
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="🆕 Создать заявку", callback_data="menu_create_ticket")
    kb.button(text="📄 Мои заявки", callback_data="menu_my_tickets")
    kb.button(text="📚 FAQ", callback_data="faq_show_guides")
    if role == "admin":
        kb.button(text="📢 Рассылка", callback_data="admin_mailing_menu")
    kb.adjust(2)
    return kb.as_markup()


# --- КЛАВИАТУРЫ ДЛЯ АВТОРИЗАЦИИ И МЕНЮ ---

def get_start_auth_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для начальной авторизации (замена /login)."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🚪 Войти в систему", callback_data="auth_login_btn")
    return kb.as_markup()


def main_menu_keyboard(role: str) -> ReplyKeyboardMarkup:
    """Генерирует основное меню для пользователя или администратора."""
    buttons = [
        [KeyboardButton(text="🆘 Создать запрос")],
        [KeyboardButton(text="📋 Мои запросы"), KeyboardButton(text="👤 Мой профиль")],
        [KeyboardButton(text="❓ FAQ"), KeyboardButton(text="🔑 Мои доступы")],
        [KeyboardButton(text="🚪 Выход из профиля")]
    ]

    if role == 'admin':
        buttons.insert(0,
            [KeyboardButton(text="📋 Все заявки"), KeyboardButton(text="💻 Оборудование")]
        )
        buttons.insert(1,
            [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="🛠️ Админ-панель")]
        )

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
        selective=True
    )


# --- КЛАВИАТУРЫ ДЛЯ ЗАЯВОК И АДМИНИСТРИРОВАНИЯ ---

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


def get_admin_ticket_actions(ticket_id: int) -> InlineKeyboardMarkup:
    """Кнопка 'Закрыть заявку' для администратора."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Закрыть заявку", callback_data=f"admin_close_{ticket_id}")
    return kb.as_markup()


# --- КЛАВИАТУРЫ ДЛЯ РАССЫЛКИ ---

def get_mailing_schedule_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для выбора расписания рассылки."""
    kb = InlineKeyboardBuilder()
    kb.button(text="➡️ Отправить СЕЙЧАС", callback_data="mail_schedule_now")
    kb.button(text="🗓️ Постоянно (Будни, 19:00)", callback_data="mail_schedule_weekly")
    kb.adjust(1)
    return kb.as_markup()


# --- КЛАВИАТУРЫ ДЛЯ ПРОФИЛЯ/FAQ ---

def get_faq_admin_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для управления FAQ."""
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить материал", callback_data="faq_add")
    kb.button(text="📝 Редактировать/Удалить", callback_data="faq_edit_list")
    kb.adjust(1)
    return kb.as_markup()

def confirm_logout_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для подтверждения выхода."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, выйти", callback_data="logout_confirm"),
            InlineKeyboardButton(text="❌ Нет, остаться", callback_data="logout_cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_faq_initial_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для начального меню FAQ (кнопка 'Гайды')."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📖 Гайды", callback_data="faq_show_guides")
    kb.adjust(1)
    return kb.as_markup()


def get_faq_guides_list_keyboard(guides: list[dict]) -> InlineKeyboardMarkup:
    """Динамическая клавиатура для списка сохраненных гайдов."""
    kb = InlineKeyboardBuilder()

    # Кнопки для каждого гайда (используем ID для callback_data)
    for guide in guides:
        kb.button(
            text=guide['title'][:35],
            callback_data=f"guide_show_{guide['id']}"
        )

    kb.adjust(1)

    # Кнопка "Назад"
    kb.button(text="« Назад в FAQ", callback_data="faq_back_to_main")

    return kb.as_markup()
