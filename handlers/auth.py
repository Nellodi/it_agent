# Файл: it_ecosystem_bot/handlers/auth.py
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ИМПОРТЫ ИСПРАВЛЕНЫ
from utils.excel_parser import ExcelParser 
from database import save_authorized_user, get_user_role 
from keyboards.common import main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

# --- Загрузка данных при старте ---
parser = ExcelParser(file_path='users.xlsx') 
ALL_USERS = parser.load_users_data() 
# ----------------------------------

class AuthStates(StatesGroup):
    """Состояния FSM для процесса авторизации."""
    waiting_for_login = State()
    waiting_for_password = State()

def get_menu_text(user_data):
    """Генерация приветственного текста после авторизации."""
    role_emoji = "🛡️ Администратор" if user_data.get('role') == 'admin' else "👤 Пользователь"
    return (
        f"✅ **Авторизация успешна!**\n\n"
        f"Добро пожаловать в IT-Экосистему, **{user_data['full_name']}**!\n"
        f"Ваша роль: {role_emoji}"
    )

@router.message(Command("login")) # Только /login, без /start
async def cmd_login(message: types.Message, state: FSMContext):
    """Обработка команды /login, начинающей процесс авторизации."""
    
    user_role = await get_user_role(message.from_user.id)
    if user_role:
        await state.clear()
        await message.answer(
            f"👤 Вы уже авторизованы как **{user_role.upper()}**.", 
            reply_markup=main_menu_keyboard(user_role)
        )
        return

    if not ALL_USERS:
        await message.answer("❌ Системная ошибка: База сотрудников пуста или недоступна.")
        return
        
    await message.answer(
        "🏢 **IT-Экосистема: Вход**\n"
        "Введите ваш **Логин** из файла `users.xlsx`."
    )
    await state.set_state(AuthStates.waiting_for_login)

@router.message(AuthStates.waiting_for_login)
async def process_login(message: types.Message, state: FSMContext):
    """Обработка ввода логина."""
    
    login_input = message.text.strip().lower() 
    logger.info(f"AUTH: Пользователь {message.from_user.id} ввел логин: {login_input}")
    
    user_record = next((u for u in ALL_USERS if u['login'] == login_input), None)
    
    if user_record:
        await state.update_data(user_record=user_record)
        await message.answer("🔒 Логин принят. Введите ваш **Пароль**:")
        await state.set_state(AuthStates.waiting_for_password)
        logger.info(f"AUTH: Логин '{login_input}' найден. Запрос пароля.")
    else:
        logger.warning(f"AUTH: Неудачная попытка: Логин '{login_input}' не найден в базе.")
        await message.answer("❌ Ошибка: Логин не найден. Проверьте правильность ввода и попробуйте снова.")


@router.message(AuthStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    """Обработка ввода пароля и завершение авторизации."""
    
    password_input = message.text.strip()
    state_data = await state.get_data()
    user_record = state_data.get('user_record')
    
    if not user_record:
        await message.answer("⚠️ Сессия авторизации потеряна. Начните снова с команды /start.")
        await state.clear()
        return

    if user_record['password'] == password_input:
        telegram_id = message.from_user.id
        
        success = await save_authorized_user(telegram_id, user_record)
        
        if success:
            await state.clear()
            await message.answer(
                get_menu_text(user_record), 
                reply_markup=main_menu_keyboard(user_record['role']) 
            )
            logger.info(f"AUTH: Успешная авторизация: {user_record['login']} (Роль: {user_record['role']})")
        else:
            await message.answer("❌ Критическая ошибка: Не удалось завершить регистрацию в БД. Попробуйте снова.")
            await state.set_state(AuthStates.waiting_for_login)
            
    else:
        logger.warning(f"AUTH: Неверный пароль для логина {user_record['login']}.")
        await message.answer("❌ Ошибка: Неверный пароль. Попробуйте снова.")

@router.message(Command("cancel"))
@router.message(F.text.lower() == "отмена")
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отмена текущего FSM-состояния."""
    await state.clear()
    await message.answer("Операция отменена. Для входа используйте /login.")