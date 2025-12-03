# Файл: it_ecosystem_bot/handlers/tickets.py
import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import save_new_ticket, get_admin_telegram_ids, close_ticket_for_rating, finalize_ticket_rating, \
    get_admin_info, get_user_tickets, get_user_role
from keyboards.common import get_rating_keyboard

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

    # !!! КЛЮЧЕВАЯ ДИАГНОСТИКА: Проверяем, почему не найдена роль
    if not user_role:
        logger.warning(
            f"TICKETS: Пользователь {message.from_user.id} не найден в БД при попытке создать заявку. Роль: {user_role}")
        await message.answer("⚠️ Вы не авторизованы. Начните с команды /start или /login.")
        return
    # Если все ОК, продолжаем

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
    try:
        ticket_id, ticket_number = await save_new_ticket(callback.from_user.id, state_data)
    except Exception as e:
        logger.error(f"Ошибка сохранения заявки: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при сохранении заявки. Попробуйте снова.")
        await state.clear()
        return

    # 8. Отправляются уведомления админам
    admin_ids = await get_admin_telegram_ids()

    notification_text = (
        f"🚨 <b>НОВАЯ ЗАЯВКА</b>\n"
        f"<b>Номер:</b> {ticket_number}\n"
        f"<b>Тема:</b> {state_data['title']}\n"
        f"<b>Категория:</b> {state_data['category']}\n"
        f"<b>Приоритет:</b> {priority}\n"
        f"<b>От пользователя:</b> {callback.from_user.full_name}\n\n"
        f"Админ: Для закрытия используйте команду <code>/close_ticket {ticket_id}</code>"
    )

    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=notification_text)
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
            f"{status_emoji} <b>{t['number']}</b>: {t['title']} "
            f"(Статус: <b>{t['status'].upper()}</b>)\n"
            f"Создана: {t['created']}\n"
        )

    await message.answer(response)


# =================================================================
# 3. ЛОГИКА ЗАКРЫТИЯ И ОЦЕНКИ SYSADMIN'А
# =================================================================

@router.message(Command("close_ticket"))
async def cmd_close_ticket(message: types.Message, bot: Bot):
    """Команда админа для закрытия заявки и запроса оценки."""
    user_role = await get_user_role(message.from_user.id)
    if user_role != 'admin':
        await message.answer("🚫 Команда только для администраторов.")
        return

    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer(
            "❌ Используйте формат: <code>/close_ticket [ID заявки]</code> (ID заявки — это ID из БД, который виден в уведомлении).")
        return

    ticket_id = int(parts[1])
    admin_id = message.from_user.id

    creator_id = await close_ticket_for_rating(ticket_id, admin_id)

    if creator_id is None:
        await message.answer(f"❌ Заявка с ID {ticket_id} не найдена или уже закрыта.")
        return

    await message.answer(f"✅ Заявка ID {ticket_id} переведена в статус 'Ожидает оценки'.")

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


@router.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: types.CallbackQuery, bot: Bot):
    """Обработка нажатия на инлайн-кнопку оценки."""

    parts = callback.data.split('_')
    ticket_id = int(parts[1])
    rating = int(parts[2])

    result = await finalize_ticket_rating(ticket_id, rating)

    if result:
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

    @router.callback_query(F.data.startswith("rate_"))
    async def process_rating(callback: types.CallbackQuery, bot: Bot):
        """Обработка нажатия на инлайн-кнопку оценки."""

        parts = callback.data.split('_')
        ticket_id = int(parts[1])
        rating = int(parts[2])

        # 1. Завершаем оценку и получаем данные
        result = await finalize_ticket_rating(ticket_id, rating)

        if result:
            # !!! КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Вызываем асинхронную функцию обновления рейтинга
            await update_admin_rating(result['admin_id'], result['rating'])

            admin_info = await get_admin_info(result['admin_id'])

            # 2. Сообщаем пользователю об успехе
            await callback.message.edit_text(
                f"🌟 Спасибо за вашу оценку в <b>{rating} звезд</b>! Заявка {result['ticket_number']} закрыта."
            )

            # 3. Сообщаем администратору
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