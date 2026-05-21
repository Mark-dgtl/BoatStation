from fastapi import APIRouter, Query, Depends, HTTPException, status, Request, Cookie, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import auth, schemas, crud
from models import RentCreate
import logging
from typing import Optional

router = APIRouter()

templates = Jinja2Templates(directory="./templates")

logger = logging.getLogger(__name__)

def get_current_admin(request: Request, user_id: int = Cookie(None), user_role: str = Cookie(None)):
    if not user_id or user_role not in ["admin", "owner"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated as admin")
    return int(user_id)


@router.get("/dashboard")
async def admin_dashboard(current_user_id: int = Depends(get_current_admin)):
    return RedirectResponse(url="/api/admin/rentals", status_code=status.HTTP_302_FOUND)

@router.get("/rentals")
async def admin_rentals(request: Request, current_user_id: int = Depends(get_current_admin)):
    stats = crud.get_admin_dashboard_stats()
    pending_requests = crud.get_pending_rental_requests()
    active_rentals = crud.get_active_rentals()

    with crud.db_query() as query:
        clients = crud.get_all_clients_for_form(query)
        vessels = crud.get_all_vessels(query)
        water_bodies = crud.get_all_water_bodies(query)
        instructions = crud.get_all_instructions(query)
        instructors = crud.get_instructors_with_pending_load(query)
        user_info = crud.get_user_by_id(query, current_user_id)

    return templates.TemplateResponse("admin/rentals.html", {
        "request": request,
        "stats": stats,
        "pending_requests": pending_requests,
        "active_rentals": active_rentals,
        "clients": clients,
        "vessels": vessels,
        "water_bodies": water_bodies,
        "instructions": instructions,
        "instructors": instructors,
        "user": user_info
    })


@router.get("/vessels")
async def admin_vessels(request: Request, current_user_id: int = Depends(get_current_admin)):
    with crud.db_query() as query:
        all_vessels = crud.get_all_vessels(query)

        vessels_by_status = {}
        vessels_by_status['all'] = all_vessels

        # СТРОГО как в твоей таблице type_status_vessel:
        target_statuses = ['Свободен', 'В прокате', 'На ремонте', 'Резерв']

        for status_name in target_statuses:
            # Фильтруем список
            vessels_by_status[status_name] = [
                v for v in all_vessels if v.get('status_name') == status_name
            ]

    with crud.db_query() as query:
        user_info = crud.get_user_by_id(query, current_user_id)

    return templates.TemplateResponse("admin/vessels.html", {
        "request": request,
        "vessels_by_status": vessels_by_status,
        "user": user_info
    })


@router.put("/requests/{request_id}/assign_instructor")
async def admin_assign_instructor_to_request(
    request_id: int,
    body: dict,
    current_user_id: int = Depends(get_current_admin),
):
    instructor_id = body.get("instructor_id")
    if not instructor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="instructor_id is required")

    request_obj = crud.get_rental_request_by_id(request_id)
    if not request_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if request_obj["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Instructor can only be assigned to pending requests",
        )

    assigned = crud.assign_instructor_to_request(request_id, int(instructor_id))
    if not assigned:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to assign instructor")

    return {"msg": "Инструктор назначен", "instructor_id": assigned}


@router.put("/requests/{request_id}/status")
async def admin_update_request_status(
    request_id: int,
    update_: schemas.RentalRequestUpdate,
    current_user_id: int = Depends(get_current_admin)
):
    request_obj = crud.get_rental_request_by_id(request_id)
    if not request_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if update_.status == "approved":
        if request_obj["status"] != "instructor_confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Сначала инструктор должен подтвердить проведение инструктажа.",
            )

        instr_id = request_obj.get("instruction_id")
        if not instr_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Назначьте инструктора заявке.",
            )
        instruction = crud.get_instruction_by_id(instr_id)
        if not instruction:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction not found.")
        if not instruction.get("time_conducted"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Инструктаж ещё не отмечен как проведённый.",
            )

        if crud.client_has_active_rental(request_obj["client_id"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="У клиента уже есть активная аренда. Сначала оформите возврат плавсредства.",
            )

        # Аренду создаёт триггер approve_request_trigger при смене status на approved.
        updated_request = crud.update_rental_request_status(request_id, "approved", update_.admin_comment)
        if not updated_request:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update request status after approval.",
            )

        new_rent = crud.get_rent_by_request_id(request_id)
        if not new_rent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Заявка утверждена, но аренда не создана триггером БД.",
            )

        return {"msg": "Заявка утверждена, аренда создана", "request": updated_request, "rental": new_rent}

    elif request_obj['status'] in ('pending', 'instructor_confirmed') and update_.status in ['rejected', 'cancelled']:
        updated_request = crud.update_rental_request_status(request_id, update_.status, update_.admin_comment)
        if not updated_request:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update request status")
        return {"msg": "Request status updated successfully", "request": updated_request}

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot perform this action on the current request status.")


