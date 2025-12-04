# Файл: it_ecosystem_bot/handlers/tickets.py
import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import save_new_ticket, get_admin_telegram_ids, close_ticket_for_rating, finalize_ticket_rating, \
    get_admin_info, get_user_tickets, get_user_role, get_full_user_profile, update_admin_rating

# !!! ИМПОРТ ИСПРАВЛЕН: Добавлен get_admin_ticket_actions
from keyboards.common import get_rating_keyboard, get_admin_ticket_actions

logger = logging.getLogger(__name__)
router = Router()


class TicketStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_category = State()
    waiting_for_priority = State()


TICKET_CATEGORIES = ["ПО", "Оборудование", "Сеть", "Принтер", "Другое"]
TICKET_PRIORITIES = ["Высокий", "Средний", "Низкий"]


# =================================================================
# 1. СОЗДАНИЕ ЗАЯВКИ (USER)
# =================================================================

@router.message(F.text == "🆘 Создать заявку")
async def cmd_create_ticket(message: types.Message, state: FSMContext):
    user_role = await get_user_role(message.from_user.id)
    if not user_role:
        await message.answer("⚠️ Вы не авторизованы. Начните с команды /start или /login.")
        return

    await message.answer("📝 <b>Новая заявка</b>\nВведите краткое <b>название/тему</b> проблемы:")
    await state.set_state(TicketStates.waiting_for_title)


