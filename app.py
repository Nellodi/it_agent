import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from database import init_db, import_users_from_excel
from handlers import auth, start, profile, tickets, admin, admin_tickets, equipment, workplaces, faq

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    load_dotenv()
    config = load_config()

    if not config.tg_bot.token:
        logger.critical("Не найден BOT_TOKEN в .env.")
        return

    try:
        await init_db()
        # Однократно переносим пользователей из Excel в справочник БД, дальше работаем только с SQLite
        await asyncio.to_thread(import_users_from_excel)
        logger.info("DB: успешно инициализирована и миграции применены.")
    except Exception as e:
        logger.critical(f"DB: ошибка инициализации/миграции: {e}")
        return

    scheduler = AsyncIOScheduler()
    scheduler.start()
    logger.info("Scheduler запущен.")

    bot = Bot(
        token=config.tg_bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Handlers
    dp.include_router(start.router)
    dp.include_router(auth.router)
    dp.include_router(profile.router)
    dp.include_router(tickets.router)
    dp.include_router(admin.router)
    dp.include_router(admin_tickets.router)
    dp.include_router(equipment.router)
    dp.include_router(workplaces.router)
    dp.include_router(faq.router)

    logger.info("IT-ecosystem bot запущен и готов принимать обновления.")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), scheduler=scheduler)
    scheduler.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен (KeyboardInterrupt).")
