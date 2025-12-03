# Файл: it_ecosystem_bot/database.py
import sqlite3  # Убедимся, что sqlite3 импортирован
import asyncio
import logging
import time
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

DB_PATH = 'it_ecosystem.db'


async def init_db():
    """Инициализирует базу данных и создает необходимые таблицы."""

    def create_tables():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Таблица: authorized_users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS authorized_users (
                telegram_id INTEGER PRIMARY KEY,
                login TEXT UNIQUE,
                full_name TEXT,
                department TEXT,
                position TEXT,
                role TEXT DEFAULT 'user',
                authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Таблица: tickets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                ticket_number TEXT UNIQUE,
                title TEXT,
                description TEXT,
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'medium',
                category TEXT,
                admin_id INTEGER, -- ID назначенного администратора
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES authorized_users (telegram_id)
            )
        """)

        # 3. Таблица: sys_admins (Для хранения рейтинга администраторов)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sys_admins (
                telegram_id INTEGER PRIMARY KEY,
                full_name TEXT,
                total_rating REAL DEFAULT 0.0,    -- Общая сумма оценок (для расчета среднего)
                rating_count INTEGER DEFAULT 0,   -- Количество полученных оценок
                FOREIGN KEY (telegram_id) REFERENCES authorized_users (telegram_id)
            )
        """)

        # 4. Таблица: ticket_history (История изменений статусов)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                old_status TEXT,
                new_status TEXT,
                changed_by INTEGER,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                comment TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets (id),
                FOREIGN KEY (changed_by) REFERENCES authorized_users (telegram_id)
            )
        """)

        # 5. Таблица: workplaces (Рабочие места)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workplaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT UNIQUE NOT NULL,
                department TEXT,
                location TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 6. Таблица: equipment (Оборудование)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inv_number TEXT UNIQUE NOT NULL,
                model TEXT,
                serial TEXT,
                category TEXT,
                status TEXT DEFAULT 'available',
                user_id INTEGER,
                workplace_id INTEGER,
                assigned_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES authorized_users (telegram_id),
                FOREIGN KEY (workplace_id) REFERENCES workplaces (id)
            )
        """)

        # 7. Таблица: equipment_history (История распределения оборудования)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equipment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id INTEGER NOT NULL,
                from_user_id INTEGER,
                to_user_id INTEGER,
                assigned_by INTEGER,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT,
                FOREIGN KEY (equipment_id) REFERENCES equipment (id),
                FOREIGN KEY (from_user_id) REFERENCES authorized_users (telegram_id),
                FOREIGN KEY (to_user_id) REFERENCES authorized_users (telegram_id),
                FOREIGN KEY (assigned_by) REFERENCES authorized_users (telegram_id)
            )
        """)

        # 8. Таблица: licenses (Лицензии)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                license_number TEXT UNIQUE,
                product TEXT,
                version TEXT,
                expiry_date DATE,
                status TEXT DEFAULT 'active',
                cost REAL,
                assigned_to INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assigned_to) REFERENCES authorized_users (telegram_id)
            )
        """)

        conn.commit()
        conn.close()

    await asyncio.to_thread(create_tables)