@router.get("/vessels/{vessel_id}")
async def get_edit_vessel_form(
        request: Request,
        vessel_id: int,
        current_user_id: int = Depends(get_current_admin)
):
    """
    Отображает форму редактирования плавсредства.
    """
    with crud.db_query() as query:
        vessel = crud.get_vessel_by_id(query, vessel_id)
        if not vessel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Плавсредство не найдено")

        vessel_types = crud.get_all_vessel_types(query)
        vessel_statuses = crud.get_all_vessel_statuses(query)
        user_info = crud.get_user_by_id(query, current_user_id)

    return templates.TemplateResponse("admin/edit_vessel.html", {
        "request": request,
        "vessel": vessel,
        "vessel_types": vessel_types,
        "vessel_statuses": vessel_statuses,
        "user": user_info
    })


@router.put("/vessels/{vessel_id}")
async def update_vessel(
        vessel_id: int,
        data: dict,
        current_user_id: int = Depends(get_current_admin)
):
    """
    Обрабатывает обновление информации о плавсредстве.
    """
    with crud.db_query() as query:
        try:
            # Проверяем обязательные поля
            required_fields = ['name', 'number', 'type_vessel_id', 'current_status_id']
            for field in required_fields:
                if field not in data:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Отсутствует обязательное поле: {field}"
                    )

            # Обновляем плавсредство
            updated_vessel = crud.update_vessel(query, vessel_id, data)
            if not updated_vessel:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Плавсредство не найдено или не было изменено"
                )

            # Логируем изменение
            logger.info(f"Admin {current_user_id} updated vessel {vessel_id}")

            return {
                "msg": "Плавсредство успешно обновлено",
                "vessel": updated_vessel
            }

        except ValueError as e:
            # Обработка ошибок валидации (например, дубликат номера)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error updating vessel {vessel_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при обновлении плавсредства"
            )





@router.get("/create_rental_manual")
async def get_create_rental_manual_form(
    request: Request,
    current_user_id: int = Depends(get_current_admin)
):
    with crud.db_query() as query:
        clients = crud.get_all_clients_for_form(query)
        vessels = crud.get_all_vessels(query)
        water_bodies = crud.get_all_water_bodies(query)
        instructions = crud.get_all_instructions(query)
        user_info = crud.get_user_by_id(query, current_user_id)

    return templates.TemplateResponse("admin/create_rental.html", {
        "request": request,
        "clients": clients,
        "vessels": vessels,
        "water_bodies": water_bodies,
        "instructions": instructions,
        "user": user_info
    })



@router.get("/search_clients")
async def search_clients(
    query: str = Query(default="", min_length=0), # Позволим пустой запрос для получения всех
    current_user_id: int = Depends(get_current_admin)
):
    """
    Эндпоинт для поиска клиентов. Возвращает JSON.
    """
    with crud.db_query() as query:
        # Ищем по фамилии или логину (или оба)
        # Используем LOWER для регистронезависимого поиска
        # '%' || %s || '%' в psycopg2 нужно экранировать как %s
        search_pattern = f"%{query}%"
        query.execute("""
            SELECT c.id, c.surname, u.login
            FROM Client c
            JOIN Users u ON c.user_id = u.id
            WHERE LOWER(c.surname) LIKE LOWER(%s) OR LOWER(u.login) LIKE LOWER(%s)
            ORDER BY c.surname, u.login
            LIMIT 10; -- Ограничиваем количество результатов
        """, (search_pattern, search_pattern))
        clients = query.fetchall()

    # Возвращаем список словарей
    return [{"id": c["id"], "surname": c["surname"], "login": c["login"]} for c in clients]



