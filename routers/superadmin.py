from fastapi import APIRouter, Depends, HTTPException, status, Request, Cookie
from fastapi.templating import Jinja2Templates
from sqlalchemy.dialects.postgresql import psycopg2

import auth, schemas, crud
import logging

router = APIRouter()

templates = Jinja2Templates(directory="./templates")

logger = logging.getLogger(__name__)

def get_current_superadmin(request: Request, user_id: int = Cookie(None), user_role: str = Cookie(None)):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    # Разрешаем владельцу (owner) И админам с role_id = 4
    if user_role != "owner" and user_role != 4:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return int(user_id)

@router.get("/dashboard")
async def superadmin_dashboard(request: Request, current_user_id: int = Depends(get_current_superadmin)):
    stats = crud.get_superadmin_dashboard_stats()
    with crud.db_query() as query:
        user_info = crud.get_user_by_id(query, current_user_id)
    return templates.TemplateResponse("superadmin/dashboard.html", {
        "request": request,
        "stats": stats,
        "user": user_info
    })

@router.get("/crud")
async def superadmin_crud(request: Request, current_user_id: int = Depends(get_current_superadmin)):
    allowed_tables = crud.get_allowed_tables_for_crud()
    with crud.db_query() as query:
        user_info = crud.get_user_by_id(query, current_user_id)
    return templates.TemplateResponse("superadmin/crud.html", {"request": request, "tables": allowed_tables, "user": user_info})

@router.get("/logs")
async def superadmin_logs(request: Request, current_user_id: int = Depends(get_current_superadmin)):
    with crud.db_query() as query:
        user_info = crud.get_user_by_id(query, current_user_id)
    return templates.TemplateResponse("superadmin/logs.html", {"request": request, "user": user_info})

# --- УНИВЕРСАЛЬНЫЙ CRUD ---
@router.post("/crud/read/{table_name}")
async def crud_read(
    table_name: str,
    filters: dict = None,
    current_user_id: int = Depends(get_current_superadmin)
):
    try:
        data = crud.read_table_data(table_name, filters)
        return {"data": data}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except psycopg2.Error as e:
        logger.error(f"Database error during CRUD read: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during read operation.")

@router.post("/crud/create/{table_name}")
async def crud_create(
    table_name: str,
    record: dict,
    current_user_id: int = Depends(get_current_superadmin)
):
    allowed_tables = crud.get_allowed_tables_for_crud()
    if table_name.lower() not in allowed_tables:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access to table '{table_name}' is forbidden.")

    import re
    for key in record.keys():
        if not re.match(r'^[a-zA-Z0-9_]+$', key):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid column name: {key}")

    columns = ', '.join(record.keys())
    placeholders = ', '.join(['%s'] * len(record))
    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) RETURNING *;"

    with crud.db_query() as query:
        try:
            query.execute(sql, list(record.values()))
            new_record = query.fetchone()
            logger.info(f"Superadmin {current_user_id} created record in {table_name}.")
            return {"msg": "Record created successfully", "record": dict(new_record)}
        except psycopg2.Error as e:
            logger.error(f"Database error during CRUD create: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during create operation.")

@router.put("/crud/update/{table_name}/{record_id}")
async def crud_update(
    table_name: str,
    record_id: int,
    updates: dict,
    current_user_id: int = Depends(get_current_superadmin)
):
    allowed_tables = crud.get_allowed_tables_for_crud()
    if table_name.lower() not in allowed_tables:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access to table '{table_name}' is forbidden.")

    import re
    for key in updates.keys():
        if not re.match(r'^[a-zA-Z0-9_]+$', key):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid column name: {key}")

    set_clause = ', '.join([f"{key} = %s" for key in updates.keys()])
    sql = f"UPDATE {table_name} SET {set_clause} WHERE id = %s RETURNING *;"

    with crud.db_query() as query:
        try:
            query.execute(sql, list(updates.values()) + [record_id])
            updated_record = query.fetchone()
            if not updated_record:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
            logger.info(f"Superadmin {current_user_id} updated record {record_id} in {table_name}.")
            return {"msg": "Record updated successfully", "record": dict(updated_record)}
        except psycopg2.Error as e:
            logger.error(f"Database error during CRUD update: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during update operation.")

