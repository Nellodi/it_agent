# Файл: it_ecosystem_bot/handlers/workplaces.py
import logging
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    create_workplace, get_workplace, get_workplace_equipment, get_all_workplaces,
    get_user_role
)
from utils.auth_checks import is_admin

logger = logging.getLogger(__name__)
router = Router()


class WorkplaceStates(StatesGroup):
    creating_workplace = State()
    entering_number = State()
    entering_department = State()
    entering_location = State()


# =================================================================
# 1. ПРОСМОТР ВСЕ РАБОЧИХ МЕСТ
# =================================================================

@router.message(F.text == "🏢 Рабочие места")
async def cmd_view_workplaces(message: types.Message):
    """Показывает список всех рабочих мест."""
    
    workplaces = await get_all_workplaces()
    
    if not workplaces:
        await message.answer(
            "📭 <b>В системе нет рабочих мест.</b>\n\n"
            "Администраторы могут добавить рабочие места командой /wp_create"
        )
        return
    
    text = f"🏢 <b>Все рабочие места</b> (всего: {len(workplaces)})\n\n"
    
    for idx, wp in enumerate(workplaces, 1):
        text += (
            f"{idx}. <b>РМ {wp['number']}</b>\n"
            f"   Отделение: {wp['department']}\n"
            f"   Местоположение: {wp['location']}\n\n"
        )
    
    kb = InlineKeyboardBuilder()
    
    # Кнопки для каждого рабочего места
    for wp in workplaces[:5]:
        kb.button(text=f"РМ {wp['number']}", callback_data=f"wp_detail_{wp['id']}")
    
    if len(workplaces) > 5:
        kb.button(text=f"📋 Ещё {len(workplaces) - 5}...", callback_data="wp_show_all")
    
    kb.adjust(2)
    
    if is_admin(message.from_user.id):
        kb.button(text="➕ Создать рабочее место", callback_data="wp_create_btn")
    
    await message.answer(text, reply_markup=kb.as_markup())


# =================================================================
# 2. СОЗДАНИЕ РАБОЧЕГО МЕСТА (АДМИН)
# =================================================================

@router.message(Command("wp_create"))
@router.callback_query(F.data == "wp_create_btn")
async def cmd_create_workplace(message_or_callback, state: FSMContext):
    """Начинает процесс создания нового рабочего места."""
    
    if isinstance(message_or_callback, types.Message):
        message = message_or_callback
        is_msg = True
    else:
        message = message_or_callback.message
        is_msg = False
    
    if not is_admin(message.from_user.id):
        if not is_msg:
            await message_or_callback.answer("🚫 Доступ запрещен.")
        else:
            await message.answer("🚫 Доступ запрещен.")
        return
    
    text = (
        "🏢 <b>Создание нового рабочего места</b>\n\n"
        "Введите <b>номер рабочего места</b> (например, 101, 102-А):"
    )
    
    if is_msg:
        await message.answer(text)
    else:
        await message.edit_text(text)
    
    await state.set_state(WorkplaceStates.entering_number)
    
    if not is_msg:
        await message_or_callback.answer()


@router.message(StateFilter(WorkplaceStates.entering_number))
async def enter_wp_number(message: types.Message, state: FSMContext):
    """Получает номер рабочего места."""
    
    wp_number = message.text.strip()
    await state.update_data(wp_number=wp_number)
    
    await message.answer(
        f"✅ <b>Номер рабочего места:</b> {wp_number}\n\n"
        f"Введите <b>отделение/отдел</b> (например, 'IT отдел', 'HR'):"
    )
    
    await state.set_state(WorkplaceStates.entering_department)


@router.message(StateFilter(WorkplaceStates.entering_department))
async def enter_wp_department(message: types.Message, state: FSMContext):
    """Получает отделение."""
    
    department = message.text.strip()
    await state.update_data(wp_department=department)
    
    await message.answer(
        f"✅ <b>Отделение:</b> {department}\n\n"
        f"Введите <b>местоположение</b> (например, '2 этаж, кабинет 201'):"
    )
    
    await state.set_state(WorkplaceStates.entering_location)


