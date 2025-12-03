# Файл: it_ecosystem_bot/handlers/profile.py
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_user_role, get_admin_info, remove_authorized_user, get_user_tickets, get_user_equipment
from keyboards.common import confirm_logout_keyboard  # Импорт новой клавиатуры

logger = logging.getLogger(__name__)
router = Router()


# =================================================================
# 1. ПРОФИЛЬ (Основная логика)
# =================================================================

@router.message(F.text == "👤 Профиль")
async def show_user_profile(message: types.Message):
    """Отображает информацию о профиле пользователя."""

    user_id = message.from_user.id
    user_role = await get_user_role(user_id)

    if not user_role:
        await message.answer("⚠️ Сессия не найдена. Начните с команды /start.")
        return

    profile_text = (
        f"👤 <b>Ваш Профиль</b>\n\n"
        f"<b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"<b>Роль в системе:</b> {user_role.upper()}\n"
    )

    if user_role == 'admin':
        admin_info = await get_admin_info(user_id)
        if admin_info:
            rating_display = f"{admin_info['avg_rating']}/5.0 ⭐️"
            profile_text += f"\n<b>Средний рейтинг:</b> {rating_display}\n"

    # Показываем основные опции профиля
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 История заявок", callback_data="profile_tickets")
    kb.button(text="💻 Мое оборудование", callback_data="profile_equipment")
    kb.adjust(1)
    
    if user_role == 'admin':
        kb.button(text="📊 Статистика", callback_data="profile_stats")
    
    kb.button(text="🚪 Выход", callback_data="profile_logout")

    await message.answer(profile_text, reply_markup=kb.as_markup())


# =================================================================
# 2. ИСТОРИЯ ЗАЯВОК ПОЛЬЗОВАТЕЛЯ
# =================================================================

@router.callback_query(F.data == "profile_tickets")
async def show_user_tickets_history(callback: types.CallbackQuery):
    """Показывает историю заявок пользователя."""
    
    user_id = callback.from_user.id
    tickets = await get_user_tickets(user_id)
    
    if not tickets:
        await callback.message.edit_text(
            "📭 <b>У вас нет заявок.</b>\n\n"
            "Создайте новую заявку в меню 'Помощь'.",
            reply_markup=InlineKeyboardBuilder().button(text="« Назад", callback_data="profile_back").as_markup()
        )
        await callback.answer()
        return
    
    # Формируем список заявок
    text = f"📋 <b>Ваши заявки</b> (всего: {len(tickets)})\n\n"
    
    status_emoji = {
        'open': '🟢',
        'in_progress': '🟡',
        'on_hold': '🟠',
        'closed': '✅',
        'await_rating': '⭐️'
    }
    
    for idx, ticket in enumerate(tickets, 1):
        emoji = status_emoji.get(ticket['status'], '•')
        text += (
            f"{idx}. <code>{ticket['number']}</code> {emoji}\n"
            f"   <b>{ticket['title'][:40]}</b>\n"
            f"   Статус: {ticket['status']}\n"
            f"   Создана: {ticket['created']}\n\n"
        )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="« Назад к профилю", callback_data="profile_back")
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 3. ОБОРУДОВАНИЕ ПОЛЬЗОВАТЕЛЯ
# =================================================================

@router.callback_query(F.data == "profile_equipment")
async def show_user_equipment_in_profile(callback: types.CallbackQuery):
    """Показывает оборудование, назначенное пользователю."""
    
    user_id = callback.from_user.id
    equipment_list = await get_user_equipment(user_id)
    
    if not equipment_list:
        await callback.message.edit_text(
            "📭 <b>Вам не назначено оборудование.</b>\n\n"
            "Обратитесь к администратору для получения оборудования.",
            reply_markup=InlineKeyboardBuilder().button(text="« Назад", callback_data="profile_back").as_markup()
        )
        await callback.answer()
        return
    
    # Формируем список оборудования
    text = f"💻 <b>Ваше оборудование</b> (всего: {len(equipment_list)})\n\n"
    
    for idx, item in enumerate(equipment_list, 1):
        text += (
            f"{idx}. <code>{item['inv_number']}</code>\n"
            f"   <b>Модель:</b> {item['model']}\n"
            f"   <b>Категория:</b> {item['category']}\n"
            f"   <b>Серийный номер:</b> {item['serial']}\n"
            f"   <b>Назначено:</b> {item['assigned_at']}\n\n"
        )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="« Назад к профилю", callback_data="profile_back")
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 4. СТАТИСТИКА АДМИНИСТРАТОРА
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
    
    # Формируем статистику
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
# 5. ВОЗВРАТ К ПРОФИЛЮ
# =================================================================

@router.callback_query(F.data == "profile_back")
async def back_to_profile(callback: types.CallbackQuery):
    """Возвращает к профилю пользователя."""
    
    user_id = callback.from_user.id
    user_role = await get_user_role(user_id)
    
    if not user_role:
        await callback.message.edit_text("⚠️ Сессия не найдена. Начните с команды /start.")
        await callback.answer()
        return
    
    profile_text = (
        f"👤 <b>Ваш Профиль</b>\n\n"
        f"<b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"<b>Роль в системе:</b> {user_role.upper()}\n"
    )

    if user_role == 'admin':
        admin_info = await get_admin_info(user_id)
        if admin_info:
            rating_display = f"{admin_info['avg_rating']}/5.0 ⭐️"
            profile_text += f"\n<b>Средний рейтинг:</b> {rating_display}\n"

    kb = InlineKeyboardBuilder()
    kb.button(text="📋 История заявок", callback_data="profile_tickets")
    kb.button(text="💻 Мое оборудование", callback_data="profile_equipment")
    kb.adjust(1)
    
    if user_role == 'admin':
        kb.button(text="📊 Статистика", callback_data="profile_stats")
    
    kb.button(text="🚪 Выход", callback_data="profile_logout")
    
    await callback.message.edit_text(profile_text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 6. ВЫХОД (Logout)
# =================================================================

@router.callback_query(F.data == "profile_logout")
async def request_logout_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Запрашивает подтверждение выхода из аккаунта."""

    await state.clear()

    await callback.message.edit_text(
        "❓ Вы уверены, что хотите выйти из аккаунта?\n\n"
        "Вы потеряете доступ к функциям бота до повторной авторизации.",
        reply_markup=confirm_logout_keyboard()
    )
    await callback.answer()


@router.message(F.text == "🚪 Выход")
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

    if success:
        await state.clear()
        await callback.message.edit_text("✅ Вы успешно вышли из аккаунта.", reply_markup=None)

        await callback.message.answer(
            "Для продолжения работы используйте команду /login.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        logger.info(f"LOGOUT: Пользователь {user_id} успешно вышел.")
    else:
        await callback.message.edit_text("❌ Произошла ошибка при выходе. Попробуйте нажать '🚪 Выход' снова.")

    await callback.answer()


@router.callback_query(F.data == "logout_cancel")
async def process_logout_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает отмену выхода и возвращает пользователя обратно."""

    user_role = await get_user_role(callback.from_user.id)

    if user_role:
        from keyboards.common import main_menu_keyboard

        await callback.message.edit_text(
            "Операция отменена. Вы остаетесь в системе.",
            reply_markup=None
        )

        await callback.message.answer(
            "Выберите действие:",
            reply_markup=main_menu_keyboard(user_role)
        )
    else:
        await callback.message.edit_text("⚠️ Сессия потеряна. Нажмите /start для повторной авторизации.",
                                         reply_markup=None)

    await callback.answer()