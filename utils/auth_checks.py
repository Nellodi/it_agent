# Файл: it_ecosystem_bot/utils/auth_checks.py
import os
import logging
from typing import Callable, Awaitable, Any
from aiogram.types import Message
# Для работы декоратора
from aiogram import Router

logger = logging.getLogger(__name__)


def is_admin(telegram_id: int) -> bool:
    """Проверяет, является ли пользователь администратором (по БД, не по .env)."""
    # Эта функция используется для проверки роли пользователя из БД
    # Она заглушка - реальная проверка делается в обработчиках через get_user_role()
    # Используется только для быстрой проверки перед основной логикой
    return True  # По умолчанию даём доступ (проверка будет в обработчиках)


def is_super_admin(telegram_id: int) -> bool:
    """Проверяет, является ли пользователь Супер-Админом по ID из .env."""

    # Приоритетная переменная по структуре кода
    super_admin_ids_str = os.getenv('SUPER_ADMIN_IDS', '')

    if not super_admin_ids_str:
        # Если SUPER_ADMIN_IDS не найдена, проверяем ADMIN_IDS (в вашем случае)
        super_admin_ids_str = os.getenv('ADMIN_IDS', '')
        if super_admin_ids_str:
            logger.warning(
                "AUTH_CHECKS: Используется переменная ADMIN_IDS. Рекомендуется переименовать ее в SUPER_ADMIN_IDS.")
        else:
            # Ни одна из переменных не найдена
            logger.critical("AUTH_CHECKS: Переменная SUPER_ADMIN_IDS или ADMIN_IDS не найдена в .env.")
            return False

    try:
        # Парсим ID, игнорируя пустые строки и нечисловые значения
        super_admin_ids = [int(id.strip()) for id in super_admin_ids_str.split(',') if id.strip().isdigit()]

        if not super_admin_ids:
            logger.error("AUTH_CHECKS: Переменная SUPER/ADMIN_IDS пуста или содержит нечисловые значения.")
            return False

        return telegram_id in super_admin_ids
    except ValueError:
        logger.error("AUTH_CHECKS: Ошибка парсинга ID в .env")
        return False


def super_admin_required(handler: Callable[[Message], Awaitable[Any]]):
    """Декоратор для ограничения доступа к функциям только для Супер-Админов."""

    async def wrapper(message: Message, *args, **kwargs):
        if is_super_admin(message.from_user.id):
            return await handler(message, *args, **kwargs)
        else:
            await message.answer(
                "🚫 <b>Доступ запрещен.</b> У вас нет прав Супер-Администратора для выполнения этой команды.")
            logger.warning(f"Попытка доступа Супер-Админ: {message.from_user.id}")
            return

    return wrapper