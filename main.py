import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters.command import Command
import asyncio

from config import load_config
from database import Database

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = load_config()
bot = Bot(token=config.tg_bot.token)
dp = Dispatcher()
db = Database(config.db.path)

# FSM States
class TicketCreation(StatesGroup):
    waiting_floor = State()
    waiting_workplace = State()
    waiting_category = State()
    waiting_title = State()
    waiting_description = State()
    waiting_photo = State()

# Хелперы
def generate_ticket_number() -> str:
    """Генерировать номер заявки TKYYMMDDXXXX."""
    now = datetime.now()
    date_part = now.strftime('%y%m%d')
    import random
    random_part = str(random.randint(1000, 9999))
    return f"TK{date_part}{random_part}"

def get_main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Получить главное меню."""
    buttons = [
        [InlineKeyboardButton(text="📋 Мои заявки", callback_data="my_tickets")],
        [InlineKeyboardButton(text="➕ Создать заявку", callback_data="create_ticket")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="view_faq")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="my_profile")],
    ]
    
    if is_admin:
        buttons.extend([
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="send_broadcast")],
            [InlineKeyboardButton(text="📚 Управление FAQ", callback_data="manage_faq")],
            [InlineKeyboardButton(text="📊 Все заявки", callback_data="all_tickets")],
        ])
    
    buttons.append([InlineKeyboardButton(text="🚪 Выход", callback_data="logout")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_floor_kb() -> InlineKeyboardMarkup:
    """Получить клавиатуру выбора этажа."""
    buttons = [[InlineKeyboardButton(text=f"Этаж {floor}", callback_data=f"floor_{floor}")] 
               for floor in config.floors]
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_ticket")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_category_kb() -> InlineKeyboardMarkup:
    """Получить клавиатуру выбора категории."""
    buttons = [[InlineKeyboardButton(text=cat, callback_data=f"cat_{i}")] 
               for i, cat in enumerate(config.ticket_categories)]
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_ticket")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Handlers
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик /start."""
    user = db.get_user_by_telegram_id(message.from_user.id)
    
    if user:
        is_admin = user['role'] == 'admin' or message.from_user.id in config.super_admin_ids
        await message.answer(
            f"👋 Добро пожаловать, {user['full_name'] or message.from_user.first_name}!",
            reply_markup=get_main_menu_kb(is_admin)
        )
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Авторизоваться", callback_data="login")]
        ])
        await message.answer(
            "👋 Добро пожаловать в IT Ecosystem Bot!\n\n"
            "Пожалуйста, авторизуйтесь для начала работы.",
            reply_markup=kb
        )

@dp.callback_query(F.data == "login")
async def login_user(callback: types.CallbackQuery):
    """Авторизация пользователя."""
    db.add_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    user = db.get_user_by_telegram_id(callback.from_user.id)
    
    await callback.message.edit_text(
        f"✅ Вы авторизованы!\n\n"
        f"👤 Пользователь: {user['full_name']}\n"
        f"🆔 Telegram ID: {callback.from_user.id}",
        reply_markup=get_main_menu_kb()
    )

@dp.callback_query(F.data == "create_ticket")
async def start_create_ticket(callback: types.CallbackQuery, state: FSMContext):
    """Начать создание заявки."""
    await state.set_state(TicketCreation.waiting_floor)
    await callback.message.edit_text(
        "📝 Создание заявки\n\n"
        "🏢 Выберите ваш этаж:",
        reply_markup=get_floor_kb()
    )

@dp.callback_query(TicketCreation.waiting_floor, F.data.startswith("floor_"))
async def select_floor(callback: types.CallbackQuery, state: FSMContext):
    """Выбрать этаж."""
    floor = int(callback.data.split("_")[1])
    await state.update_data(floor=floor)
    
    workplaces = db.get_workplaces_by_floor(floor)
    if not workplaces:
        workplaces = [
            {"id": i+1, "workplace_number": f"РМ-{i+1}"} 
            for i in range(5)
        ]
    
    buttons = [[InlineKeyboardButton(text=wp['workplace_number'], 
                                    callback_data=f"wp_{wp['id']}")] 
               for wp in workplaces]
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_ticket")])
    
    await state.set_state(TicketCreation.waiting_workplace)
    await callback.message.edit_text(
        f"📍 Выберите рабочее место (Этаж {floor}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@dp.callback_query(TicketCreation.waiting_workplace, F.data.startswith("wp_"))
async def select_workplace(callback: types.CallbackQuery, state: FSMContext):
    """Выбрать рабочее место."""
    workplace_id = int(callback.data.split("_")[1])
    await state.update_data(workplace_id=workplace_id)
    
    await state.set_state(TicketCreation.waiting_category)
    await callback.message.edit_text(
        "📂 Выберите категорию проблемы:",
        reply_markup=get_category_kb()
    )

@dp.callback_query(TicketCreation.waiting_category, F.data.startswith("cat_"))
async def select_category(callback: types.CallbackQuery, state: FSMContext):
    """Выбрать категорию."""
    cat_idx = int(callback.data.split("_")[1])
    category = config.ticket_categories[cat_idx]
    await state.update_data(category=category)
    
    await state.set_state(TicketCreation.waiting_title)
    await callback.message.edit_text(
        f"📌 Категория: <b>{category}</b>\n\n"
        "Напишите краткое описание проблемы (заголовок):"
    )

@dp.message(TicketCreation.waiting_title)
async def receive_title(message: types.Message, state: FSMContext):
    """Получить заголовок заявки."""
    await state.update_data(title=message.text)
    
    await state.set_state(TicketCreation.waiting_description)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Пропустить фото", callback_data="skip_photo")]
    ])
    await message.answer(
        "📷 Прикрепите фото проблемы (если есть) или пропустите.",
        reply_markup=kb
    )

