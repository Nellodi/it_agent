# -*- coding: utf-8 -*-
# Файл: it_ecosystem_bot/handlers/profile.py
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# !!! ИСПРАВЛЕНИЕ: ИМПОРТИРУЕМ main_menu_keyboard ВМЕСТО НЕЙЗВЕСТНОЙ ФУНКЦИИ
from database import get_user_role, get_admin_info, remove_authorized_user, get_user_tickets, get_user_equipment, \
    get_full_user_profile
from keyboards.common import confirm_logout_keyboard, main_menu_keyboard  # Используем main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


# =================================================================
# 1. ПРОФИЛЬ (Основная логика)
# =================================================================

@router.message(F.text == "👤 Мой профиль")
async def show_user_profile(message: types.Message):
    """Отображает полную информацию о профиле пользователя."""

    user_id = message.from_user.id
    profile_data = await get_full_user_profile(user_id)

    if not profile_data:
        await message.answer("⚠️ Сессия не найдена. Начните с команды /start.")
        return

    profile_text = (
        f"👤 <b>Профиль сотрудника</b>\n\n"
        f"<b>ФИО:</b> {profile_data['full_name']}\n"
        f"<b>Должность:</b> {profile_data['position']}\n"
        f"<b>Отдел:</b> {profile_data['department']}\n"
        f"<b>Логин:</b> <code>{profile_data['login']}</code>\n"
        f"<b>Email:</b> <code>{profile_data['email']}</code>\n"
        f"<b>Роль в системе:</b> {profile_data['role'].upper()}\n"
        f"<b>Дата входа:</b> {profile_data['authorized_at']}"
    )

    if profile_data['role'] == 'admin':
        admin_info = await get_admin_info(user_id)
        if admin_info:
            rating_display = f"{admin_info['avg_rating']}/5.0 ⭐️"
            profile_text += f"\n\n<b>Средний рейтинг SysAdmin:</b> {rating_display}"

    # Клавиатура с опциями профиля
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 История запросов", callback_data="profile_tickets")
    kb.button(text="💻 Мое оборудование", callback_data="profile_equipment")
    kb.adjust(1)

    if profile_data['role'] == 'admin':
        kb.button(text="📊 Статистика", callback_data="profile_stats")

    kb.button(text="🚪 Выход", callback_data="profile_logout")

    await message.answer(profile_text, reply_markup=kb.as_markup())


# =================================================================
# 2. ИСТОРИЯ ЗАЯВОК ПОЛЬЗОВАТЕЛЯ (Callback)
# =================================================================

@router.callback_query(F.data == "profile_tickets")
async def show_user_tickets_history(callback: types.CallbackQuery):
    """Показывает историю заявок пользователя."""

    user_id = callback.from_user.id
    if not await get_user_role(user_id):
        await callback.answer("⚠️ Сессия не найдена.", show_alert=True)
        return

    tickets = await get_user_tickets(user_id)

    if not tickets:
        await callback.message.edit_text(
            "📭 <b>У вас нет заявок.</b>",
            reply_markup=InlineKeyboardBuilder().button(text="« Назад", callback_data="profile_back").as_markup()
        )
        await callback.answer()
        return

    # Формируем список заявок
    text = f"📋 <b>Ваши запросы</b> (всего: {len(tickets)})\n\n"

    status_emoji = {
        'open': '🔴', 'in_progress': '🟡', 'on_hold': '🟠',
        'closed': '✅', 'await_rating': '⭐️'
    }

    for idx, ticket in enumerate(tickets, 1):
        emoji = status_emoji.get(ticket['status'], '•')
        text += (
            f"{idx}. <code>{ticket['number']}</code> {emoji}\n"
            f"   <b>{ticket['title'][:40]}...</b>\n"
            f"   Статус: {ticket['status'].upper()}\n"
            f"   Создана: {ticket['created_at'].split(' ')[0]}\n\n"
        )

    kb = InlineKeyboardBuilder()
    kb.button(text="« Назад к профилю", callback_data="profile_back")

    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 3. ОБОРУДОВАНИЕ ПОЛЬЗОВАТЕЛЯ (Callback)
# =================================================================

@router.callback_query(F.data == "profile_equipment")
async def show_user_equipment_in_profile(callback: types.CallbackQuery):
    """Показывает оборудование, назначенное пользователю."""

    user_id = callback.from_user.id
    equipment_list = await get_user_equipment(user_id)

    if not equipment_list:
        await callback.message.edit_text(
            "📭 <b>Вам не назначено оборудование.</b>",
            reply_markup=InlineKeyboardBuilder().button(text="« Назад", callback_data="profile_back").as_markup()
        )
        await callback.answer()
        return

    # Формируем список оборудования
    text = f"💻 <b>Ваше оборудование</b> (всего: {len(equipment_list)})\n\n"

    for idx, item in enumerate(equipment_list, 1):
        text += (
            f"{idx}. <b>{item['model']}</b> (<code>{item['inv_number']}</code>)\n"
            f"   Категория: {item['category']}\n"
            f"   Назначено: {item['assigned_at'].split(' ')[0]}\n\n"
        )

    kb = InlineKeyboardBuilder()
    kb.button(text="« Назад к профилю", callback_data="profile_back")

    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 4. СТАТИСТИКА АДМИНИСТРАТОРА (Callback)
