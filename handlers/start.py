# Файл: it_ecosystem_bot/handlers/start.py
import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import get_user_role
from keyboards.common import main_menu_keyboard  # Убедитесь, что этот импорт есть

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Обработка команды /start.
    Проверяет авторизацию: если пользователь в БД, показывает меню; иначе предлагает авторизоваться.
    """

    user_role = await get_user_role(message.from_user.id)

    if user_role:
        await state.clear()
        # Используем HTML-форматирование
        await message.answer(
            f"👤 С возвращением! Вы авторизованы как <b>{user_role.upper()}</b>.",
            reply_markup=main_menu_keyboard(user_role)
        )
        logger.info(f"START: Пользователь {message.from_user.id} уже авторизован с ролью {user_role}.")
    else:
        await message.answer(
            "🏢 <b>IT-Экосистема</b>\n\n"
            "Добро пожаловать! Для начала работы необходимо войти в систему.\n"
            "Нажмите /login, чтобы начать авторизацию."
        )
        logger.info(f"START: Пользователь {message.from_user.id} не авторизован. Предложено /login.")


@router.message(Command("check_role"))
async def cmd_check_role(message: types.Message):
    """Диагностическая команда для проверки текущей роли в БД."""
    user_id = message.from_user.id
    user_role = await get_user_role(user_id)

    if user_role:
        await message.answer(
            f"🔑 <b>Проверка роли</b>:\n"
            f"Ваш Telegram ID: <code>{user_id}</code>\n"
            f"Ваша текущая роль в БД: <b>{user_role.upper()}</b>"
        )
    else:
        await message.answer(
            f"❌ Ваш Telegram ID <code>{user_id}</code> не найден в базе данных авторизованных пользователей.")