@dp.message(TicketCreation.waiting_description)
async def receive_description(message: types.Message, state: FSMContext):
    """Получить описание заявки."""
    await state.update_data(description=message.text)
    
    data = await state.get_data()
    user = db.get_user_by_telegram_id(message.from_user.id)
    ticket_number = generate_ticket_number()
    
    ticket_id = db.create_ticket(
        user_id=user['id'],
        ticket_number=ticket_number,
        title=data['title'],
        description=data['description'],
        category=data['category'],
        floor=data['floor'],
        workplace_id=data['workplace_id']
    )
    
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu")]
    ])
    
    await message.answer(
        f"✅ Заявка создана!\n\n"
        f"🎫 Номер заявки: <b>{ticket_number}</b>\n"
        f"📂 Категория: {data['category']}\n"
        f"🏢 Этаж: {data['floor']}\n\n"
        f"Администратор скоро с вами свяжется.",
        reply_markup=kb
    )

@dp.callback_query(F.data == "my_tickets")
async def view_my_tickets(callback: types.CallbackQuery):
    """Просмотр своих заявок."""
    user = db.get_user_by_telegram_id(callback.from_user.id)
    tickets = db.get_user_tickets(user['id'])
    
    if not tickets:
        await callback.message.edit_text("📋 У вас нет заявок.")
        return
    
    text = "📋 <b>Ваши заявки:</b>\n\n"
    for t in tickets:
        status_emoji = {"open": "🔵", "in_progress": "🟡", "closed": "🟢"}.get(t['status'], "⚪")
        text += f"{status_emoji} <b>{t['ticket_number']}</b>\n{t['title']}\n✍️ {t['description'][:50]}...\n\n"
    
    await callback.message.edit_text(text)

@dp.callback_query(F.data == "view_faq")
async def view_faq(callback: types.CallbackQuery):
    """Просмотр FAQ."""
    faq_items = db.get_faq()
    
    if not faq_items:
        text = "❓ FAQ пусто."
    else:
        text = "❓ <b>Часто задаваемые вопросы:</b>\n\n"
        for item in faq_items[:5]:
            text += f"<b>Q:</b> {item['question']}\n<b>A:</b> {item['answer']}\n\n"
    
    await callback.message.edit_text(text)

@dp.callback_query(F.data == "my_profile")
async def view_profile(callback: types.CallbackQuery):
    """Просмотр профиля."""
    user = db.get_user_by_telegram_id(callback.from_user.id)
    
    text = f"""👤 <b>Ваш профиль</b>

📛 Имя: {user['full_name']}
🆔 Telegram ID: {callback.from_user.id}
🏢 Этаж: {user['floor'] or 'Не указан'}
📍 Рабочее место: РМ-{user['workplace_id'] or 'Не указано'}
👨‍💼 Роль: {user['role'].upper()}
📅 Дата регистрации: {user['created_at']}
"""
    await callback.message.edit_text(text)

@dp.callback_query(F.data == "logout")
async def logout(callback: types.CallbackQuery):
    """Выход из профиля."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Авторизоваться", callback_data="login")]
    ])
    await callback.message.edit_text(
        "👋 Вы вышли из профиля.\n\nДля продолжения работы авторизуйтесь снова.",
        reply_markup=kb
    )

@dp.callback_query(F.data == "cancel_ticket")
async def cancel_ticket(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания заявки."""
    await state.clear()
    is_admin = callback.from_user.id in config.super_admin_ids
    await callback.message.edit_text(
        "❌ Создание заявки отменено.",
        reply_markup=get_main_menu_kb(is_admin)
    )

@dp.callback_query(F.data == "menu")
async def back_to_menu(callback: types.CallbackQuery):
    """Вернуться в главное меню."""
    is_admin = callback.from_user.id in config.super_admin_ids
    await callback.message.edit_text(
        "🏠 Главное меню",
        reply_markup=get_main_menu_kb(is_admin)
    )

async def main():
    """Запуск бота."""
    logger.info("🤖 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
