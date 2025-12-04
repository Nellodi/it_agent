# -*- coding: utf-8 -*-
# it_ecosystem_bot/handlers/tickets.py
import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import (
    save_new_ticket,
    get_admin_telegram_ids,
    close_ticket_for_rating,
    finalize_ticket_rating,
    get_admin_info,
    get_user_tickets,
    get_user_role,
    get_full_user_profile,
    update_admin_rating,
    get_available_floors,
    get_workplaces_by_floor,
    add_ticket_attachment,
)
from keyboards.common import (
    get_rating_keyboard,
    get_admin_ticket_actions,
    inline_main_menu,
)

logger = logging.getLogger(__name__)
router = Router()


class TicketStates(StatesGroup):
    waiting_for_floor = State()
    waiting_for_workplace = State()
    waiting_for_category = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_photo = State()
    waiting_for_priority = State()


TICKET_CATEGORIES = ["Офисное ПО", "Железо", "Сеть/Интернет", "Доступы", "Другое"]
TICKET_PRIORITIES = ["низкий", "средний", "высокий"]


# --- Клавиатуры ----------------------------------------------------------------
def floors_keyboard(floors: list[int]) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for f in floors:
        kb.button(text=f"Этаж {f}", callback_data=f"floor_{f}")
    kb.button(text="🚫 Отмена", callback_data="ticket_cancel")
    kb.adjust(2)
    return kb.as_markup()


def workplaces_keyboard(workplaces: list[dict]) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for wp in workplaces:
        text = wp["number"]
        if wp.get("pc_name"):
            text = f"{wp['number']} ({wp['pc_name']})"
        kb.button(text=text, callback_data=f"wp_{wp['number']}")
    kb.button(text="⬅️ К выбору этажа", callback_data="back_to_floor")
    kb.button(text="🚫 Отмена", callback_data="ticket_cancel")
    kb.adjust(2)
    return kb.as_markup()


def category_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in TICKET_CATEGORIES:
        kb.button(text=cat, callback_data=f"cat_{cat}")
    kb.button(text="⬅️ Назад к рабочему месту", callback_data="back_to_workplace")
    kb.button(text="🚫 Отмена", callback_data="ticket_cancel")
    kb.adjust(2)
    return kb.as_markup()


def photo_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📎 Прикрепить фото", callback_data="wait_photo")
    kb.button(text="⏭ Пропустить", callback_data="skip_photo")
    kb.button(text="🚫 Отмена", callback_data="ticket_cancel")
    kb.adjust(1)
    return kb.as_markup()


# --- Старт создания заявки ----------------------------------------------------
async def _start_ticket_flow(message: types.Message, state: FSMContext):
    user_role = await get_user_role(message.from_user.id)
    if not user_role:
        await message.answer("Сначала авторизуйся /start и войди.", reply_markup=None)
        return

    floors = await get_available_floors()
    await state.clear()
    await state.set_state(TicketStates.waiting_for_floor)
    await message.answer(
        "🆕 <b>Новая заявка</b>\n\n1/6: выбери этаж:",
        reply_markup=floors_keyboard(floors),
    )


@router.message(F.text == "🟦 Создать запрос")
@router.message(Command("create_ticket"))
async def cmd_create_ticket(message: types.Message, state: FSMContext):
    await _start_ticket_flow(message, state)


@router.callback_query(F.data == "menu_create_ticket")
async def cb_create_ticket(callback: types.CallbackQuery, state: FSMContext):
    await _start_ticket_flow(callback.message, state)
    await callback.answer()