async def save_authorized_user(telegram_id: int, user_data: Dict[str, str]):
    """Сохраняет нового авторизованного пользователя в authorized_users."""

    def insert_user():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        login = user_data['login']
        full_name = user_data['full_name']
        department = user_data['department']
        position = user_data['position']
        role = user_data.get('role', 'user')

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO authorized_users 
                (telegram_id, login, full_name, department, position, role)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (telegram_id, login, full_name, department, position, role))
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"DB: Пользователь {login} ({telegram_id}) успешно сохранен.")
            return True
        except sqlite3.Error as e:
            logger.error(f"DB: Ошибка сохранения пользователя {login}: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(insert_user)


async def get_user_role(telegram_id: int) -> str | None:
    """Получает роль пользователя."""

    def fetch_role():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM authorized_users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    return await asyncio.to_thread(fetch_role)


async def save_new_ticket(user_id: int, data: Dict[str, str]) -> Tuple[int, str]:
    """Сохраняет новую заявку и возвращает ее ID и номер."""

    def insert_ticket():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Генерация номера заявки: TKYYMMDDXXXX (TK2512030001)
        date_part = time.strftime("%y%m%d", time.localtime())
        # Получаем последний номер для сегодняшней даты
        cursor.execute(f"SELECT MAX(ticket_number) FROM tickets WHERE ticket_number LIKE 'TK{date_part}%'")
        last_num = cursor.fetchone()[0]

        if last_num:
            sequence = int(last_num[-4:]) + 1
        else:
            sequence = 1

        ticket_number = f"TK{date_part}{sequence:04d}"

        cursor.execute("""
            INSERT INTO tickets (user_id, ticket_number, title, description, category, priority)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, ticket_number, data['title'], data['description'], data['category'], data['priority']))

        ticket_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return ticket_id, ticket_number

    return await asyncio.to_thread(insert_ticket)


async def get_admin_telegram_ids() -> list[int]:
    """Получает все Telegram ID пользователей с ролью 'admin'."""

    def fetch_admin_ids():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id FROM authorized_users WHERE role = 'admin'")
        admin_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return admin_ids

    return await asyncio.to_thread(fetch_admin_ids)


async def register_sys_admin(telegram_id: int, full_name: str, position: str) -> bool:
    """Регистрирует пользователя как SysAdmin в sys_admins и обновляет role в authorized_users."""

    def register():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            # 1. Обновляем роль в authorized_users
            cursor.execute("UPDATE authorized_users SET role = 'admin', position = ? WHERE telegram_id = ?",
                           (position, telegram_id))

            # 2. Добавляем в sys_admins для отслеживания рейтинга
            cursor.execute("INSERT OR IGNORE INTO sys_admins (telegram_id, full_name) VALUES (?, ?)",
                           (telegram_id, full_name))

            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB: Ошибка регистрации SysAdmin {telegram_id}: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(register)


async def update_admin_rating(admin_id: int, rating: int):
    """Обновляет рейтинг администратора и average_rating."""

    def update_rating():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Получаем текущие данные
        cursor.execute("SELECT total_rating, rating_count FROM sys_admins WHERE telegram_id = ?", (admin_id,))
        result = cursor.fetchone()

        if not result:
            logger.warning(f"DB: SysAdmin {admin_id} не найден для обновления рейтинга.")
            return

        total_rating, rating_count = result

        # 2. Расчет нового рейтинга
        new_total_rating = total_rating + rating
        new_rating_count = rating_count + 1

        # 3. Обновление записи
        cursor.execute("""
            UPDATE sys_admins SET total_rating = ?, rating_count = ?
            WHERE telegram_id = ?
        """, (new_total_rating, new_rating_count, admin_id))

        conn.commit()
        conn.close()
        logger.info(
            f"DB: Рейтинг SysAdmin {admin_id} обновлен. Новая оценка: {rating}. Всего оценок: {new_rating_count}")

    await asyncio.to_thread(update_rating)


async def close_ticket_for_rating(ticket_id: int, admin_id: int) -> int | None:
    """Обновляет статус заявки на 'await_rating' и возвращает user_id создателя."""

    def close_ticket():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Обновляем статус, назначаем админа (если не назначен) и ставим дату закрытия
        cursor.execute("""
            UPDATE tickets 
            SET status = 'await_rating', admin_id = ?, closed_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status != 'await_rating'
        """, (admin_id, ticket_id))

        if cursor.rowcount == 0:
            return None  # Не удалось обновить (возможно, уже в этом статусе)

        # Получаем user_id для отправки запроса на оценку
        cursor.execute("SELECT user_id FROM tickets WHERE id = ?", (ticket_id,))
        user_id = cursor.fetchone()[0]

        conn.commit()
        conn.close()
        return user_id

    return await asyncio.to_thread(close_ticket)


async def get_admin_info(admin_id: int) -> dict | None:
    """Получает ФИО и средний рейтинг администратора."""

    def fetch_admin_info():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT full_name, total_rating, rating_count 
            FROM sys_admins WHERE telegram_id = ?
        """, (admin_id,))
        result = cursor.fetchone()

        if result:
            full_name, total_rating, rating_count = result
            avg_rating = total_rating / rating_count if rating_count > 0 else 0.0
            return {
                'full_name': full_name,
                'avg_rating': round(avg_rating, 2),
            }
        return None

    return await asyncio.to_thread(fetch_admin_info)


async def finalize_ticket_rating(ticket_id: int, rating: int) -> dict | None:
    """Записывает оценку, обновляет статус заявки и возвращает данные для обновления рейтинга."""

    def finalize():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Получаем admin_id заявки
        cursor.execute("SELECT admin_id, ticket_number, user_id FROM tickets WHERE id = ?", (ticket_id,))
        result = cursor.fetchone()
        if not result:
            return None

        admin_id, ticket_number, user_id = result

        if not admin_id:
            logger.error(f"DB: Заявка {ticket_id} не была назначена администратору.")
            return None

        # 2. Обновляем статус заявки на 'closed'
        cursor.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", (ticket_id,))

        conn.commit()
        conn.close()

        # 3. Возвращаем ID администратора и оценку для обновления рейтинга
        return {
            'admin_id': admin_id,
            'ticket_number': ticket_number,
            'user_id': user_id,
            'rating': rating  # <--- Добавляем оценку
        }

    # Возвращаем результат выполнения синхронной части
    return await asyncio.to_thread(finalize)


async def get_user_tickets(user_id: int) -> List[Dict]:
    """Получает список заявок пользователя."""

    def fetch_tickets():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ticket_number, title, status, created_at FROM tickets WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,))

        tickets = []
        for row in cursor.fetchall():
            tickets.append({
                'number': row[0],
                'title': row[1],
                'status': row[2],
                'created': row[3]
            })
        conn.close()
        return tickets

    return await asyncio.to_thread(fetch_tickets)