@router.message(TicketStates.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("✏️ Введите подробное <b>описание</b> проблемы:")
    await state.set_state(TicketStates.waiting_for_description)


@router.message(TicketStates.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())

    keyboard = [[types.InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")] for cat in TICKET_CATEGORIES]
    await message.answer("🗂️ Выберите <b>категорию</b> заявки:",
                         reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.set_state(TicketStates.waiting_for_category)


@router.callback_query(TicketStates.waiting_for_category, F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split('_')[1]
    await state.update_data(category=category)
    await callback.message.edit_text(f"🗂️ Категория: <b>{category}</b> выбрана.")

    keyboard = [[types.InlineKeyboardButton(text=prio, callback_data=f"prio_{prio}")] for prio in TICKET_PRIORITIES]
    await callback.message.answer("🔥 Выберите <b>приоритет</b> заявки:",
                                  reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.set_state(TicketStates.waiting_for_priority)
    await callback.answer()


@router.callback_query(TicketStates.waiting_for_priority, F.data.startswith("prio_"))
async def finalize_ticket_creation(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    priority = callback.data.split('_')[1]
    await state.update_data(priority=priority)

    # 7. Заявка сохраняется в БД
    state_data = await state.get_data()
    user_id = callback.from_user.id

    # Получаем имя из парсера
    user_profile = await get_full_user_profile(user_id)
    user_full_name = user_profile['full_name'] if user_profile else "Неизвестный пользователь"

    try:
        ticket_id, ticket_number = await save_new_ticket(user_id, state_data)
    except Exception as e:
        logger.error(f"Ошибка сохранения заявки: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при сохранении заявки. Попробуйте снова.")
        await state.clear()
        return

    # 8. Отправляются уведомления админам
    admin_ids = await get_admin_telegram_ids()

    notification_text = (
        f"🚨 <b>НОВАЯ ЗАЯВКА</b>\n"
        f"<b>Номер:</b> {ticket_number} (ID: <code>{ticket_id}</code>)\n"
        f"<b>Тема:</b> {state_data['title']}\n"
        f"<b>Категория:</b> {state_data['category']}\n"
        f"<b>Приоритет:</b> {priority}\n"
        f"<b>От пользователя:</b> {user_full_name}"  # Имя из БД
    )

    for admin_id in admin_ids:
        try:
            # !!! КРИТИЧЕСКИЙ ВЫЗОВ: Добавляем кнопку закрытия
            await bot.send_message(
                chat_id=admin_id,
                text=notification_text,
                reply_markup=get_admin_ticket_actions(ticket_id)
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

    await callback.message.edit_text(
        f"✅ Заявка <b>{ticket_number}</b> успешно создана. \nОжидайте ответа Системного Администратора. \nПриоритет: <b>{priority}</b>"
    )
    await state.clear()
    await callback.answer()


# =================================================================
# 2. ПРОСМОТР ЗАЯВОК (USER)
# =================================================================

@router.message(F.text == "📋 Мои заявки")
async def show_my_tickets(message: types.Message):
    """Отображает список заявок пользователя."""
    tickets = await get_user_tickets(message.from_user.id)

    if not tickets:
        await message.answer("У вас пока нет созданных заявок. Нажмите '🆘 Создать заявку' для создания.")
        return

    response = "📋 <b>Ваши Заявки</b>:\n\n"

    for t in tickets:
        status_emoji = {"open": "🔴", "await_rating": "🟠", "closed": "🟢"}.get(t['status'], "⚪")
        response += (
            f"{status_emoji} <b>{t['number']}</b> (ID: <code>{t['id']}</code>): {t['title']} "
            f"(Статус: <b>{t['status'].upper()}</b>)\n"
            f"Создана: {t['created_at']}\n"  # Используем created_at, так как это ключ в dict
        )

    await message.answer(response)


# =================================================================
# 3. ЛОГИКА ЗАКРЫТИЯ ПО КНОПКЕ (ADMIN)
# =================================================================

@router.callback_query(F.data.startswith("admin_close_"))
async def handle_admin_close_button(callback: types.CallbackQuery, bot: Bot):
    """Обрабатывает нажатие кнопки 'Закрыть заявку'."""
    user_role = await get_user_role(callback.from_user.id)
    if user_role != 'admin':
        await callback.answer("🚫 У вас нет прав администратора.")
        return

    try:
        # Извлекаем ID заявки из callback_data: admin_close_123
        ticket_id = int(callback.data.split('_')[-1])
    except ValueError:
        await callback.answer("❌ Неверный формат ID заявки.")
        return

    admin_id = callback.from_user.id

    # Обновляем статус заявки и получаем user_id создателя
    creator_id = await close_ticket_for_rating(ticket_id, admin_id)

    if creator_id is None:
        await callback.message.edit_text(f"❌ Заявка ID <code>{ticket_id}</code> не найдена или уже закрыта.",
                                         reply_markup=None)
        await callback.answer()
        return

    # Изменяем сообщение для админа, чтобы убрать кнопку и показать статус
    await callback.message.edit_text(f"✅ Вы перевели заявку ID <code>{ticket_id}</code> в статус 'Ожидает оценки'.",
                                     reply_markup=None)

    # Отправляем запрос на оценку пользователю
    try:
        await bot.send_message(
            chat_id=creator_id,
            text="⭐ <b>ОЦЕНИТЕ РАБОТУ АДМИНИСТРАТОРА</b>\n\n"
                 "Ваша заявка решена! Пожалуйста, оцените работу Системного Администратора по шкале от 1 до 5 звезд.",
            reply_markup=get_rating_keyboard(ticket_id)
        )
        logger.info(f"Админ {admin_id} запросил оценку для заявки {ticket_id} у пользователя {creator_id}.")
    except Exception as e:
        logger.error(f"Не удалось отправить запрос на оценку пользователю {creator_id}: {e}")

    await callback.answer("Заявка закрыта, ожидаем оценку пользователя.")


# =================================================================
# 4. ОБРАБОТКА ОЦЕНКИ
# =================================================================

@router.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: types.CallbackQuery, bot: Bot):
    """Обработка нажатия на инлайн-кнопку оценки."""

    parts = callback.data.split('_')
    ticket_id = int(parts[1])
    rating = int(parts[2])

    result = await finalize_ticket_rating(ticket_id, rating)

    if result:
        # !!! КРИТИЧЕСКИЙ ВЫЗОВ: Обновление рейтинга
        await update_admin_rating(result['admin_id'], result['rating'])

        admin_info = await get_admin_info(result['admin_id'])

        await callback.message.edit_text(
            f"🌟 Спасибо за вашу оценку в <b>{rating} звезд</b>! Заявка {result['ticket_number']} закрыта."
        )

        if admin_info:
            admin_msg = (
                f"🎉 <b>ПОЛУЧЕНА ОЦЕНКА!</b>\n\n"
                f"Заявка {result['ticket_number']} была оценена пользователем на <b>{rating} звезд</b>.\n"
                f"Ваш средний рейтинг теперь: <b>{admin_info['avg_rating']}/5.0 ⭐️</b>"
            )
            try:
                await bot.send_message(result['admin_id'], admin_msg)
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {result['admin_id']} о рейтинге: {e}")

    else:
        await callback.message.edit_text("❌ Ошибка: Не удалось обработать оценку. Возможно, заявка уже закрыта.")

    await callback.answer()


# =================================================================
# 5. УСТАРЕВШАЯ КОМАНДА (Удалена, но оставлена заглушка)
# =================================================================

@router.message(Command("close_ticket"))
async def cmd_close_ticket_deprecated(message: types.Message):
    await message.answer("Эта команда заменена кнопкой '✅ Закрыть заявку' в уведомлении о новой заявке.")