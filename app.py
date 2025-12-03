# Файл: it_ecosystem_bot/app.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties 
from dotenv import load_dotenv

# ИМПОРТЫ ИСПРАВЛЕНЫ
from config import load_config
from database import init_db
from handlers import (
    auth, start, profile, tickets, admin, admin_tickets, equipment, workplaces
)

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
# -----------------------------

async def main():
    # 1. Загрузка переменных окружения
    load_dotenv()
    config = load_config()

    if not config.tg_bot.token:
        logger.critical("Бот не может быть запущен: BOT_TOKEN не найден в .env.")
        return

    # 2. Инициализация базы данных
    try:
        await init_db() 
        logger.info("DB: База данных успешно инициализирована.")
    except Exception as e:
        logger.critical(f"DB: Ошибка инициализации БД: {e}")
        return

    # 3. Инициализация Бота и Диспетчера
    default_properties = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(token=config.tg_bot.token, default=default_properties)
    
    dp = Dispatcher()
    
    # 4. Регистрация обработчиков
    # Роутеры должны быть зарегистрированы в порядке приоритета
    dp.include_router(start.router)
    dp.include_router(auth.router)
    dp.include_router(profile.router)
    dp.include_router(tickets.router)
    dp.include_router(admin.router)
    dp.include_router(admin_tickets.router)
    dp.include_router(equipment.router)
    dp.include_router(workplaces.router)
    
    # 5. Запуск бота
    logger.info("IT-Экосистема Бот запущен и готов к работе.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.critical(f"Критическая ошибка при работе бота: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную (KeyboardInterrupt).")