# !!! ИСПРАВЛЕННАЯ ФУНКЦИЯ ВЫХОДА: Использует синхронный sqlite3
async def remove_authorized_user(telegram_id: int) -> bool:
    """Удаляет пользователя из таблицы authorized_users (деавторизация)."""

    def delete_user():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            # Используем DELETE для удаления пользователя
            cursor.execute("DELETE FROM authorized_users WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB: Ошибка удаления пользователя {telegram_id} из БД: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(delete_user)


# ===== ФУНКЦИИ УПРАВЛЕНИЯ ЗАЯВКАМИ =====

async def assign_ticket_to_admin(ticket_id: int, admin_id: int, old_status: str = None) -> bool:
    """Назначает заявку на администратора и создает запись в истории."""

    def assign_ticket():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            # Получаем текущий статус
            cursor.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,))
            result = cursor.fetchone()
            if not result:
                return False

            current_status = result[0]

            # Обновляем admin_id
            cursor.execute("UPDATE tickets SET admin_id = ? WHERE id = ?", (admin_id, ticket_id))

            # Создаем запись в истории
            cursor.execute("""
                INSERT INTO ticket_history (ticket_id, old_status, new_status, changed_by)
                VALUES (?, ?, ?, ?)
            """, (ticket_id, old_status or current_status, current_status, admin_id))

            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB: Ошибка назначения заявки {ticket_id} на админа {admin_id}: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(assign_ticket)


async def update_ticket_status(ticket_id: int, new_status: str, admin_id: int, comment: str = None) -> bool:
    """Обновляет статус заявки и создает запись в истории."""

    def update_status():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            # Получаем старый статус
            cursor.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,))
            result = cursor.fetchone()
            if not result:
                return False

            old_status = result[0]

            # Обновляем статус
            cursor.execute("UPDATE tickets SET status = ? WHERE id = ?", (new_status, ticket_id))

            # Создаем запись в истории
            cursor.execute("""
                INSERT INTO ticket_history (ticket_id, old_status, new_status, changed_by, comment)
                VALUES (?, ?, ?, ?, ?)
            """, (ticket_id, old_status, new_status, admin_id, comment))

            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB: Ошибка обновления статуса заявки {ticket_id}: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(update_status)