@router.delete("/crud/delete/{table_name}/{record_id}")
async def crud_delete(
    table_name: str,
    record_id: int,
    current_user_id: int = Depends(get_current_superadmin)
):
    allowed_tables = crud.get_allowed_tables_for_crud()
    if table_name.lower() not in allowed_tables:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access to table '{table_name}' is forbidden.")

    sql = f"DELETE FROM {table_name} WHERE id = %s RETURNING id;"

    with crud.db_query() as query:
        try:
            query.execute(sql, [record_id])
            deleted_record = query.fetchone()
            if not deleted_record:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
            logger.info(f"Superadmin {current_user_id} deleted record {deleted_record['id']} from {table_name}.")
            return {"msg": "Record deleted successfully", "deleted_id": deleted_record['id']}
        except psycopg2.Error as e:
            logger.error(f"Database error during CRUD delete: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during delete operation.")

# ... (остальные эндпоинты суперадмина, например, управление пользователями) ...
# Эндпоинты для управления пользователями (получение списка, деталей, обновление, удаление)
@router.get("/users")
async def get_all_users(current_user_id: int = Depends(get_current_superadmin)):
    with crud.db_query() as query:
        users = crud.get_all_users(query)
        return {"users": users}

# Эндпоинт для получения деталей конкретного пользователя
# Принимает user_id как ПАРАМЕТР ПУТИ
# Проверяет аутентификацию с помощью Depends
@router.get("/users/{target_user_id}") # <-- Имя параметра в пути: target_user_id
async def get_user_details(
    target_user_id: int, # <-- Принимаем параметр из пути как target_user_id
    current_user_id: int = Depends(get_current_superadmin) # <-- Проверяем аутентификацию и получаем ID текущего юзера
):
    # current_user_id - это ID вошедшего суперадмина (из куки)
    # target_user_id - это ID пользователя, чьи детали запрашиваются (из URL)
    with crud.db_query() as query:
        details = crud.get_user_details(query, target_user_id) # Передаем ID цели
        if not details:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return {"details": details}

# Эндпоинт для обновления роли пользователя
@router.put("/users/{target_user_id}/role") # <-- Имя параметра в пути: target_user_id
async def update_user_role_endpoint(
    target_user_id: int, # <-- Принимаем ID цели из пути
    role_: dict, # Pydantic модель? Пока dict. {"new_role_name": "admin"}
    current_user_id: int = Depends(get_current_superadmin) # <-- Проверяем аутентификацию
):
    new_role_name = role_data.get("new_role_name")
    if not new_role_name:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New role name is required.")
    with crud.db_query() as query:
        try:
            crud.update_user_role(query, target_user_id, new_role_name) # Передаем ID цели
            logger.info(f"Superadmin {current_user_id} updated role of user {target_user_id} to {new_role_name}.")
            return {"msg": f"Role of user {target_user_id} updated to {new_role_name} successfully."}
        except ValueError as e: # Raised if role doesn't exist
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# Эндпоинт для удаления пользователя
@router.delete("/users/{target_user_id}") # <-- Имя параметра в пути: target_user_id
async def delete_user_endpoint(
    target_user_id: int, # <-- Принимаем ID цели из пути
    current_user_id: int = Depends(get_current_superadmin) # <-- Проверяем аутентификацию
):
    with crud.db_query() as query:
        try:
            crud.delete_user(query, target_user_id) # Передаем ID цели
            logger.info(f"Superadmin {current_user_id} deleted user {target_user_id}.")
            return {"msg": f"User {target_user_id} deleted successfully."}
        except ValueError as e: # Raised if dependencies exist
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))