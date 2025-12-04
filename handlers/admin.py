# -*- coding: utf-8 -*-
# Файл: it_ecosystem_bot/handlers/admin.py
import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # Импортируем Scheduler

from database import get_user_role, register_sys_admin, get_all_users_for_mailing
from utils.auth_checks import super_admin_required, is_super_admin
from keyboards.common import get_faq_admin_keyboard, get_mailing_schedule_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


class AdminStates(StatesGroup):
    waiting_for_admin_id = State()
    waiting_for_admin_name = State()
    waiting_for_admin_position = State()

    waiting_for_mailing_text = State()
    waiting_for_mailing_schedule = State()


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

    await message.answer(
        "📚 <b>Управление FAQ:</b>",
        reply_markup=get_faq_admin_keyboard()
    )


# =================================================================
# 2. РАССЫЛКА (ADMIN) - ИСПРАВЛЕН ВОЗВРАТ КНОПОК
# =================================================================

async def send_scheduled_mailing(bot: Bot, mailing_text: str):
    """Функция, которую вызывает планировщик (Scheduler)."""
    user_ids = await get_all_users_for_mailing()

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, mailing_text)
        except Exception:
            pass
    logger.info(f"SCHEDULER: Выполнена плановая рассылка.")


@router.message(F.text == "📢 Рассылка")
async def cmd_start_mailing(message: types.Message, state: FSMContext):
    user_role = await get_user_role(message.from_user.id)
    if user_role != 'admin':
        await message.answer("🚫 <b>Доступ запрещен.</b>")
        return

    await message.answer(
        "📢 <b>Новая рассылка</b>\n"
        "Введите текст сообщения для рассылки всем авторизованным пользователям:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AdminStates.waiting_for_mailing_text)


@router.message(AdminStates.waiting_for_mailing_text)
async def process_mailing_text(message: types.Message, state: FSMContext):
    mailing_text = message.text
    await state.update_data(mailing_text=mailing_text)

    await message.answer(
        "🗓️ <b>Выберите расписание:</b>",
        reply_markup=get_mailing_schedule_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_mailing_schedule)


@router.callback_query(AdminStates.waiting_for_mailing_schedule, F.data.startswith("mail_schedule_"))
async def process_mailing_schedule(callback: types.CallbackQuery, state: FSMContext, bot: Bot,
                                   scheduler: AsyncIOScheduler):
    action = callback.data
    data = await state.get_data()
    mailing_text = data['mailing_text']
    user_id = callback.from_user.id

    user_role = await get_user_role(user_id)
    await state.clear()

    if action == "mail_schedule_now":
        user_ids = await get_all_users_for_mailing()
        success_count = 0

        for u_id in user_ids:
            try:
                await bot.send_message(u_id, mailing_text)
                success_count += 1
            except Exception:
                pass

        await callback.message.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\nОтправлено: {success_count} сообщений."
        )

    elif action == "mail_schedule_weekly":
        # Планирование на будние дни (Пн-Пт в 19:00 UZT)
        scheduler.add_job(
            send_scheduled_mailing,
            trigger='cron',
            day_of_week='mon-fri',
            hour=19,
            minute=0,
            timezone='Asia/Tashkent',  # UZT time zone
            args=[bot, mailing_text]
        )
        await callback.message.edit_text(
            "✅ <b>Рассылка запланирована!</b>\n\n"
            "Будет отправляться автоматически каждый будний день (Пн-Пт) в 19:00 UZT."
        )

    # !!! ФИКС: Возвращаем главное меню с основными кнопками
    await callback.message.answer(
        "Выберите следующее действие:",
        reply_markup=main_menu_keyboard(user_role)
    )
    await callback.answer()


# =================================================================
# 3. РЕГИСТРАЦИЯ СИСТЕМНЫХ АДМИНИСТРАТОРОВ
# =================================================================

@router.message(Command("reg_admin"))
@super_admin_required
async def cmd_reg_admin(message: types.Message, state: FSMContext, **kwargs):
    await state.clear()
    await message.answer(
        "🔑 <b>Регистрация SysAdmin'а</b>\n"
        "Введите <b>Telegram ID</b> нового системного администратора...",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AdminStates.waiting_for_admin_id)


@router.message(AdminStates.waiting_for_admin_id)
async def process_admin_id(message: types.Message, state: FSMContext, **kwargs):
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
    admin_name = message.text.strip()
    await state.update_data(admin_name=admin_name)
    await message.answer("✅ ФИО принято. Введите <b>Должность</b>:")
    await state.set_state(AdminStates.waiting_for_admin_position)


@router.message(AdminStates.waiting_for_admin_position)
async def process_admin_position(message: types.Message, state: FSMContext, **kwargs):
    state_data = await state.get_data()
    admin_id = state_data['admin_id']
    admin_name = state_data['admin_name']
    admin_position = message.text.strip()

    success = await register_sys_admin(admin_id, admin_name, admin_position)

    if success:
        await message.answer(
            f"🎉 <b>Системный администратор {admin_name} успешно зарегистрирован!</b>"
        )
        logger.info(f"Супер-Админ {message.from_user.id} зарегистрировал SysAdmin'а {admin_id}.")
    else:
        await message.answer(
            "❌ <b>Ошибка регистрации.</b> Убедитесь, что пользователь авторизован в боте и попробуйте снова.")

    await state.clear()