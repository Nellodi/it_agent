# -*- coding: utf-8 -*-
# Файл: it_ecosystem_bot/handlers/faq.py
import logging
import asyncio
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from database import get_user_role, save_faq_material, get_all_users_for_mailing, get_all_faq_materials
from keyboards.common import main_menu_keyboard, get_faq_initial_keyboard, get_faq_guides_list_keyboard

logger = logging.getLogger(__name__)
router = Router()


class FAQStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_file = State()


# --- АСИНХРОННАЯ ФУНКЦИЯ РАССЫЛКИ ---
async def send_faq_mailing(bot: Bot, faq_data: dict):
    """Отправляет уведомление о новом FAQ всем пользователям."""

    user_ids = await get_all_users_for_mailing()
    logger.info(f"FAQ: Найдено {len(user_ids)} пользователей для рассылки. Пробуем отправить...")

    title = faq_data['title']
    description = faq_data['description']
    file_id = faq_data.get('file_id')
    file_type = faq_data.get('file_type')

    caption_text = (
        f"📣 <b>[ВАЖНО] Новый гайд/FAQ:</b>\n\n"
        f"<b>Тема:</b> {title}\n"
        f"<b>Описание:</b> {description}\n\n"
        f"<i>Подробности в разделе '❓ FAQ'.</i>"
    )

    success_count = 0

    for user_id in user_ids:
        try:
            if file_id:
                if 'photo' in file_type:
                    await bot.send_photo(user_id, photo=file_id, caption=caption_text)
                elif 'video' in file_type:
                    await bot.send_video(user_id, video=file_id, caption=caption_text)
                elif 'document' in file_type or 'pdf' in file_type or 'word' in file_type:
                    await bot.send_document(user_id, document=file_id, caption=caption_text)
                else:
                    await bot.send_message(user_id, caption_text)
            else:
                await bot.send_message(user_id, caption_text)

            success_count += 1

        except Exception as e:
            logger.error(
                f"FAQ: Не удалось отправить рассылку пользователю {user_id}. Вероятно, заблокировал бота. Ошибка: {e}")
            pass

    logger.info(
        f"FAQ: Уведомление о гайде '{title}' успешно отправлено {success_count} пользователям из {len(user_ids)}.")


# =================================================================
# 1. ПОКАЗ FAQ (для всех пользователей)
# =================================================================

@router.message(F.text == "❓ FAQ")
async def cmd_show_faq(message: types.Message):
    """Показывает список FAQ и кнопку 'Гайды'."""

    text = (
        "📚 <b>Часто задаваемые вопросы (FAQ)</b>\n\n"
        "• <b>Как запросить новое ПО?</b>\n   Создайте заявку, выбрав категорию 'ПО'.\n\n"
        "• <b>Почему не работает принтер?</b>\n   Проверьте кабель питания и статус в системе.\n\n"
    )

    await message.answer(text, reply_markup=get_faq_initial_keyboard())


@router.callback_query(F.data == "faq_back_to_main")
async def cmd_faq_back_to_main(callback: types.CallbackQuery):
    """Возврат в основное меню FAQ."""

    await callback.answer()  # Отвечаем сразу

    text = (
        "📚 <b>Часто задаваемые вопросы (FAQ)</b>\n\n"
        "• <b>Как запросить новое ПО?</b>\n   Создайте заявку, выбрав категорию 'ПО'.\n\n"
        "• <b>Почему не работает принтер?</b>\n   Проверьте кабель питания и статус в системе.\n\n"
    )

    await callback.message.edit_text(text, reply_markup=get_faq_initial_keyboard())


@router.callback_query(F.data == "faq_show_guides")
async def cmd_show_guides_list(callback: types.CallbackQuery):
    """Показывает список всех сохраненных гайдов."""

    await callback.answer()  # Отвечаем сразу

    guides = await get_all_faq_materials()

    if not guides:
        await callback.message.edit_text("📖 <b>Гайды</b>\n\n❌ Гайды еще не добавлены.",
                                         reply_markup=get_faq_initial_keyboard())
        return

    await callback.message.edit_text(
        "📖 <b>Список Гайдов</b>\n\nВыберите нужный материал:",
        reply_markup=get_faq_guides_list_keyboard(guides)
    )


