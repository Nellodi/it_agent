# Файл: it_ecosystem_bot/handlers/equipment.py
import logging
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    create_equipment, get_all_equipment, get_equipment, delete_equipment,
    assign_equipment_to_user, get_user_equipment, get_user_role
)
from utils.auth_checks import is_admin
from utils.inventory_generator import generate_inventory_number, get_available_categories

logger = logging.getLogger(__name__)
router = Router()


class EquipmentStates(StatesGroup):
    viewing_equipment = State()
    creating_equipment = State()
    choosing_category = State()
    entering_model = State()
    entering_serial = State()
    managing_equipment = State()
    assigning_user = State()
    confirming_assignment = State()


# =================================================================
# 1. ПРОСМОТР ВСЕ ОБОРУДОВАНИЯ (АДМИН МЕНЮ)
# =================================================================

@router.message(F.text == "💻 Оборудование")
async def cmd_view_equipment(message: types.Message):
    """Показывает статистику оборудования."""
    
    if not is_admin(message.from_user.id):
        await message.answer("🚫 <b>Доступ запрещен.</b> Только администраторы могут управлять оборудованием.")
        return
    
    # Получаем статистику оборудования
    available = await get_all_equipment(status='available')
    assigned = await get_all_equipment(status='assigned')
    
    text = (
        f"💻 <b>Инвентарный учет оборудования</b>\n\n"
        f"✅ Доступное: {len(available)}\n"
        f"👤 Назначено пользователям: {len(assigned)}\n\n"
        f"<b>Команды:</b>\n"
        f"/eq_create - Добавить новое оборудование\n"
        f"/eq_list - Список всего оборудования\n"
        f"/eq_assign - Назначить оборудование пользователю\n"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить оборудование", callback_data="eq_create_btn")
    kb.button(text="📋 Список оборудования", callback_data="eq_list_btn")
    kb.button(text="👤 Назначить пользователю", callback_data="eq_assign_btn")
    kb.adjust(1)
    
    await message.answer(text, reply_markup=kb.as_markup())


# =================================================================
# 2. СОЗДАНИЕ НОВОГО ОБОРУДОВАНИЯ
# =================================================================

@router.message(Command("eq_create"))
@router.callback_query(F.data == "eq_create_btn")
async def cmd_create_equipment(message_or_callback, state: FSMContext):
    """Начинает процесс создания нового оборудования."""
    
    # Определяем тип входа
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
    
    # Показываем выбор категории
    categories = get_available_categories()
    
    kb = InlineKeyboardBuilder()
    for cat_name, cat_code in list(categories.items())[:6]:
        kb.button(text=f"{cat_code} - {cat_name.replace('_', ' ').title()}", 
                 callback_data=f"eq_cat_{cat_name}")
    kb.adjust(2)
    
    text = "➕ <b>Создание нового оборудования</b>\n\nВыберите категорию:"
    
    if is_msg:
        await message.answer(text, reply_markup=kb.as_markup())
    else:
        await message.edit_text(text, reply_markup=kb.as_markup())
    
    await state.set_state(EquipmentStates.choosing_category)
    
    if not is_msg:
        await message_or_callback.answer()


@router.callback_query(F.data.startswith("eq_cat_"), StateFilter(EquipmentStates.choosing_category))
async def select_category(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор категории."""
    
    category = callback.data.replace("eq_cat_", "")
    await state.update_data(equipment_category=category)
    
    # Генерируем инвентарный номер
    inv_number = generate_inventory_number(category)
    
    await callback.message.edit_text(
        f"✅ <b>Категория выбрана:</b> {category}\n\n"
        f"<b>Сгенерированный инвентарный номер:</b> <code>{inv_number}</code>\n\n"
        f"Введите <b>модель оборудования</b> (например, 'HP LaunchPad 15'):"
    )
    
    await state.update_data(inv_number=inv_number)
    await state.set_state(EquipmentStates.entering_model)
    await callback.answer()


@router.message(StateFilter(EquipmentStates.entering_model))
async def enter_model(message: types.Message, state: FSMContext):
    """Обрабатывает ввод модели."""
    
    model = message.text.strip()
    await state.update_data(equipment_model=model)
    
    await message.answer(
        f"✅ <b>Модель:</b> {model}\n\n"
        f"Введите <b>серийный номер:</b>"
    )
    
    await state.set_state(EquipmentStates.entering_serial)


@router.message(StateFilter(EquipmentStates.entering_serial))
async def enter_serial(message: types.Message, state: FSMContext):
    """Обрабатывает ввод серийного номера и завершает создание."""
    
    serial = message.text.strip()
    state_data = await state.get_data()
    
    inv_number = state_data['inv_number']
    model = state_data['equipment_model']
    category = state_data['equipment_category']
    
    # Создаём оборудование в БД
    success = await create_equipment(inv_number, model, serial, category)
    
    if success:
        await message.answer(
            f"✅ <b>Оборудование успешно добавлено!</b>\n\n"
            f"<b>Инвентарный номер:</b> <code>{inv_number}</code>\n"
            f"<b>Модель:</b> {model}\n"
            f"<b>Серийный номер:</b> {serial}\n"
            f"<b>Категория:</b> {category}"
        )
        logger.info(f"Admin {message.from_user.id} добавил оборудование {inv_number}")
    else:
        await message.answer("❌ <b>Ошибка при добавлении оборудования.</b>")
    
    await state.clear()


# =================================================================
# 3. ПРОСМОТР СПИСКА ОБОРУДОВАНИЯ
# =================================================================

@router.message(Command("eq_list"))
@router.callback_query(F.data == "eq_list_btn")
async def cmd_list_equipment(message_or_callback, state: FSMContext):
    """Показывает список оборудования с фильтрацией."""
    
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
    
    # Получаем всё оборудование
    equipment = await get_all_equipment()
    
    if not equipment:
        text = "📭 <b>В системе нет оборудования.</b>"
    else:
        text = f"📋 <b>Список оборудования</b> (всего: {len(equipment)})\n\n"
        
        for idx, item in enumerate(equipment[:15], 1):
            status_emoji = "✅" if item['status'] == 'available' else "👤"
            user_info = f" → {item['user_name']}" if item['user_name'] else ""
            
            text += (
                f"{idx}. <code>{item['inv_number']}</code>\n"
                f"   {item['model']} | {item['serial']}\n"
                f"   {status_emoji} {item['status']}{user_info}\n\n"
            )
        
        if len(equipment) > 15:
            text += f"... и ещё {len(equipment) - 15}"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Фильтровать", callback_data="eq_filter")
    kb.button(text="➕ Добавить", callback_data="eq_create_btn")
    kb.adjust(2)
    kb.button(text="« Назад", callback_data="eq_back")
    
    if is_msg:
        await message.answer(text, reply_markup=kb.as_markup())
    else:
        await message.edit_text(text, reply_markup=kb.as_markup())
    
    if not is_msg:
        await message_or_callback.answer()


# =================================================================
# 4. НАЗНАЧЕНИЕ ОБОРУДОВАНИЯ ПОЛЬЗОВАТЕЛЮ
# =================================================================

@router.message(Command("eq_assign"))
@router.callback_query(F.data == "eq_assign_btn")
async def cmd_assign_equipment(message_or_callback, state: FSMContext):
    """Начинает процесс назначения оборудования."""
    
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
        "👤 <b>Назначение оборудования пользователю</b>\n\n"
        "Введите <b>инвентарный номер оборудования</b> (например, LT-2025-0001):"
    )
    
    if is_msg:
        await message.answer(text)
    else:
        await message.edit_text(text)
    
    await state.set_state(EquipmentStates.assigning_user)
    
    if not is_msg:
        await message_or_callback.answer()


@router.message(StateFilter(EquipmentStates.assigning_user))
async def input_equipment_inv_number(message: types.Message, state: FSMContext):
    """Получает инвентарный номер оборудования."""
    
    inv_number = message.text.strip().upper()
    
    # Проверяем наличие оборудования
    equipment = await get_equipment(inv_number=inv_number)
    
    if not equipment:
        await message.answer(f"❌ <b>Оборудование {inv_number} не найдено.</b>")
        return
    
    await state.update_data(selected_equipment_id=equipment['id'], selected_inv_number=inv_number)
    
    await message.answer(
        f"✅ <b>Оборудование найдено:</b>\n\n"
        f"<code>{equipment['inv_number']}</code>\n"
        f"{equipment['model']}\n\n"
        f"Теперь введите <b>Telegram ID пользователя</b> для назначения:"
    )


@router.message(StateFilter(EquipmentStates.assigning_user))
async def input_user_id_for_assignment(message: types.Message, state: FSMContext):
    """Получает ID пользователя для назначения оборудования."""
    
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный числовой ID пользователя.")
        return
    
    state_data = await state.get_data()
    equipment_id = state_data['selected_equipment_id']
    inv_number = state_data['selected_inv_number']
    
    # Проверяем что пользователь существует
    role = await get_user_role(user_id)
    if not role:
        await message.answer(f"❌ <b>Пользователь с ID {user_id} не авторизован в боте.</b>")
        return
    
    # Назначаем оборудование
    success = await assign_equipment_to_user(equipment_id, user_id, message.from_user.id)
    
    if success:
        await message.answer(
            f"✅ <b>Оборудование успешно назначено!</b>\n\n"
            f"<code>{inv_number}</code> → Пользователю {user_id}"
        )
        logger.info(f"Admin {message.from_user.id} назначил оборудование {inv_number} пользователю {user_id}")
    else:
        await message.answer("❌ <b>Ошибка при назначении оборудования.</b>")
    
    await state.clear()


# =================================================================
# 5. ПРОСМОТР ОБОРУДОВАНИЯ ПОЛЬЗОВАТЕЛЯ
# =================================================================

@router.message(F.text == "💻 Мое оборудование")
async def show_user_equipment(message: types.Message):
    """Показывает оборудование текущего пользователя."""
    
    user_id = message.from_user.id
    equipment_list = await get_user_equipment(user_id)
    
    if not equipment_list:
        await message.answer(
            "📭 <b>Вам не назначено оборудование.</b>\n\n"
            "Обратитесь к администратору для получения оборудования."
        )
        return
    
    text = f"💻 <b>Ваше оборудование</b> (всего: {len(equipment_list)})\n\n"
    
    for idx, item in enumerate(equipment_list, 1):
        text += (
            f"{idx}. <code>{item['inv_number']}</code>\n"
            f"   <b>Модель:</b> {item['model']}\n"
            f"   <b>Категория:</b> {item['category']}\n"
            f"   <b>Серийный номер:</b> {item['serial']}\n"
            f"   <b>Назначено:</b> {item['assigned_at']}\n\n"
        )
    
    await message.answer(text)


# =================================================================
# 6. УДАЛЕНИЕ ОБОРУДОВАНИЯ (АДМИН)
# =================================================================

@router.message(Command("eq_delete"))
async def cmd_delete_equipment(message: types.Message, state: FSMContext):
    """Удаляет оборудование из системы."""
    
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Доступ запрещен.")
        return
    
    await message.answer("🗑️ <b>Удаление оборудования</b>\n\nВведите инвентарный номер для удаления:")
    await state.set_state(EquipmentStates.managing_equipment)


@router.message(StateFilter(EquipmentStates.managing_equipment))
async def confirm_delete_equipment(message: types.Message, state: FSMContext):
    """Подтверждает удаление оборудования."""
    
    inv_number = message.text.strip().upper()
    
    # Получаем оборудование
    equipment = await get_equipment(inv_number=inv_number)
    
    if not equipment:
        await message.answer(f"❌ <b>Оборудование {inv_number} не найдено.</b>")
        await state.clear()
        return
    
    # Просим подтверждение
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Удалить", callback_data=f"eq_delete_confirm_{equipment['id']}")
    kb.button(text="❌ Отмена", callback_data="eq_delete_cancel")
    
    await message.answer(
        f"⚠️ <b>Вы действительно хотите удалить это оборудование?</b>\n\n"
        f"<code>{equipment['inv_number']}</code>\n"
        f"{equipment['model']}\n\n"
        f"Это действие необратимо!",
        reply_markup=kb.as_markup()
    )
    
    await state.clear()


@router.callback_query(F.data.startswith("eq_delete_confirm_"))
async def perform_delete(callback: types.CallbackQuery):
    """Выполняет удаление оборудования."""
    
    equipment_id = int(callback.data.replace("eq_delete_confirm_", ""))
    
    success = await delete_equipment(equipment_id)
    
    if success:
        await callback.message.edit_text("✅ <b>Оборудование удалено.</b>")
        logger.info(f"Admin {callback.from_user.id} удалил оборудование {equipment_id}")
    else:
        await callback.message.edit_text("❌ <b>Ошибка при удалении оборудования.</b>")
    
    await callback.answer()


@router.callback_query(F.data == "eq_delete_cancel")
async def cancel_delete(callback: types.CallbackQuery):
    """Отменяет удаление оборудования."""
    
    await callback.message.edit_text("❌ <b>Удаление отменено.</b>")
    await callback.answer()


# =================================================================
# 7. ВСПОМОГАТЕЛЬНЫЕ КНОПКИ
# =================================================================

@router.callback_query(F.data == "eq_back")
async def go_back_to_main(callback: types.CallbackQuery):
    """Возвращает на главное меню оборудования."""
    await callback.message.delete()
    await callback.answer()
