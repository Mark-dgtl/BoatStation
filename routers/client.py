from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request, Cookie
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import auth, schemas, utils, crud # Импортируем crud вместо db сессии
from models import RentalRequestCreate
import logging

router = APIRouter()

templates = Jinja2Templates(directory="./templates")

logger = logging.getLogger(__name__)

def get_current_client(request: Request, user_id: int = Cookie(None), user_role: str = Cookie(None)):
    if not user_id or user_role != "client":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated as client")
    return int(user_id) # Возвращаем ID как int

@router.get("/dashboard")
async def client_dashboard(current_user_id: int = Depends(get_current_client)):
    return RedirectResponse(url="/api/client/profile", status_code=status.HTTP_302_FOUND)

@router.get("/profile")
async def client_profile(request: Request, current_user_id: int = Depends(get_current_client)):
    client_info = crud.get_client_by_user_id(current_user_id)
    if not client_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return templates.TemplateResponse("client/profile.html", {"request": request, "client": client_info})

@router.put("/profile")
async def update_client_profile(
    request: Request,
    current_user_id: int = Depends(get_current_client)
):
    data = await request.json()
    # Валидация через Pydantic не обязательна, но желательна
    # validated_data = UserUpdateProfile(**data) # Если создать такую схему
    updated_client = crud.update_client_profile(current_user_id, data)
    if not updated_client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found or update failed")
    return {"msg": "Profile updated successfully", "client": updated_client}

@router.get("/rentals")
async def client_rentals(request: Request, current_user_id: int = Depends(get_current_client)):
    client_info = crud.get_client_by_user_id(current_user_id)
    client_data = crud.get_client_by_user_id(current_user_id)
    if not client_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    history = crud.get_rental_history_by_client_id(client_info['id']) # Передаем ID клиента
    current = crud.get_current_rental_by_client_id(client_info['id'])
    upcoming_requests = crud.get_pending_requests_by_client_id(client_info['id'])
    return templates.TemplateResponse("client/rentals.html", {
        "request": request,
        "history": history,
        "client": client_data,
        "current": current,
        "upcoming_requests": upcoming_requests
    })


@router.get("/vessels")
async def client_vessels_list(request: Request, current_user_id: int = Depends(get_current_client)):
    with crud.db_query() as query:
        # 1. Получаем объект клиента из БД по его ID
        client_data = crud.get_client_by_user_id(current_user_id)  # или ваше точное название функции, например get_user_by_id

        vessels_with_equipment = crud.get_vessels_with_equipment()
        allowed_by_type = crud.get_allowed_water_bodies_by_vessel_type(query)
        for vessel in vessels_with_equipment:
            vessel["allowed_water_bodies"] = allowed_by_type.get(vessel["type_name"], [])

        type_counts: dict = {}
        for vessel in vessels_with_equipment:
            type_counts[vessel["type_name"]] = type_counts.get(vessel["type_name"], 0) + 1
        vessel_types = sorted(type_counts.keys())

        return templates.TemplateResponse("client/vessels.html", {
            "request": request,
            "client": client_data,
            "vessels": vessels_with_equipment,
            "allowed_water_bodies_by_type": allowed_by_type,
            "vessel_types": vessel_types,
            "vessel_type_counts": type_counts,
        })


@router.get("/water_bodies")
async def client_water_bodies_list(request: Request, current_user_id: int = Depends(get_current_client)):
    with crud.db_query() as query:
        # 2. Аналогично получаем объект клиента для страницы водоемов
        client_data = crud.get_client_by_user_id(current_user_id)

        water_bodies, wb_categories = crud.get_water_bodies_for_client_page(query)

        return templates.TemplateResponse("client/water_bodies.html", {
            "request": request,
            "client": client_data,
            "water_bodies": water_bodies,
            "wb_categories": wb_categories,
        })


@router.get("/get_vessels_for_water_body/{water_body_id}")
async def get_vessels_for_water_body(water_body_id: int, current_user_id: int = Depends(get_current_client)):
    with crud.db_query() as query:
        # Проверка аутентификации не нужна, так как роут защищен
        vessels = crud.get_available_vessels_for_water_body(water_body_id)
    # Возвращаем только плавсредства
    return {"vessels": vessels}


def _naive_datetime(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


@router.post("/request_rental")
async def client_create_rental_request(
    request_: RentalRequestCreate, # Pydantic модель валидирует
    current_user_id: int = Depends(get_current_client)
):
    desired_start = _naive_datetime(request_.desired_start)
    desired_end = _naive_datetime(request_.desired_end)

    client_info = crud.get_client_by_user_id(current_user_id)
    if not client_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    if desired_end <= desired_start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time.")
    duration_hours = (desired_end - desired_start).total_seconds() / 3600
    if duration_hours > 24:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum rental duration is 24 hours.")

    if crud.client_period_conflicts_with_active_rental(client_info['id'], desired_start, desired_end):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Выбранное время пересекается с текущей арендой. Выберите период после её окончания.",
        )

    if not crud.check_vessel_availability(request_.vessel_id, desired_start, desired_end):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Плавсредство занято в выбранное время.",
        )

    if not crud.is_vessel_water_body_allowed(request_.vessel_id, request_.water_body_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для этого типа плавсредства выбранный водоём недоступен. Выберите водоём из списка разрешённых.",
        )

    # Создаем заявку
    new_request = crud.create_rental_request(client_info['id'], request_.vessel_id, request_.water_body_id, desired_start, desired_end)
    if not new_request:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create rental request")

    return {
        "msg": "Заявка создана. Администратор назначит инструктора — после этого она появится у него в списке.",
        "request": new_request,
    }

@router.post("/get_available_hours")
async def get_available_hours_for_date(
    request: Request,
    current_user_id: int = Depends(get_current_client)
):
    data = await request.json()
    vessel_id = data.get("vessel_id")
    date_str = data.get("date") # Формат YYYY-MM-DD

    if not vessel_id or not date_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vessel ID and Date are required.")

    rentals_on_date = crud.get_rentals_by_vessel_and_date(vessel_id, date_str)

    available_hours = []
    booked_hours = set()
    for rental in rentals_on_date:
        start_hour = rental['start_time'].hour
        # Включаем час начала, исключаем час окончания (если не совпадает)
        end_hour = rental['return_time'].hour if rental['return_time'] else start_hour + 1
        for h in range(start_hour, end_hour):
            booked_hours.add(h)

    for hour in range(9, 18): # С 9 утра до 6 вечера
        if hour not in booked_hours:
            available_hours.append(f"{hour:02d}:00 - {hour+1:02d}:00")

    return {"available_hours": available_hours}

@router.get("/get_vessels_for_water_body/{water_body_id}")
async def get_vessels_for_water_body(water_body_id: int):

    vessels = crud.get_available_vessels_for_water_body(water_body_id)
    return {"vessels": vessels}