# =================================================================

@router.callback_query(F.data == "profile_stats")
async def show_admin_statistics(callback: types.CallbackQuery):
    """Показывает статистику администратора."""

    user_id = callback.from_user.id
    admin_info = await get_admin_info(user_id)

    if not admin_info:
        await callback.message.edit_text(
            "❌ <b>Информация о администраторе не найдена.</b>",
            reply_markup=InlineKeyboardBuilder().button(text="« Назад", callback_data="profile_back").as_markup()
        )
        await callback.answer()
        return

    text = (
        f"📊 <b>Статистика администратора</b>\n\n"
        f"<b>ФИО:</b> {admin_info['full_name']}\n"
        f"<b>Средний рейтинг:</b> {admin_info['avg_rating']}/5.0 ⭐️\n"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="« Назад к профилю", callback_data="profile_back")

    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 5. ВОЗВРАТ К ПРОФИЛЮ (Callback)
# =================================================================

@router.callback_query(F.data == "profile_back")
async def back_to_profile(callback: types.CallbackQuery):
    """Возвращает к основному окну профиля."""

    user_id = callback.from_user.id

    profile_data = await get_full_user_profile(user_id)
    if not profile_data:
        await callback.message.edit_text("⚠️ Сессия не найдена. Нажмите /start.")
        await callback.answer()
        return

    profile_text = (
        f"👤 <b>Профиль сотрудника</b>\n\n"
        f"<b>ФИО:</b> {profile_data['full_name']}\n"
        f"<b>Должность:</b> {profile_data['position']}\n"
        f"<b>Отдел:</b> {profile_data['department']}\n"
        f"<b>Логин:</b> <code>{profile_data['login']}</code>\n"
        f"<b>Email:</b> <code>{profile_data['email']}</code>\n"
        f"<b>Роль в системе:</b> {profile_data['role'].upper()}\n"
        f"<b>Дата входа:</b> {profile_data['authorized_at']}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="📋 История запросов", callback_data="profile_tickets")
    kb.button(text="💻 Мое оборудование", callback_data="profile_equipment")
    kb.adjust(1)

    if profile_data['role'] == 'admin':
        kb.button(text="📊 Статистика", callback_data="profile_stats")

    kb.button(text="🚪 Выход", callback_data="profile_logout")

    await callback.message.edit_text(profile_text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 6. ВЫХОД (Logout) - Message & Callback
# =================================================================

@router.callback_query(F.data == "profile_logout")
async def request_logout_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Запрашивает подтверждение выхода из аккаунта (через инлайн-кнопку в профиле)."""

    await callback.message.edit_text(
        "❓ Вы уверены, что хотите выйти из аккаунта?",
        reply_markup=confirm_logout_keyboard()
    )
    await callback.answer()


@router.message(F.text == "🚪 Выход из профиля")
async def request_logout_confirmation_msg(message: types.Message, state: FSMContext):
    """Запрашивает подтверждение выхода из аккаунта (вариант с текстовой кнопкой)."""

    await state.clear()

    await message.answer(
        "❓ Вы уверены, что хотите выйти из аккаунта?\n\n"
        "Вы потеряете доступ к функциям бота до повторной авторизации.",
        reply_markup=confirm_logout_keyboard()
    )


@router.callback_query(F.data == "logout_confirm")
async def process_logout_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение выхода."""
    user_id = callback.from_user.id
    success = await remove_authorized_user(user_id)
    await state.clear()

    if success:
        await callback.message.edit_text("✅ Вы успешно вышли из аккаунта.", reply_markup=None)
        await callback.message.answer(
            "Для продолжения работы используйте команду /start.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        logger.info(f"LOGOUT: Пользователь {user_id} успешно вышел.")
    else:
        await callback.message.edit_text("❌ Произошла ошибка при выходе. Попробуйте нажать '🚪 Выход' снова.")
        logger.error(f"LOGOUT: Ошибка удаления пользователя {user_id} из БД.")
    await callback.answer()


@router.callback_query(F.data == "logout_cancel")
async def process_logout_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает отмену выхода."""
    await state.clear()
    role = await get_user_role(callback.from_user.id)

    # Чтобы вернуть главное меню, нужно вызвать main_menu_keyboard
    if role:
        from keyboards.common import main_menu_keyboard
        await callback.message.edit_text("Операция отменена. Вы остаетесь в системе.", reply_markup=None)
        await callback.message.answer("Выберите действие:", reply_markup=main_menu_keyboard(role))
    else:
        await callback.message.edit_text("Не удалось определить роль. Нажмите /start.", reply_markup=None)
    await callback.answer()