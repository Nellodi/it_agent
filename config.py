# Файл: it_ecosystem_bot/config.py
from dataclasses import dataclass
import os

@dataclass
class TgBot:
    """Конфигурация Telegram бота."""
    token: str

@dataclass
class Config:
    """Общая конфигурация приложения."""
    tg_bot: TgBot

def load_config() -> Config:
    """Загружает конфигурацию из переменных окружения."""
    return Config(
        tg_bot=TgBot(token=os.getenv('BOT_TOKEN'))
    )