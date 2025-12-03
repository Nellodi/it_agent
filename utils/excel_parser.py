# Файл: it_ecosystem_bot/utils/excel_parser.py
import pandas as pd
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ExcelParser:
    """Утилита для загрузки и нормализации данных пользователей из Excel."""

    def __init__(self, file_path: str = 'users.xlsx'):
        self.file_path = file_path

    def load_users_data(self) -> List[Dict[str, str]]:
        """Загружает, нормализует и проверяет данные пользователей."""
        if not os.path.exists(self.file_path):
            logger.critical(f"PARSER: ФАТАЛЬНАЯ ОШИБКА: Файл базы пользователей не найден по пути: {self.file_path}")
            return []

        REQUIRED_COLS = ['Name', 'Login', 'Password', 'Department', 'Position']
        normalized_data = []

        try:
            # Читаем все листы, чтобы найти нужный
            xls = pd.ExcelFile(self.file_path, engine='openpyxl')
            sheet_names = xls.sheet_names

            logger.info(f"PARSER: Файл {self.file_path} содержит листы: {sheet_names}")

            for sheet_name in sheet_names:
                df = xls.parse(sheet_name)

                # 1. Нормализация заголовков
                if df.empty:
                    logger.warning(f"PARSER: Лист '{sheet_name}' пуст.")
                    continue

                df.columns = [str(col).strip() for col in df.columns]
                col_map = {col.lower(): col for col in df.columns}

                # 2. Проверяем наличие обязательных колонок
                missing_cols = [col for col in REQUIRED_COLS if col.lower() not in col_map]

                if missing_cols:
                    # Если колонки не найдены, это не тот лист или не та строка заголовка
                    logger.warning(
                        f"PARSER: Лист '{sheet_name}' пропущен. Отсутствуют колонки: {', '.join(missing_cols)}")
                    logger.warning(f"PARSER: Найденные колонки на листе: {list(df.columns)}")

                    # Пробуем загрузить лист, предполагая, что заголовки находятся в строке 1
                    try:
                        df_header1 = xls.parse(sheet_name, header=1)
                        df_header1.columns = [str(col).strip() for col in df_header1.columns]
                        col_map_header1 = {col.lower(): col for col in df_header1.columns}

                        missing_cols_header1 = [col for col in REQUIRED_COLS if col.lower() not in col_map_header1]

                        if not missing_cols_header1:
                            df = df_header1
                            col_map = col_map_header1
                            logger.info(
                                f"PARSER: Успешно найдены данные на листе '{sheet_name}' со смещением заголовка.")
                        else:
                            continue  # Пропускаем этот лист
                    except Exception:
                        continue

                # Если мы дошли сюда, значит, колонки найдены. Начинаем парсинг строк.

                for index, row in df.iterrows():
                    user_data: Dict[str, str] = {}
                    try:
                        login = str(row[col_map['login']]).strip()
                        password = str(row[col_map['password']]).strip()

                        if not login or not password:
                            continue  # Пропускаем строки без обязательных полей

                        user_data['login'] = login.lower()
                        user_data['password'] = password
                        user_data['full_name'] = str(row[col_map['name']]).strip()
                        user_data['department'] = str(row[col_map['department']]).strip()
                        user_data['position'] = str(row[col_map['position']]).strip()
                        user_data['role'] = 'admin' if 'admin' in user_data['position'].lower() else 'user'

                        normalized_data.append(user_data)

                    except Exception as e:
                        logger.error(f"PARSER: Ошибка парсинга строки {index + 2} на листе '{sheet_name}': {e}")

                if normalized_data:
                    # Если нашли данные на одном листе, прекращаем поиск, чтобы избежать дублирования
                    logger.info(
                        f"PARSER: Загружено {len(normalized_data)} пользователей с листа '{sheet_name}'. Поиск завершен.")
                    break

        except Exception as e:
            logger.critical(f"PARSER: КРИТИЧЕСКАЯ ОШИБКА ФАЙЛА: {e}")
            return []

        if not normalized_data:
            logger.critical(
                f"PARSER: НЕТ ДАННЫХ. Не найдено ни одного пользователя с полным набором Login/Password ни на одном листе.")
            return []

        logger.info(f"PARSER: Общее количество загруженных пользователей: {len(normalized_data)}.")
        return normalized_data