# Файл: it_ecosystem_bot/handlers/start.py
import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import get_user_role
from keyboards.common import main_menu_keyboard, get_start_auth_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Обработка команды /start.
    Показывает меню, если авторизован, или кнопку входа.
    """

    user_id = message.from_user.id
    user_role = await get_user_role(user_id)

    await state.clear()

    if user_role:
        # Если авторизован, показываем главное меню
        await message.answer(
            f"👤 С возвращением! Вы авторизованы как <b>{user_role.upper()}</b>.",
            reply_markup=main_menu_keyboard(user_role)
        )
        logger.info(f"START: Пользователь {user_id} авторизован с ролью {user_role}.")
    else:
        # Если не авторизован, показываем кнопку входа
        await message.answer(
            "🏢 <b>IT-Экосистема</b>\n\n"
            "Добро пожаловать! Для начала работы необходимо войти в систему.",
            reply_markup=get_start_auth_keyboard()
        )
        logger.info(f"START: Пользователь {user_id} не авторизован. Предложена кнопка входа.")


@router.message(Command("check_role"))
async def cmd_check_role(message: types.Message):
    """Диагностическая команда для проверки текущей роли в БД (оставляем для отладки)."""
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