@router.message(StateFilter(WorkplaceStates.entering_location))
async def enter_wp_location(message: types.Message, state: FSMContext):
    """Получает местоположение и завершает создание."""
    
    location = message.text.strip()
    state_data = await state.get_data()
    
    wp_number = state_data['wp_number']
    department = state_data['wp_department']
    
    # Создаём рабочее место в БД
    success = await create_workplace(wp_number, department, location)
    
    if success:
        await message.answer(
            f"✅ <b>Рабочее место успешно создано!</b>\n\n"
            f"<b>Номер:</b> {wp_number}\n"
            f"<b>Отделение:</b> {department}\n"
            f"<b>Местоположение:</b> {location}"
        )
        logger.info(f"Admin {message.from_user.id} создал рабочее место {wp_number}")
    else:
        await message.answer(
            f"❌ <b>Ошибка при создании рабочего места.</b>\n"
            f"Возможно, рабочее место с номером '{wp_number}' уже существует."
        )
    
    await state.clear()


# =================================================================
# 3. ПРОСМОТР ДЕТАЛЕЙ РАБОЧЕГО МЕСТА
# =================================================================

@router.callback_query(F.data.startswith("wp_detail_"))
async def show_workplace_details(callback: types.CallbackQuery):
    """Показывает подробную информацию о рабочем месте."""
    
    wp_id = int(callback.data.replace("wp_detail_", ""))
    
    # Получаем информацию о рабочем месте
    wp = await get_workplace(wp_id)
    
    if not wp:
        await callback.message.edit_text("❌ <b>Рабочее место не найдено.</b>")
        await callback.answer()
        return
    
    # Получаем оборудование, закреплённое за этим местом
    equipment = await get_workplace_equipment(wp_id)
    
    # Формируем текст
    text = (
        f"🏢 <b>Рабочее место {wp['number']}</b>\n\n"
        f"<b>Отделение:</b> {wp['department']}\n"
        f"<b>Местоположение:</b> {wp['location']}\n"
        f"<b>Создано:</b> {wp['created_at']}\n\n"
    )
    
    if equipment:
        text += f"<b>Закреплённое оборудование ({len(equipment)}):</b>\n\n"
        for idx, item in enumerate(equipment, 1):
            text += (
                f"{idx}. <code>{item['inv_number']}</code>\n"
                f"   {item['model']} | {item['category']}\n"
            )
    else:
        text += "📭 <b>На этом рабочем месте нет оборудования.</b>\n"
    
    # Клавиатура
    kb = InlineKeyboardBuilder()
    kb.button(text="« Назад", callback_data="wp_back")
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 4. ПОКАЗАТЬ ВСЕ РАБОЧИЕ МЕСТА (РАЗВЁРНУТЫЙ СПИСОК)
# =================================================================

@router.callback_query(F.data == "wp_show_all")
async def show_all_workplaces(callback: types.CallbackQuery):
    """Показывает полный список всех рабочих мест."""
    
    workplaces = await get_all_workplaces()
    
    text = f"🏢 <b>Все рабочие места</b> (всего: {len(workplaces)})\n\n"
    
    for idx, wp in enumerate(workplaces, 1):
        text += (
            f"{idx}. <b>РМ {wp['number']}</b> - {wp['department']}\n"
            f"   Место: {wp['location']}\n\n"
        )
    
    kb = InlineKeyboardBuilder()
    
    # Кнопки для выбора рабочего места
    for wp in workplaces:
        kb.button(text=f"РМ {wp['number']}", callback_data=f"wp_detail_{wp['id']}")
    
    kb.adjust(3)
    kb.button(text="« Назад", callback_data="wp_back")
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# =================================================================
# 5. ВСПОМОГАТЕЛЬНЫЕ КНОПКИ
# =================================================================

@router.callback_query(F.data == "wp_back")
async def go_back_to_workplaces(callback: types.CallbackQuery):
    """Возвращает на главное меню рабочих мест."""
    
    workplaces = await get_all_workplaces()
    
    if not workplaces:
        await callback.message.edit_text("📭 <b>В системе нет рабочих мест.</b>")
        await callback.answer()
        return
    
    text = f"🏢 <b>Все рабочие места</b> (всего: {len(workplaces)})\n\n"
    
    for idx, wp in enumerate(workplaces, 1):
        text += (
            f"{idx}. <b>РМ {wp['number']}</b>\n"
            f"   Отделение: {wp['department']}\n"
            f"   Местоположение: {wp['location']}\n\n"
        )
    
    kb = InlineKeyboardBuilder()
    
    for wp in workplaces[:5]:
        kb.button(text=f"РМ {wp['number']}", callback_data=f"wp_detail_{wp['id']}")
    
    if len(workplaces) > 5:
        kb.button(text=f"📋 Ещё {len(workplaces) - 5}...", callback_data="wp_show_all")
    
    kb.adjust(2)
    
    if is_admin(callback.from_user.id):
        kb.button(text="➕ Создать рабочее место", callback_data="wp_create_btn")
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()