# --- Выбор этажа --------------------------------------------------------------
@router.callback_query(TicketStates.waiting_for_floor, F.data.startswith("floor_"))
async def select_floor(callback: types.CallbackQuery, state: FSMContext):
    floor = int(callback.data.split("_")[1])
    await state.update_data(floor=floor)

    workplaces = await get_workplaces_by_floor(floor)
    if not workplaces:
        await callback.message.edit_text("Нет рабочих мест на выбранном этаже. Выбери другой этаж.")
        await callback.answer()
        return

    await state.set_state(TicketStates.waiting_for_workplace)
    await callback.message.edit_text(
        f"2/6: выбери рабочее место (этаж {floor}):",
        reply_markup=workplaces_keyboard(workplaces),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_floor")
async def back_to_floor(callback: types.CallbackQuery, state: FSMContext):
    floors = await get_available_floors()
    await state.set_state(TicketStates.waiting_for_floor)
    await callback.message.edit_text("1/6: выбери этаж:", reply_markup=floors_keyboard(floors))
    await callback.answer()


# --- Выбор рабочего места -----------------------------------------------------
@router.callback_query(TicketStates.waiting_for_workplace, F.data.startswith("wp_"))
async def select_workplace(callback: types.CallbackQuery, state: FSMContext):
    workplace_number = callback.data.split("_", 1)[1]
    await state.update_data(workplace=workplace_number)

    await state.set_state(TicketStates.waiting_for_category)
    await callback.message.edit_text(
        f"3/6: выбери категорию проблемы (место {workplace_number}):",
        reply_markup=category_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_workplace")
async def back_to_workplace(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    floor = data.get("floor")
    if not floor:
        await back_to_floor(callback, state)
        return
    workplaces = await get_workplaces_by_floor(floor)
    await state.set_state(TicketStates.waiting_for_workplace)
    await callback.message.edit_text(
        f"2/6: выбери рабочее место (этаж {floor}):",
        reply_markup=workplaces_keyboard(workplaces),
    )
    await callback.answer()


# --- Категория ---------------------------------------------------------------
@router.callback_query(TicketStates.waiting_for_category, F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split("_", 1)[1]
    await state.update_data(category=category)

    await state.set_state(TicketStates.waiting_for_title)
    await callback.message.edit_text(
        f"4/6: категория <b>{category}</b>. Введи краткий заголовок проблемы:",
        reply_markup=None,
    )
    await callback.answer()


@router.message(TicketStates.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(TicketStates.waiting_for_description)
    await message.answer("5/6: опиши проблему подробно:")


@router.message(TicketStates.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(TicketStates.waiting_for_photo)
    await message.answer("6/6: прикрепи фото (необязательно) или пропусти:", reply_markup=photo_keyboard())


@router.callback_query(TicketStates.waiting_for_photo, F.data == "skip_photo")
async def skip_photo(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await state.update_data(photo_id=None)
    await finalize_ticket(callback.message, state, bot)
    await callback.answer()


@router.callback_query(TicketStates.waiting_for_photo, F.data == "wait_photo")
async def prompt_photo(callback: types.CallbackQuery):
    await callback.message.edit_text("Пришли фото одним сообщением или нажми «Отмена».")
    await callback.answer()


@router.message(TicketStates.waiting_for_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext, bot: Bot):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await finalize_ticket(message, state, bot)


# --- Финал создания ----------------------------------------------------------
async def finalize_ticket(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_id = message.from_user.id
    user_profile = await get_full_user_profile(user_id)
    user_full_name = user_profile["full_name"] if user_profile else "Неизвестно"

    data.setdefault("priority", "medium")

    try:
        ticket_id, ticket_number = await save_new_ticket(user_id, data)

        photo_id = data.get("photo_id")
        if photo_id:
            await add_ticket_attachment(ticket_id, photo_id, "photo")
    except Exception as e:
        logger.error(f"Ошибка создания заявки: {e}")
        await message.answer("⚠️ Не удалось создать заявку. Попробуй позже.")
        await state.clear()
        return

    admin_ids = await get_admin_telegram_ids()
    notification_text = (
        f"🆕 <b>Новая заявка</b>\n"
        f"Номер: <b>{ticket_number}</b>\n"
        f"Автор: {user_full_name}\n"
        f"Этаж/место: {data.get('floor')} / {data.get('workplace')}\n"
        f"Категория: {data.get('category')}\n"
        f"Заголовок: {data.get('title')}"
    )

    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=notification_text,
                reply_markup=get_admin_ticket_actions(ticket_id),
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

    await message.answer(
        f"✅ Заявка создана! Номер <b>{ticket_number}</b>.\n"
        f"Этаж: {data.get('floor')}, место: {data.get('workplace')}.",
        reply_markup=inline_main_menu(await get_user_role(user_id) or "user"),
    )
    await state.clear()


# --- Мои заявки --------------------------------------------------------------
@router.message(F.text == "🗂 Мои запросы")
async def show_my_tickets(message: types.Message):
    user = message.from_user.id
    tickets = await get_user_tickets(user)

    if not tickets:
        await message.answer("У тебя пока нет заявок.")
        return

    text = "🗂 <b>Мои заявки</b>\n\n"
    for t in tickets:
        status_emoji = {"open": "🟢", "in_progress": "🟠", "await_rating": "⭐", "closed": "✅"}.get(
            t["status"], "▪️"
        )
        text += f"{status_emoji} {t['number']} — {t['title']} ({t['status']})\n"
    await message.answer(text)


@router.callback_query(F.data == "menu_my_tickets")
async def cb_my_tickets(callback: types.CallbackQuery):
    await show_my_tickets(callback.message)
    await callback.answer()


# --- Закрытие админом и рейтинг ---------------------------------------------
@router.callback_query(F.data.startswith("admin_close_"))
async def handle_admin_close_button(callback: types.CallbackQuery, bot: Bot):
    user_role = await get_user_role(callback.from_user.id)
    if user_role != "admin":
        await callback.answer("Только для админов", show_alert=True)
        return

    ticket_id = int(callback.data.split("_")[-1])
    admin_id = callback.from_user.id
    creator_id = await close_ticket_for_rating(ticket_id, admin_id)

    if creator_id is None:
        await callback.message.edit_text("Не удалось закрыть заявку (возможно уже закрыта).")
        await callback.answer()
        return

    await callback.message.edit_text("Заявка переведена в статус 'ожидает оценку'.")

    try:
        await bot.send_message(
            chat_id=creator_id,
            text="✅ Ваша заявка выполнена. Пожалуйста, оцените работу администратора:",
            reply_markup=get_rating_keyboard(ticket_id),
        )
    except Exception as e:
        logger.error(f"Не удалось отправить запрос рейтинга пользователю {creator_id}: {e}")

    await callback.answer()


@router.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: types.CallbackQuery, bot: Bot):
    _, ticket_id, rating = callback.data.split("_")
    ticket_id = int(ticket_id)
    rating = int(rating)

    result = await finalize_ticket_rating(ticket_id, rating)
    if not result:
        await callback.message.edit_text("Не удалось сохранить оценку.")
        await callback.answer()
        return

    await update_admin_rating(result["admin_id"], result["rating"])
    admin_info = await get_admin_info(result["admin_id"])

    await callback.message.edit_text("Спасибо за оценку! Заявка закрыта.")

    if admin_info:
        try:
            await bot.send_message(
                result["admin_id"],
                f"⭐ Тебе поставили {rating}/5 за заявку {result['ticket_number']}.\n"
                f"Средний рейтинг: {admin_info['avg_rating']}/5.",
            )
        except Exception as e:
            logger.error(f"Не удалось отправить рейтинг админу {result['admin_id']}: {e}")

    await callback.answer()


# --- Отмена / выход из FSM ---------------------------------------------------
@router.callback_query(F.data == "ticket_cancel")
@router.message(Command("cancel"))
async def cancel_ticket(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.clear()
    role = await get_user_role(event.from_user.id)
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text("Создание заявки отменено.", reply_markup=inline_main_menu(role or "user"))
        await event.answer()
    else:
        await event.answer("Создание заявки отменено.", reply_markup=inline_main_menu(role or "user"))