@router.callback_query(F.data.startswith("guide_show_"))
async def cmd_show_single_guide(callback: types.CallbackQuery, bot: Bot):
    """Показывает подробный контент одного гайда."""

    await callback.answer()  # Отвечаем сразу

    try:
        faq_id = int(callback.data.replace("guide_show_", ""))
    except ValueError:
        await callback.message.edit_text("❌ Ошибка ID гайда.")
        return

    guides = await get_all_faq_materials()
    guide = next((g for g in guides if g['id'] == faq_id), None)

    if not guide:
        await callback.message.edit_text("❌ Гайд не найден.", reply_markup=get_faq_initial_keyboard())
        return

    # --- Формирование текста ---
    text = (
        f"📖 <b>Гайд: {guide['title']}</b>\n\n"
        f"<b>Описание:</b>\n{guide['description']}\n\n"
    )

    # Кнопка для возврата к списку гайдов
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="« Назад к списку гайдов", callback_data="faq_show_guides")]
    ])

    # --- Отправка текста и файла ---
    if guide['file_id']:
        text += "📎 <b>Вложение:</b> См. ниже"

        # Редактируем сообщение для отображения текста
        await callback.message.edit_text(text, reply_markup=kb)

        file_id = guide['file_id']
        file_type = guide['file_type']

        try:
            # Отправляем прикрепленный файл отдельным сообщением
            if 'photo' in file_type:
                await bot.send_photo(callback.from_user.id, photo=file_id, caption="Вложение к гайду")
            elif 'video' in file_type:
                await bot.send_video(callback.from_user.id, video=file_id, caption="Вложение к гайду")
            elif 'document' in file_type or 'pdf' in file_type or 'word' in file_type:
                await bot.send_document(callback.from_user.id, document=file_id, caption="Вложение к гайду")
            else:
                await bot.send_message(callback.from_user.id, "❌ Неизвестный тип вложения.")
        except Exception as e:
            logger.error(f"FAQ: Не удалось отправить вложение гайда {faq_id} пользователю {callback.from_user.id}: {e}")
            await bot.send_message(callback.from_user.id, "❌ Не удалось отобразить прикрепленный файл.")

    else:
        text += "📎 <b>Вложение:</b> Отсутствует"
        await callback.message.edit_text(text, reply_markup=kb)


# =================================================================
# 2. УПРАВЛЕНИЕ FAQ (ADMIN FSM) - Логика финализации
# =================================================================

@router.callback_query(F.data == "faq_add")
async def cmd_admin_faq_add(callback: types.CallbackQuery, state: FSMContext):
    """Начало процесса добавления материала."""

    await callback.answer()  # !!! КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Отвечаем сразу !!!

    user_role = await get_user_role(callback.from_user.id)
    if user_role != 'admin':
        await callback.message.answer("🚫 Доступ запрещен.")
        return

    await callback.message.edit_text("➕ <b>Добавление FAQ</b>\n\nВведите <b>Название</b> гайда/статьи:")
    await state.set_state(FAQStates.waiting_for_title)


@router.message(FAQStates.waiting_for_title)
async def process_faq_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("📝 Введите краткое <b>Описание</b> (ответ, текст гайда):")
    await state.set_state(FAQStates.waiting_for_description)


@router.message(FAQStates.waiting_for_description)
async def process_faq_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer(
        "📎 Теперь, пожалуйста, прикрепите <b>файл</b> (фото, видео, PDF, Word, HEIC) или отправьте <code>/skip</code>, чтобы пропустить этот шаг."
    )
    await state.set_state(FAQStates.waiting_for_file)


@router.message(FAQStates.waiting_for_file, Command("skip"))
async def process_faq_file_skip(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка пропуска прикрепления файла и финализация."""

    data = await state.get_data()

    # 1. Сохранение материала в БД (файл: None)
    faq_record = await save_faq_material(data['title'], data['description'], file_info=None)

    # 2. Отправка рассылки
    if faq_record:
        asyncio.create_task(send_faq_mailing(bot, faq_record))

    await message.answer(
        f"✅ <b>FAQ '{data['title']}' успешно сохранен и разослан!</b> (Без вложения).",
        reply_markup=main_menu_keyboard('admin')
    )
    await state.clear()


@router.message(FAQStates.waiting_for_file, F.photo | F.video | F.document)
async def process_faq_file(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка прикрепления файла (фото, видео, документ) и финализация."""

    file_info = {}
    if message.photo:
        file_info['id'] = message.photo[-1].file_id
        file_info['type'] = 'photo'
    elif message.video:
        file_info['id'] = message.video.file_id
        file_info['type'] = 'video'
    elif message.document:
        file_info['id'] = message.document.file_id
        file_info['type'] = 'document'
    else:
        await message.answer("❌ Неподдерживаемый формат файла. Пожалуйста, прикрепите фото, видео или документ.")
        return

    data = await state.get_data()

    # 1. Сохранение материала в БД (с файлом)
    faq_record = await save_faq_material(data['title'], data['description'], file_info)

    # 2. Отправка рассылки
    if faq_record:
        asyncio.create_task(send_faq_mailing(bot, faq_record))

    await message.answer(
        f"✅ <b>FAQ '{data['title']}' успешно сохранен и разослан!</b>\n"
        f"Тип вложения: {file_info['type']}",
        reply_markup=main_menu_keyboard('admin')
    )
    await state.clear()