# --- ЭНДПОИНТ 2: ОБРАБОТКА ФОРМЫ (POST) ---
@router.post("/create_rental_manual")
async def post_create_rental_manual(
        data: dict,
        current_user_id: int = Depends(get_current_admin)
):
    try:
        start_time = crud.parse_naive_datetime(data["start_time"])

        return_time = None
        raw_return = (data.get("return_time") or "").strip()
        if raw_return:
            return_time = crud.parse_naive_datetime(raw_return)
            if return_time <= start_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Время возврата должно быть позже времени начала. Для текущей аренды поле возврата оставьте пустым.",
                )

        client_id = int(data["client_id"])
        if return_time is None and crud.client_has_active_rental(client_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="У клиента уже есть активная аренда. Сначала оформите возврат.",
            )

        rent_data = RentCreate(
            client_id=client_id,
            instruction_id=int(data["instruction_id"]),
            vessel_id=int(data["vessel_id"]),
            water_body_id=int(data["water_body_id"]),
            start_time=start_time,
            return_time=return_time,
        )

        new_rent = crud.create_rent(rent_data)

        if not new_rent:
            # Если вернулся None, значит в crud.py сработал except
            raise HTTPException(status_code=500, detail="Ошибка БД: Проверьте консоль сервера")

        return {"msg": "Аренда успешно создана!", "rental": new_rent}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Ошибка данных (числа или даты): {e}")
    except Exception as e:
        logger.error(f"Error creating manual rental: {e}")
        # Выводим саму ошибку в detail, чтобы увидеть её в alert браузера
        raise HTTPException(status_code=500, detail=str(e))


# --- НОВЫЕ ЭНДПОИНТЫ ДЛЯ ШАБЛОНОВ ---
@router.get("/get_clients")
async def get_clients_for_admin(current_user_id: int = Depends(get_current_admin)):
    with crud.db_query() as query:
        # Получаем клиентов через представление или напрямую
        query.execute("""
            SELECT c.id, c.surname, u.login
            FROM Client c
            JOIN Users u ON c.user_id = u.id;
        """)
        clients = query.fetchall()
        return [dict(row) for row in clients]

@router.get("/get_vessels")
async def get_vessels_for_admin(current_user_id: int = Depends(get_current_admin)):
    with crud.db_query() as query:
        vessels = crud.get_all_vessels(query)
        return vessels

@router.get("/get_water_bodies")
async def get_water_bodies_for_admin(current_user_id: int = Depends(get_current_admin)):
    with crud.db_query() as query:
        water_bodies = crud.get_all_water_bodies(query)
        return water_bodies

@router.get("/get_conducted_instructions")
async def get_conducted_instructions_for_admin(current_user_id: int = Depends(get_current_admin)):
    with crud.db_query() as query:
        # Получаем инструктажи, которые уже проведены (time_conducted не NULL)
        query.execute("""
            SELECT i.*, ins.surname as instructor_surname, ti.name as instruction_type_name
            FROM Instruction i
            JOIN Instructor ins ON i.instructor_id = ins.id
            JOIN Type_instruction ti ON i.type_instruction_id = ti.id
            WHERE i.time_conducted IS NOT NULL;
        """)
        instructions = query.fetchall()
        return [dict(row) for row in instructions]

