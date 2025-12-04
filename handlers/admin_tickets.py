# Файл: it_ecosystem_bot/handlers/admin_tickets.py
# -*- coding: utf-8 -*-
import logging
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    get_all_tickets, get_ticket_history, assign_ticket_to_admin,
    update_ticket_status, get_user_role
)
from utils.auth_checks import is_admin

logger = logging.getLogger(__name__)
router = Router()


class TicketManagementStates(StatesGroup):
    viewing_tickets = State()
    filtering_tickets = State()
    selecting_ticket = State()
    choosing_action = State()
    changing_status = State()
    adding_comment = State()


# =================================================================
# 1. ПРОСМОТР ВСЕ ЗАЯВОК (АДМИН МЕНЮ)
# =================================================================

@router.message(F.text == "📋 Все заявки")
async def cmd_view_all_tickets(message: types.Message):
    """Показывает список всех заявок с фильтрацией."""
    
    if not is_admin(message.from_user.id):
        await message.answer("🚫 <b>Доступ запрещен.</b> Только администраторы могут просматривать заявки.")
        return
    
    # Получаем все заявки
    tickets = await get_all_tickets()
    
    if not tickets:
        await message.answer("📭 <b>Нет заявок в системе.</b>")
        return
    
    # Формируем сообщение со списком заявок
    text = "📋 <b>Все заявки в системе</b>\n\n"
    
    # Группируем по статусам
    statuses = {}
    for ticket in tickets:
        status = ticket['status']
        if status not in statuses:
            statuses[status] = []
        statuses[status].append(ticket)
    
    # Формируем текст с группировкой
    status_emoji = {
        'open': '🟢',
        'in_progress': '🟡',
        'on_hold': '🟠',
        'closed': '✅',
        'await_rating': '⭐️'
    }
    
    for status, items in statuses.items():
        emoji = status_emoji.get(status, '•')
        text += f"\n{emoji} <b>{status.upper()}</b> ({len(items)})\n"
        for ticket in items[:5]:  # Показываем первые 5 заявок
            text += f"  • <code>{ticket['number']}</code> - {ticket['title'][:30]}\n"
        if len(items) > 5:
            text += f"  ... и ещё {len(items) - 5}\n"
    
    text += "\n<b>Используйте команду для фильтрации:</b>\n"
    text += "/filter_tickets - фильтровать по статусу, приоритету, отделу"
    
    await message.answer(text)


@router.message(Command("filter_tickets"))
async def cmd_filter_tickets(message: types.Message, state: FSMContext):
    """Открывает меню фильтрации заявок."""
    
    if not is_admin(message.from_user.id):
        await message.answer("🚫 <b>Доступ запрещен.</b>")
        return
    
    # Создаём клавиатуру с опциями фильтрации
    kb = InlineKeyboardBuilder()
    
    # Фильтр по статусам
    kb.button(text="🟢 Открытые", callback_data="filter_status_open")
    kb.button(text="🟡 В работе", callback_data="filter_status_in_progress")
    kb.adjust(2)
    
    kb.button(text="🟠 На удержании", callback_data="filter_status_on_hold")
    kb.button(text="✅ Закрытые", callback_data="filter_status_closed")
    kb.adjust(2)
    
    kb.button(text="⭐️ Ожидают рейтинг", callback_data="filter_status_await_rating")
    kb.adjust(1)
    
    kb.button(text="« Назад", callback_data="filter_cancel")
    
    await message.answer("🔍 <b>Фильтрация заявок</b>\n\nВыберите фильтр:", reply_markup=kb.as_markup())
    await state.set_state(TicketManagementStates.filtering_tickets)


