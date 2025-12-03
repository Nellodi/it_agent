from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database import db
from config import EXCEL_FILE
from utils.excel_parser import load_users_from_excel
from utils.helpers import get_status_emoji, get_department_emoji, format_date
from datetime import datetime

router = Router()

@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message):
    """Показать профиль пользователя"""
    user = db.get_authorized_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы не авторизованы!")
        return
    
    # Загружаем полные данные из Excel
    users_data = load_users_from_excel(EXCEL_FILE)
    excel_user = None
    for u in users_data:
        if u['login'] == user['login']:
            excel_user = u
            break
    
    # Получаем заявки пользователя
    tickets = db.get_user_tickets(user['telegram_id'])
    
    # Формируем профиль
    profile_text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📋 <b>Основная информация:</b>\n"
        f"• ФИО: <b>{user['full_name']}</b>\n"
        f"• Логин: <code>{user['login']}</code>\n"
    )
    
    if excel_user and excel_user.get('nick_name'):
        profile_text += f"• Псевдоним: {excel_user['nick_name']}\n"
    
    profile_text += (
        f"• Отдел: {get_department_emoji(user['department'])} <b>{user['department']}</b>\n"
        f"• Должность: <b>{user['position']}</b>\n"
    )
    
    if excel_user:
        if excel_user.get('status'):
            status_emoji = "🟢" if excel_user['status'].lower() == 'active' else "🔴"
            profile_text += f"• Статус: {status_emoji} <b>{excel_user['status']}</b>\n"
        
        if excel_user.get('hired_date'):
            profile_text += f"• Дата найма: <b>{excel_user['hired_date']}</b>\n"
        
        if excel_user.get('city'):
            profile_text += f"• Город: <b>{excel_user['city']}</b>\n"
        
        if excel_user.get('shift'):
            profile_text += f"• Смена: <b>{excel_user['shift']}</b>\n"
        
        if excel_user.get('email'):
            profile_text += f"• Email: <code>{excel_user['email']}</code>\n"
    
    profile_text += f"• Роль: <b>{'Администратор' if user['role'] == 'admin' else 'Пользователь'}</b>\n\n"
    
    # Статистика заявок
    if tickets:
        total = len(tickets)
        resolved = len([t for t in tickets if t['status'] == 'resolved'])
        open_tickets = len([t for t in tickets if t['status'] == 'open'])
        
        profile_text += (
            f"📊 <b>Статистика заявок:</b>\n"
            f"• Всего заявок: <b>{total}</b>\n"
            f"• 🟢 Решено: <b>{resolved}</b>\n"
            f"• 🔴 Открыто: <b>{open_tickets}</b>\n"
        )
        
        if resolved > 0:
            percentage = (resolved / total) * 100
            profile_text += f"• 📈 Эффективность: <b>{percentage:.1f}%</b>\n"
        
        profile_text += "\n"
    
    # Оборудование (на основе отдела)
    from utils.helpers import generate_inventory_number
    equipment_text = ""
    
    if user['department'].lower() in ['it', 'техподдержка', 'support']:
        equipment_text = (
            f"💻 <b>Закрепленное оборудование:</b>\n"
            f"• 💻 Ноутбук Dell XPS (<code>{generate_inventory_number('NB')}</code>)\n"
            f"• 🖥 Монитор HP 24mh (<code>{generate_inventory_number('MON')}</code>)\n"
            f"• 📱 iPhone 13 (<code>{generate_inventory_number('PH')}</code>)\n"
        )
    elif user['department'].lower() in ['продажи', 'sales', 'маркетинг', 'marketing']:
        equipment_text = (
            f"💻 <b>Закрепленное оборудование:</b>\n"
            f"• 💻 Ноутбук MacBook Pro (<code>{generate_inventory_number('MBP')}</code>)\n"
            f"• 📱 iPhone 14 (<code>{generate_inventory_number('PH')}</code>)\n"
        )
    else:
        equipment_text = (
            f"💻 <b>Закрепленное оборудование:</b>\n"
            f"• 💻 Ноутбук Dell Latitude (<code>{generate_inventory_number('LT')}</code>)\n"
            f"• 🖥 Монитор Dell 24\" (<code>{generate_inventory_number('MON')}</code>)\n"
        )
    
    profile_text += equipment_text + "\n"
    
    # Лицензии ПО (на основе должности)
    if 'менеджер' in user['position'].lower() or 'manager' in user['position'].lower():
        profile_text += (
            f"🛠 <b>Лицензии ПО:</b>\n"
            f"• ✅ Microsoft Office 365\n"
            f"• ✅ CRM система\n"
            f"• ✅ 1С:Предприятие\n"
            f"• ✅ Корпоративный мессенджер\n"
        )
    elif 'разработ' in user['position'].lower() or 'developer' in user['position'].lower():
        profile_text += (
            f"🛠 <b>Лицензии ПО:</b>\n"
            f"• ✅ JetBrains All Products Pack\n"
            f"• ✅ GitHub Copilot\n"
            f"• ✅ Docker Desktop\n"
            f"• ✅ Microsoft Office 365\n"
        )
    else:
        profile_text += (
            f"🛠 <b>Лицензии ПО:</b>\n"
            f"• ✅ Microsoft Office 365\n"
            f"• ✅ Корпоративный антивирус\n"
            f"• ✅ 1С:Зарплата\n"
        )
    
    await message.answer(profile_text, parse_mode="HTML")

# Остальной код оставляем без изменений...