# Эндпоинт для отметки возврата (предположим, что он принимает ID аренды и время возврата)
@router.put("/mark_rental_returned/{rental_id}")
async def mark_rental_returned(
    rental_id: int,
    return_time_data: dict, # Pydantic модель для времени возврата, например, {"return_time": "YYYY-MM-DD HH:MM:SS"}
    current_user_id: int = Depends(get_current_admin)
):
    return_time_str = return_time_data.get("return_time")
    if not return_time_str:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Return time is required.")

    try:
        from datetime import datetime
        return_time = datetime.strptime(return_time_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid return time format. Expected YYYY-MM-DD HH:MM:SS.")

    updated_rental = crud.update_rent_return_time(rental_id, return_time)
    if not updated_rental:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rental not found or already returned.")

    return {"msg": "Rental marked as returned successfully", "rental": updated_rental}


@router.get("/repairs")
async def admin_repairs(
        request: Request,
        current_user_id: int = Depends(get_current_admin)
):
    """
    Отображает журнал ремонтов (технического состояния плавсредств).
    """
    with crud.db_query() as query:
        # Получаем журнал технического состояния с информацией о плавсредствах
        repair_logs = crud.get_repair_logs(query)
        user_info = crud.get_user_by_id(query, current_user_id)

    return templates.TemplateResponse("admin/repairs.html", {
        "request": request,
        "repair_logs": repair_logs,
        "user": user_info
    })


@router.get("/get_vessels")
async def get_vessels_for_admin(
        current_user_id: int = Depends(get_current_admin)
):
    with crud.db_query() as query:
        vessels = crud.get_all_vessels(query)
        return vessels


@router.get("/get_condition_types")
async def get_condition_types(
        current_user_id: int = Depends(get_current_admin)
):
    with crud.db_query() as query:
        # Получаем типы технического состояния
        query.execute("SELECT id, name FROM Type_tech_condition ORDER BY name;")
        condition_types = [dict(row) for row in query.fetchall()]
        return condition_types


@router.post("/add_condition_log")
async def add_condition_log(
        data: dict,
        current_user_id: int = Depends(get_current_admin)
):
    """
    Добавляет новую запись в журнал технического состояния.
    """
    # Проверяем обязательные поля
    required_fields = ['vessel_id', 'type_condition_id']
    for field in required_fields:
        if field not in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Отсутствует обязательное поле: {field}"
            )

    with crud.db_query() as query:
        try:
            # Добавляем запись
            query.execute("""
                INSERT INTO Tech_condition_log (vessel_id, type_condition_id)
                VALUES (%s, %s)
                RETURNING id;
            """, (data['vessel_id'], data['type_condition_id']))

            log_id = query.fetchone()['id']

            # Обновляем статус плавсредства на "На ремонте" (если нужно)
            # Получаем ID статуса "На ремонте"
            query.execute("SELECT id FROM Type_status_vessel WHERE name = 'На ремонте';")
            repair_status_id = query.fetchone()['id']

            # Обновляем статус плавсредства
            query.execute("""
                UPDATE Vessel
                SET current_status_id = %s
                WHERE id = %s;
            """, (repair_status_id, data['vessel_id']))

            return {
                "msg": "Запись о техническом состоянии добавлена успешно",
                "log_id": log_id
            }

        except Exception as e:
            logger.error(f"Error adding condition log: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при добавлении записи о техническом состоянии"
            )


# ... существующий код ...

# Эндпоинты для получения типов и статусов плавсредств
@router.get("/get_vessel_types")
async def get_vessel_types(
        current_user_id: int = Depends(get_current_admin)
):
    with crud.db_query() as query:
        vessel_types = crud.get_all_vessel_types(query)
        return vessel_types


@router.get("/get_vessel_statuses")
async def get_vessel_statuses(
        current_user_id: int = Depends(get_current_admin)
):
    with crud.db_query() as query:
        vessel_statuses = crud.get_all_vessel_statuses(query)
        return vessel_statuses


# Эндпоинт для создания нового плавсредства
@router.post("/vessels")
async def create_vessel(
        data: dict,
        current_user_id: int = Depends(get_current_admin)
):
    """
    Создает новое плавсредство.
    """
    # Проверка обязательных полей
    required_fields = ['name', 'number', 'type_vessel_id', 'current_status_id']
    for field in required_fields:
        if field not in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Отсутствует обязательное поле: {field}"
            )

    with crud.db_query() as query:
        try:
            # Создаем новое плавсредство
            new_vessel = crud.create_vessel(query, data)
            if not new_vessel:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось создать плавсредство"
                )

            # Логируем создание
            logger.info(f"Admin {current_user_id} created new vessel {new_vessel['id']}")

            return {
                "msg": "Плавсредство успешно добавлено",
                "vessel": new_vessel
            }

        except ValueError as e:
            # Обработка ошибок валидации (например, дубликат номера)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error creating vessel: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при добавлении плавсредства"
            )


@router.get("/vessels/check_number")
async def check_vessel_number(
        number: str,
        current_user_id: int = Depends(get_current_admin)
):
    """
    Проверяет, доступен ли номер плавсредства.
    """
    with crud.db_query() as query:
        query.execute("SELECT id FROM Vessel WHERE number = %s;", (number,))
        exists = query.fetchone() is not None

    return {"available": not exists}