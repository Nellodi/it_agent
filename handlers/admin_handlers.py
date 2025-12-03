from aiogram import Router, F
from aiogram.types import Message
from config import ADMIN_IDS, EXCEL_FILE
from database import db
from utils.excel_parser import load_users_from_excel, get_all_departments, get_users_by_department
from utils.helpers import get_status_emoji

router = Router()

def check_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id in ADMIN_IDS

@router.message(F.text == "👤 Профиль")
async def admin_profile(message: Message):
    """Профиль админа"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
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
    
    profile_text = (
        f"👑 <b>Профиль администратора</b>\n\n"
        f"📋 <b>Основная информация:</b>\n"
        f"• ФИО: <b>{user['full_name']}</b>\n"
        f"• Логин: <code>{user['login']}</code>\n"
        f"• Отдел: {user['department']}\n"
        f"• Должность: <b>{user['position']}</b>\n"
        f"• Роль: <b>Администратор</b>\n"
    )
    
    if excel_user:
        if excel_user.get('hired_date'):
            profile_text += f"• Дата найма: {excel_user['hired_date']}\n"
        if excel_user.get('city'):
            profile_text += f"• Город: {excel_user['city']}\n"
        if excel_user.get('shift'):
            profile_text += f"• Смена: {excel_user['shift']}\n"
    
    profile_text += (
        f"\n⚡️ <b>Права доступа:</b>\n"
        f"• Управление пользователями\n"
        f"• Просмотр всех заявок\n"
        f"• Доступ к аналитике\n"
        f"• Настройка системы"
    )
    
    await message.answer(profile_text, parse_mode="HTML")

@router.message(F.text == "👥 Сотрудники")
async def show_all_users(message: Message):
    """Показать всех сотрудников"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    users = load_users_from_excel(EXCEL_FILE)
    
    if not users:
        await message.answer("📭 Нет данных о сотрудниках.")
        return
    
    # Сортируем по отделу и имени
    users.sort(key=lambda x: (x['department'], x['full_name']))
    
    # Сначала показываем отделы
    departments = get_all_departments(users)
    
    response = "👥 <b>Список сотрудников по отделам:</b>\n\n"
    
    for dept in departments:
        dept_users = get_users_by_department(dept, users)
        active_users = [u for u in dept_users if u.get('status', '').lower() == 'active']
        
        if active_users:
            response += f"🏢 <b>{dept}</b> ({len(active_users)} чел.):\n"
            for user in active_users[:10]:  # Показываем первые 10 в каждом отделе
                role_emoji = "👑" if user['role'] == 'admin' else "👤"
                response += f"{role_emoji} {user['full_name']} - {user['position']}\n"
            response += "\n"
    
    if len(response) > 4000:  # Telegram лимит
        response = response[:4000] + "\n\n... и другие сотрудники"
    
    await message.answer(response, parse_mode="HTML")

@router.message(F.text == "📊 Аналитика")
async def show_analytics(message: Message):
    """Показать аналитику по сотрудникам"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    users = load_users_from_excel(EXCEL_FILE)
    
    if not users:
        await message.answer("📊 Нет данных для анализа.")
        return
    
    # Статистика по статусам
    status_stats = {}
    for user in users:
        status = user.get('status', 'unknown').lower()
        status_stats[status] = status_stats.get(status, 0) + 1
    
    # Статистика по отделам
    dept_stats = {}
    for user in users:
        dept = user['department']
        if user.get('status', '').lower() == 'active':
            dept_stats[dept] = dept_stats.get(dept, 0) + 1
    
    # Статистика по ролям
    role_stats = {'admin': 0, 'user': 0}
    for user in users:
        if user.get('status', '').lower() == 'active':
            role_stats[user['role']] = role_stats.get(user['role'], 0) + 1
    
    total_active = sum(1 for u in users if u.get('status', '').lower() == 'active')
    
    analytics_text = (
        f"📊 <b>Аналитика сотрудников</b>\n\n"
        f"👥 <b>Общая статистика:</b>\n"
        f"• Всего в базе: {len(users)} чел.\n"
        f"• Активных: {total_active} чел.\n"
        f"• Неактивных: {len(users) - total_active} чел.\n\n"
        
        f"🏢 <b>По отделам (активные):</b>\n"
    )
    
    # Топ отделов по количеству сотрудников
    sorted_depts = sorted(dept_stats.items(), key=lambda x: x[1], reverse=True)
    for dept, count in sorted_depts[:10]:
        percentage = count / total_active * 100 if total_active > 0 else 0
        analytics_text += f"• {dept}: {count} чел. ({percentage:.1f}%)\n"
    
    analytics_text += (
        f"\n👑 <b>Распределение ролей:</b>\n"
        f"• Администраторы: {role_stats['admin']} чел.\n"
        f"• Пользователи: {role_stats['user']} чел.\n\n"
        
        f"📅 <b>Статусы сотрудников:</b>\n"
    )
    
    for status, count in status_stats.items():
        analytics_text += f"• {status}: {count} чел.\n"
    
    await message.answer(analytics_text, parse_mode="HTML")

# Добавляем новую функцию для детального просмотра сотрудника
@router.message(F.text == "📋 Все заявки")
async def show_all_tickets(message: Message):
    """Показать все заявки системы"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа!")
        return
    
    # Используем существующую функцию из user_handlers
    from handlers.user_handlers import show_my_tickets
    await show_my_tickets(message)