@router.callback_query(F.data.startswith("filter_status_"), StateFilter(TicketManagementStates.filtering_tickets))
async def handle_filter_status(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает фильтр по статусу."""
    
    status = callback.data.replace("filter_status_", "")
    
    # Получаем отфильтрованные заявки
    tickets = await get_all_tickets(status=status)
    
    if not tickets:
        await callback.message.edit_text(f"📭 <b>Нет заявок со статусом '{status}'.</b>")
        await callback.answer()
        return
    
    # Формируем список заявок
    text = f"📋 <b>Заявки со статусом: {status.upper()}</b>\n\n"
    
    for idx, ticket in enumerate(tickets[:20], 1):  # Показываем максимум 20
        admin_name = "—"
        if ticket['admin_id']:
            admin_name = f"Admin {ticket['admin_id']}"
        
        text += (
            f"{idx}. <code>{ticket['number']}</code>\n"
            f"   Заголовок: {ticket['title'][:50]}\n"
            f"   Приоритет: {ticket['priority']}\n"
            f"   От пользователя: {ticket['user_name'] or 'Неизвестен'}\n"
            f"   Назначен: {admin_name}\n\n"
        )
    
    if len(tickets) > 20:
        text += f"... и ещё {len(tickets) - 20} заявок"
    
    # Клавиатура для выбора заявки
    kb = InlineKeyboardBuilder()
    for ticket in tickets[:10]:
        kb.button(text=f"{ticket['number']} - {ticket['title'][:25]}", 
                 callback_data=f"ticket_detail_{ticket['id']}")
    kb.adjust(1)
    
    kb.button(text="« Назад", callback_data="filter_cancel")
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "filter_cancel")
async def handle_filter_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет фильтрацию."""
    
    await callback.message.delete()
    await state.clear()
    await callback.answer()


# =================================================================
# 2. ПРОСМОТР ДЕТАЛЕЙ ЗАЯВКИ И УПРАВЛЕНИЕ
# =================================================================

@router.callback_query(F.data.startswith("ticket_detail_"))
async def show_ticket_details(callback: types.CallbackQuery, state: FSMContext):
    """Показывает подробную информацию о заявке."""
    
    ticket_id = int(callback.data.replace("ticket_detail_", ""))
    
    # Получаем все заявки и ищем нужную
    all_tickets = await get_all_tickets()
    ticket = next((t for t in all_tickets if t['id'] == ticket_id), None)
    
    if not ticket:
        await callback.message.edit_text("❌ <b>Заявка не найдена.</b>")
        await callback.answer()
        return
    
    # Сохраняем в стейт
    await state.update_data(current_ticket=ticket)
    
    # Получаем историю изменений
    history = await get_ticket_history(ticket_id)
    
    # Формируем подробный текст
    admin_name = "—"
    if ticket['admin_id']:
        admin_name = f"Admin {ticket['admin_id']}"
    
    text = (
        f"📋 <b>Заявка {ticket['number']}</b>\n\n"
        f"<b>Статус:</b> {ticket['status']}\n"
        f"<b>Приоритет:</b> {ticket['priority']}\n"
        f"<b>Категория:</b> {ticket['category']}\n"
        f"<b>Заголовок:</b> {ticket['title']}\n"
        f"<b>Описание:</b> {ticket['title']}\n\n"
        f"<b>От:</b> {ticket['user_name'] or 'Неизвестен'} (ID: {ticket['user_id']})\n"
        f"<b>Отделение:</b> {ticket['department'] or '—'}\n"
        f"<b>Создана:</b> {ticket['created_at']}\n"
        f"<b>Назначена:</b> {admin_name}\n"
    )
    
    if history:
        text += f"\n<b>История изменений:</b> {len(history)} записей"
    
    # Клавиатура с действиями
    kb = InlineKeyboardBuilder()
    
    if not ticket['admin_id']:
        kb.button(text="✋ Назначить на себя", callback_data=f"ticket_assign_{ticket_id}")
    
    kb.button(text="📝 Изменить статус", callback_data=f"ticket_status_{ticket_id}")
    kb.button(text="📜 История", callback_data=f"ticket_history_{ticket_id}")
    kb.adjust(1)
    
    kb.button(text="« Назад", callback_data="filter_cancel")
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 3. НАЗНАЧЕНИЕ ЗАЯВКИ НА АДМИНИСТРАТОРА
# =================================================================

@router.callback_query(F.data.startswith("ticket_assign_"))
async def handle_assign_ticket(callback: types.CallbackQuery, state: FSMContext):
    """Назначает заявку на текущего администратора."""
    
    ticket_id = int(callback.data.replace("ticket_assign_", ""))
    admin_id = callback.from_user.id
    
    # Назначаем заявку
    success = await assign_ticket_to_admin(ticket_id, admin_id)
    
    if success:
        await callback.message.edit_text(
            "✅ <b>Заявка успешно назначена на вас!</b>\n\n"
            "Теперь вы можете изменять её статус и добавлять комментарии."
        )
        logger.info(f"Admin {admin_id} назначил заявку {ticket_id} на себя")
    else:
        await callback.message.edit_text("❌ <b>Ошибка при назначении заявки.</b>")
    
    await callback.answer()


# =================================================================
# 4. ИЗМЕНЕНИЕ СТАТУСА ЗАЯВКИ
# =================================================================

@router.callback_query(F.data.startswith("ticket_status_"))
async def choose_new_status(callback: types.CallbackQuery, state: FSMContext):
    """Показывает меню выбора нового статуса."""
    
    ticket_id = int(callback.data.replace("ticket_status_", ""))
    await state.update_data(current_ticket_id=ticket_id)
    
    # Статусы с эмодзи
    statuses = [
        ("🟢 Открыта", "open"),
        ("🟡 В работе", "in_progress"),
        ("🟠 На удержании", "on_hold"),
        ("✅ Закрыта", "closed"),
        ("⭐️ Ожидает рейтинг", "await_rating"),
    ]
    
    kb = InlineKeyboardBuilder()
    
    for emoji_text, status_code in statuses:
        kb.button(text=emoji_text, callback_data=f"newstatus_{status_code}_{ticket_id}")
    
    kb.adjust(1)
    kb.button(text="« Назад", callback_data=f"ticket_detail_{ticket_id}")
    
    await callback.message.edit_text(
        "📝 <b>Выберите новый статус заявки:</b>",
        reply_markup=kb.as_markup()
    )
    await state.set_state(TicketManagementStates.changing_status)
    await callback.answer()


@router.callback_query(F.data.startswith("newstatus_"), StateFilter(TicketManagementStates.changing_status))
async def confirm_status_change(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждает смену статуса и запрашивает комментарий."""
    
    data_parts = callback.data.replace("newstatus_", "").split("_")
    new_status = "_".join(data_parts[:-1])  # Может быть "on_hold" или "in_progress"
    ticket_id = int(data_parts[-1])
    
    await state.update_data(new_status=new_status, ticket_id_for_status=ticket_id)
    
    text = (
        f"💬 <b>Хотите добавить комментарий?</b>\n\n"
        f"Ответьте сообщением или нажмите 'Пропустить' для смены статуса без комментария."
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="Пропустить", callback_data=f"skip_comment_{ticket_id}_{new_status}")
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await state.set_state(TicketManagementStates.adding_comment)
    await callback.answer()


@router.message(StateFilter(TicketManagementStates.adding_comment))
async def handle_comment(message: types.Message, state: FSMContext):
    """Обрабатывает комментарий и обновляет статус."""
    
    state_data = await state.get_data()
    ticket_id = state_data.get('ticket_id_for_status')
    new_status = state_data.get('new_status')
    comment = message.text
    admin_id = message.from_user.id
    
    # Обновляем статус с комментарием
    success = await update_ticket_status(ticket_id, new_status, admin_id, comment)
    
    if success:
        await message.answer(
            f"✅ <b>Статус заявки обновлен!</b>\n\n"
            f"Новый статус: {new_status}\n"
            f"Комментарий: {comment}"
        )
        logger.info(f"Admin {admin_id} обновил статус заявки {ticket_id} на {new_status}")
    else:
        await message.answer("❌ <b>Ошибка при обновлении статуса.</b>")
    
    await state.clear()


@router.callback_query(F.data.startswith("skip_comment_"))
async def skip_comment(callback: types.CallbackQuery, state: FSMContext):
    """Пропускает комментарий и обновляет статус."""
    
    data_parts = callback.data.replace("skip_comment_", "").split("_")
    ticket_id = int(data_parts[0])
    new_status = "_".join(data_parts[1:])
    admin_id = callback.from_user.id
    
    # Обновляем статус без комментария
    success = await update_ticket_status(ticket_id, new_status, admin_id, None)
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Статус заявки обновлен!</b>\n\n"
            f"Новый статус: {new_status}"
        )
        logger.info(f"Admin {admin_id} обновил статус заявки {ticket_id} на {new_status}")
    else:
        await callback.message.edit_text("❌ <b>Ошибка при обновлении статуса.</b>")
    
    await state.clear()
    await callback.answer()


# =================================================================
# 5. ПРОСМОТР ИСТОРИИ ЗАЯВКИ
# =================================================================

@router.callback_query(F.data.startswith("ticket_history_"))
async def show_ticket_history(callback: types.CallbackQuery):
    """Показывает историю изменений заявки."""
    
    ticket_id = int(callback.data.replace("ticket_history_", ""))
    
    history = await get_ticket_history(ticket_id)
    
    if not history:
        await callback.message.edit_text("📜 <b>История изменений</b>\n\n❌ Нет записей в истории.")
        await callback.answer()
        return
    
    text = "📜 <b>История изменений заявки</b>\n\n"
    
    for entry in history:
        text += (
            f"<b>{entry['changed_at']}</b>\n"
            f"  {entry['old_status']} → {entry['new_status']}\n"
            f"  Изменил: {entry['changed_by_name'] or 'Система'}\n"
            f"  Комментарий: {entry['comment'] or '—'}\n\n"
        )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="« Назад", callback_data=f"ticket_detail_{ticket_id}")
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@router.callback_query(F.data == "menu_all_tickets")
async def menu_all_tickets(callback: types.CallbackQuery):
    """�������� ���� ������ �� inline-����."""
    await cmd_view_all_tickets(callback.message)
    await callback.answer()
