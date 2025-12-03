from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database import db
from keyboards.main_menu import get_ticket_categories_keyboard, get_ticket_priority_keyboard
from keyboards.auth_kb import get_cancel_keyboard
from states import TicketStates
from utils.helpers import generate_ticket_number

router = Router()

@router.message(F.text == "🆘 Создать заявку")
async def start_create_ticket(message: Message, state: FSMContext):
    """Начало создания заявки"""
    user = db.get_authorized_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы не авторизованы!")
        return
    
    await state.set_state(TicketStates.waiting_for_title)
    await message.answer(
        "🆘 <b>Создание новой заявки</b>\n\n"
        "Введите краткое описание проблемы:\n"
        "<i>Пример: Не работает принтер в кабинете 301-А</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@router.message(TicketStates.waiting_for_title)
async def process_ticket_title(message: Message, state: FSMContext):
    """Обработка названия заявки"""
    if len(message.text) < 5:
        await message.answer(
            "❌ Описание слишком короткое. Введите подробнее:",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    await state.update_data(title=message.text)
    await state.set_state(TicketStates.waiting_for_description)
    await message.answer(
        "📝 Теперь опишите проблему подробнее:\n"
        "<i>Пример: Принтер HP LaserJet не печатает, выдает ошибку 'Paper jam'</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@router.message(TicketStates.waiting_for_description)
async def process_ticket_description(message: Message, state: FSMContext):
    """Обработка описания заявки"""
    await state.update_data(description=message.text)
    await state.set_state(TicketStates.waiting_for_category)
    await message.answer(
        "🎯 Выберите категорию проблемы:",
        reply_markup=get_ticket_categories_keyboard()
    )

@router.callback_query(F.data.startswith("category_"))
async def process_ticket_category(callback: CallbackQuery, state: FSMContext):
    """Обработка категории заявки"""
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    await state.set_state(TicketStates.waiting_for_priority)
    
    await callback.message.edit_text(
        "⚡️ Выберите приоритет заявки:",
        reply_markup=get_ticket_priority_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("priority_"))
async def process_ticket_priority(callback: CallbackQuery, state: FSMContext):
    """Обработка приоритета и сохранение заявки"""
    priority = callback.data.split("_")[1]
    data = await state.get_data()
    
    user = db.get_authorized_user(callback.from_user.id)
    
    if not user:
        await callback.message.answer("❌ Вы не авторизованы!")
        await state.clear()
        return
    
    # Сохраняем заявку
    ticket_number = db.add_ticket(
        user_id=user['telegram_id'],
        title=data['title'],
        description=data['description'],
        category=data['category']
    )
    
    if ticket_number:
        from utils.helpers import get_status_emoji
        
        success_text = (
            f"✅ <b>Заявка создана успешно!</b>\n\n"
            f"📋 <b>Детали заявки:</b>\n"
            f"• Номер: <code>{ticket_number}</code>\n"
            f"• Тема: {data['title']}\n"
            f"• Категория: {data['category']}\n"
            f"• Приоритет: {priority}\n"
            f"• Статус: {get_status_emoji('open')} Открыта\n\n"
            f"⏱ <b>Ожидаемое время решения:</b>\n"
            f"• Высокий приоритет: 2-4 часа\n"
            f"• Средний приоритет: 1-2 дня\n"
            f"• Низкий приоритет: 3-5 дней\n\n"
            f"📞 Вы будете уведомлены о статусе заявки."
        )
        
        await callback.message.answer(success_text, parse_mode="HTML")
        
        # Отправляем уведомление админам
        from config import ADMIN_IDS
        from aiogram import Bot
        from config import BOT_TOKEN
        
        bot = Bot(token=BOT_TOKEN)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"🆘 Новая заявка #{ticket_number}\n"
                    f"От: {user['full_name']}\n"
                    f"Тема: {data['title']}\n"
                    f"Приоритет: {priority}"
                )
            except:
                pass
        
        await bot.session.close()
    else:
        await callback.message.answer("❌ Ошибка при создании заявки!")
    
    await state.clear()
    await callback.answer()