async def get_all_tickets(status: str = None, department: str = None, priority: str = None) -> List[Dict]:
    """Получает список всех заявок с опциональной фильтрацией."""

    def fetch_tickets():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        query = """
            SELECT t.id, t.ticket_number, t.title, t.status, t.priority, t.category, 
                   t.user_id, t.admin_id, t.created_at, u.full_name, u.department
            FROM tickets t
            LEFT JOIN authorized_users u ON t.user_id = u.telegram_id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND t.status = ?"
            params.append(status)
        if priority:
            query += " AND t.priority = ?"
            params.append(priority)
        if department:
            query += " AND u.department = ?"
            params.append(department)

        query += " ORDER BY t.created_at DESC"

        cursor.execute(query, params)
        tickets = []
        for row in cursor.fetchall():
            tickets.append({
                'id': row[0],
                'number': row[1],
                'title': row[2],
                'status': row[3],
                'priority': row[4],
                'category': row[5],
                'user_id': row[6],
                'admin_id': row[7],
                'created_at': row[8],
                'user_name': row[9],
                'department': row[10]
            })
        conn.close()
        return tickets

    return await asyncio.to_thread(fetch_tickets)


async def get_ticket_history(ticket_id: int) -> List[Dict]:
    """Получает историю изменения статуса заявки."""

    def fetch_history():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT th.old_status, th.new_status, th.changed_by, th.changed_at, th.comment,
                   u.full_name
            FROM ticket_history th
            LEFT JOIN authorized_users u ON th.changed_by = u.telegram_id
            WHERE th.ticket_id = ?
            ORDER BY th.changed_at DESC
        """, (ticket_id,))

        history = []
        for row in cursor.fetchall():
            history.append({
                'old_status': row[0],
                'new_status': row[1],
                'changed_by': row[2],
                'changed_at': row[3],
                'comment': row[4],
                'changed_by_name': row[5]
            })
        conn.close()
        return history

    return await asyncio.to_thread(fetch_history)


# ===== ФУНКЦИИ УПРАВЛЕНИЯ ОБОРУДОВАНИЕМ =====

async def create_equipment(inv_number: str, model: str, serial: str, category: str) -> bool:
    """Создает новое оборудование."""

    def create_eq():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO equipment (inv_number, model, serial, category)
                VALUES (?, ?, ?, ?)
            """, (inv_number, model, serial, category))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB: Ошибка создания оборудования {inv_number}: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(create_eq)


async def get_equipment(equipment_id: int = None, inv_number: str = None) -> Dict | None:
    """Получает информацию об оборудовании."""

    def fetch_eq():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if equipment_id:
            cursor.execute("""
                SELECT id, inv_number, model, serial, category, status, user_id, 
                       workplace_id, assigned_at, created_at
                FROM equipment WHERE id = ?
            """, (equipment_id,))
        elif inv_number:
            cursor.execute("""
                SELECT id, inv_number, model, serial, category, status, user_id, 
                       workplace_id, assigned_at, created_at
                FROM equipment WHERE inv_number = ?
            """, (inv_number,))
        else:
            return None

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'id': result[0],
                'inv_number': result[1],
                'model': result[2],
                'serial': result[3],
                'category': result[4],
                'status': result[5],
                'user_id': result[6],
                'workplace_id': result[7],
                'assigned_at': result[8],
                'created_at': result[9]
            }
        return None

    return await asyncio.to_thread(fetch_eq)


async def assign_equipment_to_user(equipment_id: int, user_id: int, assigned_by: int) -> bool:
    """Назначает оборудование пользователю."""

    def assign_eq():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            # Получаем текущего владельца
            cursor.execute("SELECT user_id FROM equipment WHERE id = ?", (equipment_id,))
            result = cursor.fetchone()
            from_user_id = result[0] if result else None

            # Обновляем оборудование
            cursor.execute("""
                UPDATE equipment SET user_id = ?, status = 'assigned', assigned_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id, equipment_id))

            # Создаем запись в истории
            cursor.execute("""
                INSERT INTO equipment_history (equipment_id, from_user_id, to_user_id, assigned_by)
                VALUES (?, ?, ?, ?)
            """, (equipment_id, from_user_id, user_id, assigned_by))

            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB: Ошибка назначения оборудования {equipment_id}: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(assign_eq)


