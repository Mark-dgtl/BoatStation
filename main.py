from typing import List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import crud
import logging_config
from routers import auth as auth_router, client as client_router, instructor as instructor_router, admin as admin_router, superadmin as superadmin_router, logs as logs_router
from logging_config import logger
import datetime # Для логирования времени

app = FastAPI(title="Лодочная станция API (SQL Only)")


@app.get("/get_water")
async def get_water():
    with crud.db_query() as query:
        water_bodies = crud.get_all_water_bodies(query)
    return {"water_bodies": water_bodies}


@app.get("/get_vessels_for_water_body/{water_body_id}")
async def get_vessels_for_water_body(water_body_id: int):
    try:
        # Вызываем твой CRUD
        vessels = crud.get_available_vessels_for_water_body(water_body_id)

        # Печатаем в консоль сервера для отладки
        print(f"DEBUG: Водоем ID {water_body_id}, Найдено судов: {len(vessels)}")

        return {"vessels": vessels}
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# Подключаем middleware для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.datetime.now()
    response = await call_next(request)
    process_time = (datetime.datetime.now() - start_time).total_seconds()
    # Пытаемся получить user_id из cookie
    user_id = request.cookies.get("user_id", "Anonymous")
    logger.info(f"{request.method} {request.url.path} - Status: {response.status_code} - Process Time: {process_time:.4f}s - User: {user_id}")
    return response

# Подключаем middleware для логирования ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    logger.error(f"URL: {request.url}")
    logger.error(f"Method: {request.method}")
    logger.opt(exception=True).error("Full traceback:")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключаем шаблоны
templates = Jinja2Templates(directory="./templates")

# Подключаем роутеры
app.include_router(auth_router.router, prefix="/api/auth", tags=["authentication"])
app.include_router(client_router.router, prefix="/api/client", tags=["client"])
app.include_router(instructor_router.router, prefix="/api/instructor", tags=["instructor"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["admin"])
app.include_router(superadmin_router.router, prefix="/api/superadmin", tags=["superadmin"])
app.include_router(logs_router.router, prefix="/api/logs", tags=["logs"]) # Предположим, он тоже подключен

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        # Иначе watchfiles видит запись в logs/*.log и пишет «1 change detected» бесконечно
        reload_excludes=["logs/*", "*.log", ".git/*", "__pycache__/*", ".venv/*"],
    )