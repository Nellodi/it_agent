import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import save_authorized_user, get_user_role, get_full_user_profile
from utils.excel_parser import ExcelParser
from keyboards.common import main_menu_keyboard, get_start_auth_keyboard

logger = logging.getLogger(__name__)
router = Router()

# Загрузка пользователей из Excel (старый механизм авторизации)
parser = ExcelParser(file_path="users.xlsx")
ALL_USERS = parser.load_users_data()


class AuthStates(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()


def get_menu_text(user_data: dict) -> str:
    role_emoji = "🛡 Администратор" if user_data.get("role") == "admin" else "👤 Пользователь"
    return (
        "✅ <b>Успешная авторизация!</b>\n\n"
        f"Рады видеть в IT-экосистеме, <b>{user_data['full_name']}</b>!\n"
        f"Ваша роль: {role_emoji}"
    )


@router.callback_query(F.data == "auth_login_btn")
async def start_login_process(callback: types.CallbackQuery, state: FSMContext):
    """Запрос логина (через Excel-справочник)."""
    await callback.message.edit_text("Введите <b>логин</b> (по данным из Excel):")
    await state.set_state(AuthStates.waiting_for_login)
    await callback.answer()


@router.message(AuthStates.waiting_for_login)
async def process_login(message: types.Message, state: FSMContext):
    login_input = message.text.strip().lower()
    logger.info(f"AUTH: запрос логина {login_input} от {message.from_user.id}")

    user_record = next((u for u in ALL_USERS if u["login"] == login_input), None)

    if user_record:
        await state.update_data(user_record=user_record)
        await message.answer("Логин найден. Введите <b>пароль</b>:")
        await state.set_state(AuthStates.waiting_for_password)
        logger.info(f"AUTH: логин '{login_input}' найден.")
    else:
        logger.warning(f"AUTH: логин '{login_input}' не найден в Excel.")
        await message.answer(
            "⚠️ Логин не найден. Проверьте ввод или обратитесь к администратору.",
            reply_markup=get_start_auth_keyboard(),
        )
        await state.clear()


@router.message(AuthStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password_input = message.text.strip()
    data = await state.get_data()
    user_record = data.get("user_record")

    if not user_record:
        await message.answer("Сессия авторизации сброшена. Нажмите /start и попробуйте снова.")
        await state.clear()
        return

    if user_record["password"] == password_input:
        user_id = message.from_user.id
        success = await save_authorized_user(user_id, user_record)

        if success:
            await state.clear()
            current_profile = await get_full_user_profile(user_id)
            user_role = current_profile["role"] if current_profile else user_record.get("role", "user")
            user_record["role"] = user_role

            await message.answer(get_menu_text(user_record), reply_markup=main_menu_keyboard(user_role))
            logger.info(f"AUTH: пользователь {user_record['login']} успешно авторизован (роль: {user_role}).")
        else:
            await message.answer("⚠️ Ошибка сохранения профиля. Попробуйте ещё раз.")
            await state.set_state(AuthStates.waiting_for_login)
    else:
        logger.warning(f"AUTH: неверный пароль для {user_record.get('login')}.")
        await message.answer("❌ Неверный пароль. Попробуйте снова.", reply_markup=get_start_auth_keyboard())
        await state.clear()


@router.message(Command("login"))
async def login_command(message: types.Message, state: FSMContext):
    """Поддержка текстовой команды /login."""
    await message.answer("Введите <b>логин</b> (по данным из Excel):")
    await state.set_state(AuthStates.waiting_for_login)