async def get_user_equipment(user_id: int) -> List[Dict]:
    """Получает список оборудования, назначенного пользователю."""

    def fetch_eq():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, inv_number, model, serial, category, status, assigned_at
            FROM equipment
            WHERE user_id = ? AND status = 'assigned'
            ORDER BY assigned_at DESC
        """, (user_id,))

        equipment = []
        for row in cursor.fetchall():
            equipment.append({
                'id': row[0],
                'inv_number': row[1],
                'model': row[2],
                'serial': row[3],
                'category': row[4],
                'status': row[5],
                'assigned_at': row[6]
            })
        conn.close()
        return equipment

    return await asyncio.to_thread(fetch_eq)


async def get_all_equipment(status: str = None, category: str = None) -> List[Dict]:
    """Получает список всего оборудования с опциональной фильтрацией."""

    def fetch_all():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        query = """
            SELECT e.id, e.inv_number, e.model, e.serial, e.category, e.status, 
                   e.user_id, u.full_name, e.assigned_at
            FROM equipment e
            LEFT JOIN authorized_users u ON e.user_id = u.telegram_id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND e.status = ?"
            params.append(status)
        if category:
            query += " AND e.category = ?"
            params.append(category)

        query += " ORDER BY e.created_at DESC"

        cursor.execute(query, params)
        equipment = []
        for row in cursor.fetchall():
            equipment.append({
                'id': row[0],
                'inv_number': row[1],
                'model': row[2],
                'serial': row[3],
                'category': row[4],
                'status': row[5],
                'user_id': row[6],
                'user_name': row[7],
                'assigned_at': row[8]
            })
        conn.close()
        return equipment

    return await asyncio.to_thread(fetch_all)


async def delete_equipment(equipment_id: int) -> bool:
    """Удаляет оборудование."""

    def delete_eq():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM equipment WHERE id = ?", (equipment_id,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB: Ошибка удаления оборудования {equipment_id}: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(delete_eq)


# ===== ФУНКЦИИ УПРАВЛЕНИЯ РАБОЧИМИ МЕСТАМИ =====

async def create_workplace(number: str, department: str, location: str) -> bool:
    """Создает новое рабочее место."""

    def create_wp():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO workplaces (number, department, location)
                VALUES (?, ?, ?)
            """, (number, department, location))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"DB: Ошибка создания рабочего места {number}: {e}")
            return False
        finally:
            conn.close()

    return await asyncio.to_thread(create_wp)


async def get_workplace(workplace_id: int) -> Dict | None:
    """Получает информацию о рабочем месте."""

    def fetch_wp():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, number, department, location, created_at
            FROM workplaces WHERE id = ?
        """, (workplace_id,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'id': result[0],
                'number': result[1],
                'department': result[2],
                'location': result[3],
                'created_at': result[4]
            }
        return None

    return await asyncio.to_thread(fetch_wp)


async def get_workplace_equipment(workplace_id: int) -> List[Dict]:
    """Получает список оборудования, закрепленного за рабочим местом."""

    def fetch_eq():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, inv_number, model, serial, category, status, user_id
            FROM equipment
            WHERE workplace_id = ?
            ORDER BY inv_number
        """, (workplace_id,))

        equipment = []
        for row in cursor.fetchall():
            equipment.append({
                'id': row[0],
                'inv_number': row[1],
                'model': row[2],
                'serial': row[3],
                'category': row[4],
                'status': row[5],
                'user_id': row[6]
            })
        conn.close()
        return equipment

    return await asyncio.to_thread(fetch_eq)


async def get_all_workplaces() -> List[Dict]:
    """Получает список всех рабочих мест."""

    def fetch_all():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, number, department, location
            FROM workplaces
            ORDER BY number
        """)

        workplaces = []
        for row in cursor.fetchall():
            workplaces.append({
                'id': row[0],
                'number': row[1],
                'department': row[2],
                'location': row[3]
            })
        conn.close()
        return workplaces

    return await asyncio.to_thread(fetch_all)