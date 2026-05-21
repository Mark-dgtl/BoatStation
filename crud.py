from datetime import datetime
from typing import Optional, List

import psycopg2

from database import db_query
from sql_queries import auth as q_auth
from sql_queries import client as q_client
from sql_queries import common as q_common
from sql_queries import admin as q_admin
from sql_queries import instructor as q_instructor
from sql_queries import superadmin as q_superadmin
from sql_queries import rental_request as q_rr
from sql_queries import user as q_user
from sql_queries import vessel as q_vessel
from models import UserLogin, UserRegister, RentalRequestCreate, RentalRequestUpdateStatus, RentCreate
from schemas import RentalRequest, Rent, Vessel, WaterBody, Instruction
import logging

logger = logging.getLogger(__name__)


def parse_naive_datetime(value: str) -> datetime:
    """Парсит datetime-local (YYYY-MM-DDTHH:MM) или ISO без сдвига часового пояса."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Дата и время не указаны")
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        dt = datetime.strptime(value[:16], "%Y-%m-%dT%H:%M")
    return dt.replace(tzinfo=None) if dt.tzinfo else dt

# --- AUTH ---
def authenticate_user(login: str, password: str) -> Optional[dict]:
    with db_query() as query:
        query.execute(q_auth.AUTHENTICATE_USER, (login, password))
        user = query.fetchone()
        if user:
            logger.info(f"User {login} authenticated successfully.")
            return dict(user) # Convert RealDictRow to dict
        else:
            logger.warning(f"Authentication failed for login: {login}")
            return None

def get_user_by_login(login: str) -> Optional[dict]:
    with db_query() as query:
        query.execute(q_auth.GET_USER_BY_LOGIN, (login,))
        user = query.fetchone()
        return dict(user) if user else None

def create_client_and_user(user_data: UserRegister) -> Optional[dict]:
    with db_query() as query:
        try:
            # Начинаем транзакцию (conn.commit() в конце менеджера контекста)
            # 1. Получить role_id для 'client'
            query.execute(q_auth.GET_CLIENT_ROLE_ID)
            role_row = query.fetchone()
            if not role_row:
                logger.error("Role 'client' not found in database.")
                return None
            client_role_id = role_row['id']

            # 2. Создать пользователя
            query.execute(q_auth.INSERT_USER, (user_data.login, user_data.password, client_role_id))
            user_id = query.fetchone()['id']
            logger.debug(f"Created user with ID {user_id} for login {user_data.login}")

            # 3. Создать клиента
            query.execute(q_auth.INSERT_CLIENT, (user_data.surname, user_data.address, user_data.passport, user_id))
            client = query.fetchone()
            logger.info(f"Created client with ID {client['id']} linked to user ID {user_id}")

            return dict(client)
        except psycopg2.Error as e:
            logger.error(f"Database error during user registration: {e}")
            # Rollback handled by context manager
            return None

# --- CLIENT ---
def get_client_by_user_id(user_id: int) -> Optional[dict]:
    with db_query() as query:
        query.execute(q_client.GET_CLIENT_BY_USER_ID, (user_id,))
        client = query.fetchone()
        return dict(client) if client else None

def update_client_profile(user_id: int, update_data: dict) -> Optional[dict]:
    with db_query() as query:
        try:
            query.execute(q_client.UPDATE_CLIENT_PROFILE, (update_data.get('surname'), update_data.get('address'), update_data.get('passport'), user_id))
            updated_client = query.fetchone()
            if updated_client:
                logger.info(f"Updated profile for client linked to user ID {user_id}")
                return dict(updated_client)
            else:
                logger.warning(f"No client found for user ID {user_id} to update.")
                return None
        except psycopg2.Error as e:
            logger.error(f"Database error during profile update: {e}")
            return None

def get_rental_history_by_client_id(client_id: int) -> List[dict]:
    with db_query() as query:
        query.execute(q_client.GET_RENTAL_HISTORY, (client_id,))
        rows = query.fetchall()
        return [dict(row) for row in rows]

def get_current_rental_by_client_id(client_id: int) -> Optional[dict]:
    with db_query() as query:
        query.execute(q_client.GET_CURRENT_RENTAL, (client_id,))
        row = query.fetchone()
        return dict(row) if row else None

def _rental_request_row_to_dict(row) -> dict:
    """Преобразует строку заявки с JOIN в структуру для Jinja-шаблонов."""
    data = dict(row)
    data["vessel"] = {
        "id": data["vessel_id"],
        "name": data["vessel_name"],
        "number": data.get("vessel_number"),
        "type_name": data["type_name"],
    }
    data["water_body"] = {
        "id": data["water_body_id"],
        "name": data["water_body_name"],
    }
    data["client"] = {
        "id": data["client_id"],
        "surname": data.get("client_surname"),
    }
    instructor_surname = data.get("instructor_surname")
    instructor_id = data.get("assigned_instructor_id")
    data["assigned_instructor"] = (
        {"id": instructor_id, "surname": instructor_surname}
        if instructor_id else None
    )
    return data

def get_pending_requests_by_client_id(client_id: int) -> List[dict]:
    with db_query() as query:
        query.execute(q_rr.PENDING_BY_CLIENT, (client_id,))
        rows = query.fetchall()
        return [_rental_request_row_to_dict(row) for row in rows]

def get_vessels_with_equipment() -> List[dict]:
    with db_query() as query:
        query.execute(q_client.GET_VESSELS_WITH_EQUIPMENT)
        rows = query.fetchall()
        return [dict(row) for row in rows]

def get_all_water_bodies(db_cursor: object) -> List[dict]: # Принимаем db_cursor
    """
    Получает список всех водоемов.
    :rtype: List[dict]
    """
    db_cursor.execute(q_client.GET_ALL_WATER_BODIES)
    rows = db_cursor.fetchall()
    return [dict(row) for row in rows]


def _water_body_category_key(name: str) -> str:
    lower = (name or "").lower()
    if "водохр" in lower or "водохран" in lower:
        return "reservoir"
    if "озер" in lower:
        return "lake"
    if "залив" in lower or "река" in lower or "речн" in lower or "морск" in lower:
        return "bay"
    return "other"


WATER_BODY_CATEGORY_LABELS = {
    "reservoir": "Водохранилище",
    "lake": "Озеро",
    "bay": "Залив / река",
    "other": "Другое",
}


def get_water_bodies_for_client_page(db_cursor: object) -> tuple[List[dict], List[dict]]:
    """Водоёмы с категорией, счётчиком судов и списком типов для фильтра."""
    db_cursor.execute(q_client.GET_WATER_BODIES_WITH_VESSEL_COUNT)
    rows = [dict(row) for row in db_cursor.fetchall()]
    for row in rows:
        key = _water_body_category_key(row["name"])
        row["category_key"] = key
        row["category_label"] = WATER_BODY_CATEGORY_LABELS[key]
    type_counts: dict = {}
    for row in rows:
        type_counts[row["category_key"]] = type_counts.get(row["category_key"], 0) + 1
    categories = [
        {"key": "all", "label": "Все", "count": len(rows)},
    ]
    for key, label in WATER_BODY_CATEGORY_LABELS.items():
        if type_counts.get(key):
            categories.append({"key": key, "label": label, "count": type_counts[key]})
    return rows, categories

def is_vessel_water_body_allowed(vessel_id: int, water_body_id: int) -> bool:
    with db_query() as query:
        query.execute(q_client.IS_VESSEL_WATER_BODY_ALLOWED, (water_body_id, vessel_id))
        return bool(query.fetchone()["is_allowed"])


def get_allowed_water_bodies_by_vessel_type(db_cursor: object) -> dict:
    """Водоёмы, разрешённые для типа судна (Swimming_danger.is_dangerous = false)."""
    db_cursor.execute(q_client.GET_ALLOWED_WATER_BODIES_BY_VESSEL_TYPE)
    result: dict = {}
    for row in db_cursor.fetchall():
        result.setdefault(row["vessel_type"], []).append({"id": row["id"], "name": row["name"]})
    return result

def get_available_vessels_for_water_body(water_body_id: int) -> List[dict]:
    with db_query() as query:
        query.execute(q_client.GET_AVAILABLE_VESSELS_FOR_WATER_BODY, (water_body_id,))
        rows = query.fetchall()
        return [dict(row) for row in rows]

def create_rental_request(client_id: int, vessel_id: int, water_body_id: int, desired_start: datetime, desired_end: datetime) -> Optional[dict]:
    with db_query() as query:
        try:
            query.execute(q_rr.CREATE, (client_id, vessel_id, water_body_id, desired_start, desired_end))
            new_request = query.fetchone()
            if new_request:
                logger.info(f"Created rental request {new_request['id']} for client {client_id}.")
                return dict(new_request)
            else:
                logger.error("Failed to create rental request.")
                return None
        except psycopg2.Error as e:
            logger.error(f"Database error during request creation: {e}")
            return None

def get_rentals_by_vessel_and_date(vessel_id: int, target_date_str: str) -> List[dict]:
    with db_query() as query:
        query.execute(q_client.GET_RENTALS_BY_VESSEL_AND_DATE, (vessel_id, target_date_str))
        rows = query.fetchall()
        return [dict(row) for row in rows]

# --- Функция проверки доступности ---
def client_period_conflicts_with_active_rental(
    client_id: int, desired_start: datetime, desired_end: datetime
) -> bool:
    """True, если новый период пересекается с незакрытой арендой клиента."""
    with db_query() as query:
        query.execute(
            q_common.CHECK_CLIENT_RENTAL_PERIOD_OVERLAP,
            (client_id, desired_start, desired_end),
        )
        return query.fetchone() is not None


def check_vessel_availability(vessel_id: int, desired_start: datetime, desired_end: datetime) -> bool:
    with db_query() as query:
        query.execute(
            q_common.CHECK_VESSEL_AVAILABILITY,
            (vessel_id, desired_end, desired_start, vessel_id, desired_end),
        )
        return not query.fetchone()["is_taken"]


def check_availability(client_id: int, vessel_id: int, desired_start: datetime, desired_end: datetime) -> bool:
    """Период не пересекается с активной арендой клиента и судно свободно."""
    if client_period_conflicts_with_active_rental(client_id, desired_start, desired_end):
        return False
    return check_vessel_availability(vessel_id, desired_start, desired_end)

def client_has_active_rental(client_id: int) -> bool:
    with db_query() as query:
        query.execute(q_common.CHECK_CLIENT_ACTIVE_RENTAL, (client_id,))
        return query.fetchone() is not None

def get_instructors_with_pending_load(db_cursor) -> List[dict]:
    """Список инструкторов с числом предстоящих заявок (status = pending)."""
    db_cursor.execute(q_common.GET_INSTRUCTORS_WITH_PENDING_LOAD)
    return [dict(row) for row in db_cursor.fetchall()]

# --- Функция назначения инструктора ---
def assign_instructor_to_request(request_id: int, instructor_id: int | None = None) -> Optional[int]:
    """
    Назначает инструктора на заявку.
    Если instructor_id задан — назначает его, иначе берёт первого из списка.
    """
    with db_query() as query:
        try:

            if instructor_id is not None:
                query.execute(q_common.GET_INSTRUCTOR_BY_ID, (instructor_id,))
                if not query.fetchone():
                    logger.warning(f"Instructor {instructor_id} not found for request {request_id}")
                    return None
                selected_instructor_id = instructor_id
            else:
                query.execute(q_common.GET_FIRST_INSTRUCTOR)
                row = query.fetchone()
                if not row:
                    logger.warning(f"No instructors available to assign to request {request_id}")
                    return None
                selected_instructor_id = row["id"]

            # Отдельный инструктаж на каждую заявку (time_conducted заполняется при подтверждении).
            query.execute(q_common.INSERT_INSTRUCTION, (selected_instructor_id,))
            instruction_row = query.fetchone()
            if not instruction_row:
                logger.warning(f"Failed to create instruction for request {request_id}")
                return None

            query.execute(q_rr.UPDATE_INSTRUCTION_ID, (instruction_row["id"], request_id))
            logger.info(f"Assigned instructor {selected_instructor_id} to request {request_id}")
            return selected_instructor_id
        except psycopg2.Error as e:
            logger.error(f"Database error during instructor assignment for request {request_id}: {e}")
            return None

# --- ADMIN ---
def get_admin_dashboard_stats() -> dict:
    with db_query() as query:
        query.execute(q_admin.GET_DASHBOARD_STATS)
        stats = query.fetchone()
        return dict(stats) if stats else {}

def get_pending_rental_requests() -> List[dict]:
    with db_query() as query:
        query.execute(q_rr.PENDING_ALL)
        rows = query.fetchall()
        return [_rental_request_row_to_dict(row) for row in rows]

def get_rental_request_by_id(request_id: int) -> Optional[dict]:
    with db_query() as query:
        query.execute(q_rr.GET_BY_ID, (request_id,))
        row = query.fetchone()
        return dict(row) if row else None

def get_rent_by_request_id(request_id: int) -> Optional[dict]:
    with db_query() as query:
        query.execute(q_rr.GET_RENT_BY_REQUEST_ID, (request_id,))
        row = query.fetchone()
        return dict(row) if row else None

def update_rental_request_status(request_id: int, new_status: str, comment: str = None) -> Optional[dict]:
    with db_query() as query:
        try:
            query.execute(q_rr.UPDATE_STATUS, (new_status, request_id))
            updated_request = query.fetchone()
            if updated_request:
                logger.info(f"Updated request {request_id} status to {new_status}")
                return dict(updated_request)
            else:
                logger.warning(f"Request {request_id} not found for status update.")
                return None
        except psycopg2.Error as e:
            logger.error(f"Database error during request status update: {e}")
            return None

def create_rent_from_approved_request(rent_data: RentCreate) -> Optional[dict]:
    with db_query() as query:
        try:
            # Вставка новой аренды
            query.execute(q_common.INSERT_RENT, (rent_data.client_id, rent_data.instruction_id, rent_data.vessel_id, rent_data.water_body_id, rent_data.start_time, rent_data.return_time))
            new_rent = query.fetchone()
            if new_rent:
                logger.info(f"Created rental {new_rent['id']} from approved request.")
                return dict(new_rent)
            else:
                logger.error("Failed to create rental from approved request.")
                return None
        except psycopg2.Error as e:
            logger.error(f"Database error during rental creation: {e}")
            return None

def get_active_rentals() -> List[dict]:
    with db_query() as query:
        query.execute(q_admin.GET_ACTIVE_RENTALS)
        rows = query.fetchall()
        return [dict(row) for row in rows]

def get_vessels_grouped_by_status() -> dict:
    with db_query() as query:
        query.execute(q_admin.GET_VESSELS_GROUPED)
        rows = query.fetchall()
        grouped = {}
        for row in rows:
            status = row['status_name']
            if status not in grouped:
                grouped[status] = []
            grouped[status].append(dict(row))
        return grouped

def get_all_repair_logs() -> List[dict]:
    with db_query() as query:
        query.execute(q_admin.GET_ALL_REPAIR_LOGS)
        rows = query.fetchall()
        return [dict(row) for row in rows]

# --- INSTRUCTOR ---
def get_instructor_by_user_id(user_id: int) -> Optional[dict]:
    with db_query() as query:
        query.execute(q_instructor.GET_INSTRUCTOR_BY_USER_ID, (user_id,))
        instructor = query.fetchone()
        return dict(instructor) if instructor else None

def get_upcoming_instructions_for_instructor(instructor_id: int) -> List[dict]:
    with db_query() as query:
        query.execute(q_instructor.GET_UPCOMING_INSTRUCTIONS, (instructor_id,))
        rows = query.fetchall()
        return [dict(row) for row in rows]

def get_conducted_instructions_for_instructor(instructor_id: int) -> List[dict]:
    with db_query() as query:
        query.execute(q_instructor.GET_CONDUCTED_INSTRUCTIONS, (instructor_id,))
        rows = query.fetchall()
        return [dict(row) for row in rows]

def get_rental_request_for_instructor(instructor_id: int, request_id: int) -> Optional[dict]:
    with db_query() as query:
        query.execute(q_rr.FOR_INSTRUCTOR, (request_id, instructor_id))
        row = query.fetchone()
        return dict(row) if row else None

def confirm_instruction_for_request(request_id: int, instructor_id: int) -> Optional[dict]:
    """Инструктор отмечает инструктаж проведённым; заявка переходит в instructor_confirmed."""
    request_obj = get_rental_request_by_id(request_id)
    if not request_obj or request_obj["status"] != "pending":
        return None
    instruction_id = request_obj.get("instruction_id")
    if not instruction_id:
        return None

    with db_query() as query:
        try:
            query.execute(q_common.MARK_INSTRUCTION_CONDUCTED, (instruction_id, instructor_id))
            if not query.fetchone():
                return None
            query.execute(q_rr.CONFIRM_BY_INSTRUCTOR, (request_id,))
            updated_request = query.fetchone()
            if updated_request:
                logger.info(f"Instructor {instructor_id} conducted instruction {instruction_id} for request {request_id}")
                return dict(updated_request)
            return None
        except psycopg2.Error as e:
            logger.error(f"Database error during instructor confirmation: {e}")
            return None

def update_request_status_to_confirmed(request_id: int) -> Optional[dict]:
    """Устаревшая обёртка; предпочтительно confirm_instruction_for_request."""
    request_obj = get_rental_request_by_id(request_id)
    if not request_obj or not request_obj.get("instruction_id"):
        return None
    with db_query() as query:
        query.execute(q_common.GET_INSTRUCTION_BY_ID, (request_obj["instruction_id"],))
        instr = query.fetchone()
        if not instr:
            return None
    return confirm_instruction_for_request(request_id, instr["instructor_id"])

# --- SUPERADMIN ---
def get_superadmin_dashboard_stats() -> dict:
    with db_query() as query:
        query.execute(q_superadmin.GET_DASHBOARD_STATS)
        stats = query.fetchone()
        return dict(stats) if stats else {}

def get_allowed_tables_for_crud() -> List[str]:
    # Белый список таблиц для универсального CRUD
    return [
        "users", "client", "instructor", "administrator",
        "vessel", "rent", "instruction", "swimming_danger",
        "equipment", "connected_water_bodies", "tech_condition_log",
        "vessel_status_log", "type_vessel", "type_status_vessel", "type_instruction", "role"
        # ... добавить остальные разрешенные ...
    ]

def read_table_data(table_name: str, filters: dict = None) -> List[dict]:
    allowed_tables = get_allowed_tables_for_crud()
    if table_name.lower() not in allowed_tables:
        raise ValueError(f"Access to table '{table_name}' is forbidden.")

    sql = f"SELECT * FROM {table_name}" # Потенциально небезопасно!
    params = []
    if filters:
        # Очень базовая проверка на безопасность ключей
        import re
        conditions = []
        for key, value in filters.items():
            if not re.match(r'^[a-zA-Z0-9_]+$', key): # Только буквы, цифры, _
                raise ValueError(f"Invalid filter key: {key}")
            conditions.append(f"{key} = %s")
            params.append(value)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

    with db_query() as query:
        query.execute(sql, params)
        rows = query.fetchall()
        return [dict(row) for row in rows]


# --- INSTRUCTION CRUD (добавлено) ---
def get_instruction_by_id(instruction_id: int) -> Optional[dict]:
    with db_query() as query:
        query.execute(q_common.GET_INSTRUCTION_BY_ID, (instruction_id,))
        row = query.fetchone()
        return dict(row) if row else None

# --- RENT CRUD (добавлено) ---
def create_rent(rent_: RentCreate) -> Optional[dict]:
    with db_query() as query:
        try:
            query.execute(q_common.INSERT_RENT, (rent_.client_id, rent_.instruction_id, rent_.vessel_id, rent_.water_body_id, rent_.start_time, rent_.return_time))
            new_rent = query.fetchone()
            if new_rent:
                if rent_.return_time is None:
                    query.execute(q_common.SET_VESSEL_STATUS_RENTED, (rent_.vessel_id,))
                logger.info(f"Created rental {new_rent['id']}.")
                return dict(new_rent)
            else:
                logger.error("Failed to create rental.")
                return None
                # В файле crud.py найдите блок except в функции create_rent:
        except psycopg2.Error as e:
            logger.error(f"Database error during rental creation: {e}")
            # ДОБАВЬТЕ ЭТУ СТРОКУ:
            raise Exception(f"БАЗА ГОВОРИТ: {e}")


            # ... (предыдущие импорты и функции) ...

# --- RENTAL REQUEST CRUD (обновлено) ---
# Уже есть create_rental_request, get_rental_request_by_id, get_rental_requests_by_status, get_pending_rental_requests
# Добавим функцию для получения заявок, назначенных инструктору
def get_rental_requests_by_assigned_instructor_id(db_cursor, instructor_user_id: int) -> List[dict]:
    """Заявки в статусе pending, назначенные инструктору (по Users.id из cookie)."""
    # Статус 'pending' означает, что заявка создана, но инструктор еще не подтвердил
    # 'instructor_confirmed' означает, что инструктор подтвердил, и она ждет утверждения админом
    # Пусть инструктор видит и те, и другие (или только 'pending'?)
    # По UI-UX: "При оставлении заявки, заявка появляется и у админа и у инструктора"
    # Значит, инструктор видит 'pending'. После подтверждения она становится 'instructor_confirmed', и инструктор её больше не видит в списке "ожидающих"?
    # Или он видит все свои подтверждённые и неподтверждённые?
    # В `instructor/instructions.html`:
    # assigned_requests = crud.get_rental_requests_by_assigned_instructor_id(instructor_info['id']) # Это 'pending'
    # conducted_instructions = crud.get_conducted_instructions_for_instructor(instructor_info['id']) # Это уже проведённые (или связанные с арендами?)
    # Пусть `get_rental_requests_by_assigned_instructor_id` возвращает только 'pending'.
    db_cursor.execute(q_rr.BY_INSTRUCTOR_USER_PENDING, (instructor_user_id,))
    rows = db_cursor.fetchall()
    return [_rental_request_row_to_dict(row) for row in rows]

# --- INSTRUCTION CRUD (обновлено) ---
# Уже есть get_instruction_by_id, create_instruction (но не реализована в CRUD, а в роутере инструктора)
# Добавим функцию для получения инструктажей инструктора
def get_instructions_for_instructor(db_cursor, instructor_id: int) -> List[dict]:
    """Получает все инструктажи, проведённые или назначенные инструктору."""
    db_cursor.execute(q_common.GET_INSTRUCTIONS_FOR_INSTRUCTOR, (instructor_id,))
    rows = db_cursor.fetchall()
    return [dict(row) for row in rows]

# --- VESSEL CRUD (обновлено) ---
# Уже есть get_vessels_with_equipment, get_vessels_by_status_name, get_vessels_with_status_and_type, get_free_vessels_count
# Добавим функцию для получения *всех* плавсредств (для админской вкладки)
def get_all_vessels(db_cursor) -> List[dict]:
    """Получает все плавсредства с информацией из представления."""
    db_cursor.execute(q_vessel.GET_ALL_VESSELS)
    rows = db_cursor.fetchall()
    return [dict(row) for row in rows]

# --- USER CRUD (обновлено) ---
# Уже есть authenticate_user, get_user_by_login, create_client_and_user
# Добавим функцию для получения данных пользователя по ID (для header'а)
def get_user_by_id(db_cursor, user_id: int) -> Optional[dict]:
    """Получает данные пользователя по ID."""
    db_cursor.execute(q_user.GET_USER_BY_ID, (user_id,))
    row = db_cursor.fetchone()
    return dict(row) if row else None

# --- ADMIN CRUD ---
# Уже есть get_admin_dashboard_stats, get_pending_rental_requests, get_rental_request_by_id, update_rental_request_status, create_rent_from_approved_request, get_active_rentals, get_vessels_grouped_by_status, get_all_repair_logs
# Добавим функцию для получения всех пользователей (для суперадмина)
def get_all_users(db_cursor) -> List[dict]:
    """Получает всех пользователей с ролями."""
    db_cursor.execute(q_superadmin.GET_ALL_USERS)
    rows = db_cursor.fetchall()
    return [dict(row) for row in rows]


def get_all_clients_for_form(query):
    query.execute(q_client.GET_ALL_CLIENTS_FOR_FORM)
    return [dict(row) for row in query.fetchall()]


# --- SUPERADMIN CRUD ---
# Уже есть get_superadmin_dashboard_stats, get_allowed_tables_for_crud, read_table_data, и CRUD для superadmin роутера
# Функции для управления пользователями (для суперадмина)
def get_user_details(db_cursor, user_id: int) -> Optional[dict]:
    """Получает подробные данные о пользователе и связанной сущности (Client, Instructor, Admin)."""
    # Сначала получим базовые данные
    user_basic = get_user_by_id(db_cursor, user_id)
    if not user_basic:
        return None

    role_name = user_basic['role_name']
    details = user_basic.copy()

    # Затем получим специфичные данные в зависимости от роли
    if role_name == 'client':
        db_cursor.execute(q_client.GET_CLIENT_DETAILS_BY_USER_ID, (user_id,))
        client_data = db_cursor.fetchone()
        if client_data:
            details.update(dict(client_data))
    elif role_name == 'instructor':
        db_cursor.execute(q_instructor.GET_INSTRUCTOR_DETAILS_BY_USER_ID, (user_id,))
        instructor_data = db_cursor.fetchone()
        if instructor_data:
            details.update(dict(instructor_data))
    elif role_name == 'admin':
        # У администратора, по База.md, только user_id. Добавим проверку.
        db_cursor.execute(q_superadmin.GET_ADMIN_BY_USER_ID, (user_id,))
        admin_data = db_cursor.fetchone()
        if admin_data:
            details['admin_user_id'] = admin_data['user_id'] # Просто подтверждение наличия
    # Добавьте другие роли при необходимости

    return details

def update_user_role(db_cursor, user_id: int, new_role_name: str):
    """Обновляет роль пользователя."""
    # Проверим, существует ли новая роль
    db_cursor.execute(q_superadmin.GET_ROLE_ID_BY_NAME, (new_role_name,))
    role_row = db_cursor.fetchone()
    if not role_row:
        raise ValueError(f"Role '{new_role_name}' does not exist.")

    role_id = role_row['id']
    db_cursor.execute(q_superadmin.UPDATE_USER_ROLE, (role_id, user_id))

def delete_user(db_cursor, user_id: int):
    """Удаляет пользователя и связанную сущность (Client, Instructor, Admin)."""
    # Это сложная операция, требующая каскадного удаления или проверки зависимостей.
    # Для упрощения, предположим, что в БД настроены каскадные внешние ключи (что не так по База.md).
    # В реальности нужно сначала удалить все зависимости (аренды, инструктажи, заявки), связанные с пользователем.
    # Или, если пользователь участвовал в арендах, возможно, стоит просто заблокировать аккаунт, а не удалять.
    # Для курсовой, допустим, можно удалить, если нет активных связей.
    # Проверим, есть ли активные аренды у клиента
    user_details = get_user_details(db_cursor, user_id)
    if not user_details:
        raise ValueError(f"User with ID {user_id} does not exist.")

    role = user_details['role_name']
    if role == 'client':
        # Проверим активные аренды
        db_cursor.execute(q_common.ACTIVE_RENTAL_BY_CLIENT_USER, (user_id,))
        active_rentals = db_cursor.fetchall()
        if active_rentals:
             raise ValueError(f"Cannot delete client {user_id} because they have active rentals: {[r['id'] for r in active_rentals]}")

    # Проверим, есть ли активные заявки
    db_cursor.execute(q_rr.ACTIVE_REQUESTS_BY_USER, (user_id,))
    active_requests = db_cursor.fetchall()
    if active_requests:
         raise ValueError(f"Cannot delete client {user_id} because they have active rental requests: {[r['id'] for r in active_requests]}")


    # Проверим, проводил ли инструктор инструктажи
    if role == 'instructor':
        db_cursor.execute(q_common.CONDUCTED_INSTRUCTIONS_BY_USER, (user_id,))
        conducted_instr = db_cursor.fetchall()
        if conducted_instr:
             raise ValueError(f"Cannot delete instructor {user_id} because they have conducted instructions: {[i['id'] for i in conducted_instr]}")

    # Если всё в порядке, удаляем
    # Удаляем из подтипов (Client, Instructor, Admin)
    if role == 'client':
        db_cursor.execute(q_client.DELETE_CLIENT_BY_USER_ID, (user_id,))
    elif role == 'instructor':
        db_cursor.execute(q_instructor.DELETE_INSTRUCTOR_BY_USER_ID, (user_id,))
    elif role == 'admin':
        db_cursor.execute(q_superadmin.DELETE_ADMIN_BY_USER_ID, (user_id,))

    # Удаляем из Users
    db_cursor.execute(q_superadmin.DELETE_USER_BY_ID, (user_id,))
    logger.info(f"Deleted user {user_id} and associated records.")

# --- UTILS (обновлено) ---
# Уже есть check_availability, assign_instructor_to_request
# Добавим функцию для получения доступных часов (уже в client.py, перенесём сюда)
def get_available_hours_for_vessel_and_date(db_cursor, vessel_id: int, target_date_str: str) -> List[str]:
    """Получает список доступных часов для плавсредства на определённую дату."""
    db_cursor.execute(q_client.GET_RENTALS_BY_VESSEL_AND_DATE, (vessel_id, target_date_str))
    rows = db_cursor.fetchall()

    booked_hours = set()
    for rental in rows:
        start_hour = rental['start_time'].hour
        # Включаем час начала, исключаем час окончания (если не совпадает)
        end_hour = rental['return_time'].hour if rental['return_time'] else start_hour + 1
        for h in range(start_hour, min(end_hour, 24)): # Ограничиваем 24 часами
            booked_hours.add(h)

    available_hours = []
    for hour in range(9, 18): # С 9 утра до 6 вечера
        if hour not in booked_hours:
            available_hours.append(f"{hour:02d}:00 - {hour+1:02d}:00")

    return available_hours

def get_all_instructions(db_cursor) -> List[dict]:
    """
    Получает список всех инструктажей с подробной информацией:
    - ID инструктажа
    - ФИО инструктора
    - Тип инструктажа
    - Время проведения (может быть NULL)
    - ID клиента (для связи с арендой)
    """
    db_cursor.execute(q_common.GET_ALL_INSTRUCTIONS)
    rows = db_cursor.fetchall()
    return [dict(row) for row in rows]


def get_vessel_by_id(db_cursor, vessel_id: int) -> Optional[dict]:
    """
    Получает информацию о плавсредстве по ID.
    """
    db_cursor.execute(q_vessel.GET_VESSEL_BY_ID, (vessel_id,))
    vessel = db_cursor.fetchone()
    return dict(vessel) if vessel else None


def get_all_vessel_types(db_cursor) -> List[dict]:
    """
    Получает список всех типов плавсредств.
    """
    db_cursor.execute(q_vessel.GET_ALL_VESSEL_TYPES)
    return [dict(row) for row in db_cursor.fetchall()]


def get_all_vessel_statuses(db_cursor) -> List[dict]:
    """
    Получает список всех статусов плавсредств.
    """
    db_cursor.execute(q_vessel.GET_ALL_VESSEL_STATUSES)
    return [dict(row) for row in db_cursor.fetchall()]


def update_vessel(db_cursor, vessel_id: int, data: dict) -> Optional[dict]:
    """
    Обновляет информацию о плавсредстве.
    """
    # Проверяем, существует ли плавсредство
    db_cursor.execute(q_vessel.GET_VESSEL_EXISTS, (vessel_id,))
    if not db_cursor.fetchone():
        return None

    # Проверяем, что номер плавсредства уникален (если он был изменен)
    if 'number' in data:
        db_cursor.execute(q_vessel.GET_VESSEL_BY_NUMBER_EXCLUDING, (data['number'], vessel_id))
        if db_cursor.fetchone():
            raise ValueError("Плавсредство с таким номером уже существует.")

    # Формируем запрос обновления
    set_clause = []
    values = []

    if 'name' in data:
        set_clause.append("name = %s")
        values.append(data['name'])

    if 'number' in data:
        set_clause.append("number = %s")
        values.append(data['number'])

    if 'type_vessel_id' in data:
        set_clause.append("type_vessel_id = %s")
        values.append(data['type_vessel_id'])

    if 'current_status_id' in data:
        set_clause.append("current_status_id = %s")
        values.append(data['current_status_id'])

    if not set_clause:
        return None  # Нечего обновлять

    # Добавляем ID в значения для условия WHERE
    values.append(vessel_id)

    query = f"UPDATE Vessel SET {', '.join(set_clause)} WHERE id = %s RETURNING *;"
    db_cursor.execute(query, values)
    updated_vessel = db_cursor.fetchone()

    return dict(updated_vessel) if updated_vessel else None


def get_repair_logs(db_cursor) -> List[dict]:
    """
    Получает журнал технического состояния плавсредств.
    Возвращает список записей с информацией о плавсредстве, типе состояния и времени изменения.
    """
    db_cursor.execute(q_admin.GET_REPAIR_LOGS)
    rows = db_cursor.fetchall()
    return [dict(row) for row in rows]


def get_all_vessel_types(db_cursor) -> List[dict]:
    """
    Получает список всех типов плавсредств.
    """
    db_cursor.execute(q_vessel.GET_ALL_VESSEL_TYPES)
    return [dict(row) for row in db_cursor.fetchall()]


def get_all_vessel_statuses(db_cursor) -> List[dict]:
    """
    Получает список всех статусов плавсредств.
    """
    db_cursor.execute(q_vessel.GET_ALL_VESSEL_STATUSES)
    return [dict(row) for row in db_cursor.fetchall()]


def create_vessel(db_cursor, data: dict) -> Optional[dict]:
    """
    Создает новое плавсредство.
    """
    # Проверка на уникальность номера
    db_cursor.execute(q_vessel.GET_VESSEL_BY_NUMBER, (data['number'],))
    if db_cursor.fetchone():
        raise ValueError("Плавсредство с таким номером уже существует.")

    # Создание плавсредства
    db_cursor.execute(q_vessel.INSERT_VESSEL, (
        data['name'],
        data['number'],
        data['type_vessel_id'],
        data['current_status_id']
    ))

    new_vessel = db_cursor.fetchone()
    return dict(new_vessel) if new_vessel else None


def update_rent_return_time(rental_id: int, return_time):
    with db_query() as query:
        # 1. Закрываем аренду и получаем ID лодки через RETURNING
        query.execute(q_common.UPDATE_RENT_RETURN_TIME, (return_time, rental_id))

        result = query.fetchone()

        if result:
            # Извлекаем ID лодки (зависит от настроек твоего курсора)
            v_id = result['vessel_id'] if isinstance(result, dict) else result[0]

            # 2. Сразу меняем статус этой лодки на 1 (Свободен)
            query.execute(q_common.SET_VESSEL_STATUS_FREE, (v_id,))
            return result

        return None


def get_user_by_id_with_role(db_cursor, user_id: int) -> Optional[dict]:
    """Получает данные пользователя вместе с role_id"""
    db_cursor.execute(q_user.GET_USER_BY_ID_WITH_ROLE, (user_id,))
    row = db_cursor.fetchone()
    return dict(row) if row else None

