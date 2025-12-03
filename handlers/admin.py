# Файл: it_ecosystem_bot/handlers/admin.py
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_user_role, register_sys_admin
from utils.auth_checks import super_admin_required, is_super_admin

logger = logging.getLogger(__name__)
router = Router()


class AdminStates(StatesGroup):
    waiting_for_admin_id = State()
    waiting_for_admin_name = State()
    waiting_for_admin_position = State()


# =================================================================
# 1. СТАРТ АДМИН-ПАНЕЛИ (ТОЛЬКО ДЛЯ ADMIN)
# =================================================================

@router.message(F.text == "🛠️ Админ-панель")
async def cmd_admin_panel(message: types.Message):
    user_role = await get_user_role(message.from_user.id)
    if user_role != 'admin':
        await message.answer("🚫 <b>Доступ запрещен.</b>")
        return

    panel_text = "🛠️ <b>Админ-панель</b>\n\n"

    if is_super_admin(message.from_user.id):
        panel_text += "🔑 <b>СУПЕР АДМИН</b>:\n<code>/reg_admin</code> - Зарегистрировать нового SysAdmin'а."

    await message.answer(panel_text)


# =================================================================
# 2. РЕГИСТРАЦИЯ СИСТЕМНЫХ АДМИНИСТРАТОРОВ (ТОЛЬКО ДЛЯ SUPER_ADMIN)
# =================================================================

@router.message(Command("reg_admin"))
@super_admin_required
async def cmd_reg_admin(message: types.Message, state: FSMContext, **kwargs):
    """
    КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Добавлен **kwargs для приема лишних аргументов
    (dispatcher, bot, и т.д.), которые генерируются при работе декоратора.
    """
    await message.answer(
        "🔑 <b>Регистрация SysAdmin'а</b>\n"
        "Введите <b>Telegram ID</b> нового системного администратора (убедитесь, что он уже авторизовался хотя бы один раз)."
    )
    await state.set_state(AdminStates.waiting_for_admin_id)


@router.message(AdminStates.waiting_for_admin_id)
async def process_admin_id(message: types.Message, state: FSMContext, **kwargs):
    """Принимает ID и переходит к ФИО."""
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный числовой Telegram ID.")
        return

    await state.update_data(admin_id=admin_id)
    await message.answer("✅ ID принят. Введите <b>ФИО</b> администратора:")
    await state.set_state(AdminStates.waiting_for_admin_name)


@router.message(AdminStates.waiting_for_admin_name)
async def process_admin_name(message: types.Message, state: FSMContext, **kwargs):
    """Принимает ФИО и переходит к Должности."""
    admin_name = message.text.strip()
    await state.update_data(admin_name=admin_name)
    await message.answer("✅ ФИО принято. Введите <b>Должность</b> (например, 'Инженер 1й категории'):")
    await state.set_state(AdminStates.waiting_for_admin_position)


@router.message(AdminStates.waiting_for_admin_position)
async def process_admin_position(message: types.Message, state: FSMContext, **kwargs):
    """Принимает Должность и завершает регистрацию SysAdmin."""
    state_data = await state.get_data()
    admin_id = state_data['admin_id']
    admin_name = state_data['admin_name']
    admin_position = message.text.strip()

    success = await register_sys_admin(admin_id, admin_name, admin_position)

    if success:
        await message.answer(
            f"🎉 <b>Системный администратор {admin_name} успешно зарегистрирован!</b>\n"
            f"Его роль обновлена до 'admin' и он может принимать заявки."
        )
        logger.info(f"Супер-Админ {message.from_user.id} зарегистрировал SysAdmin'а {admin_id}.")
    else:
        await message.answer(
            "❌ <b>Ошибка регистрации.</b> Убедитесь, что пользователь авторизован в боте и попробуйте снова.")

    await state.clear()