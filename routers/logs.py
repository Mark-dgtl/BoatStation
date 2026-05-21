from fastapi import APIRouter, Depends, HTTPException, status, Request, Cookie
from fastapi.responses import StreamingResponse
import logging_config
import asyncio
import json
import logging

router = APIRouter()

# --- НЕОБХОДИМО: Настроить loguru или другой логгер для записи в общий буфер ---
# Пока используем стандартный logging Python и файловый обработчик.
# Создадим обработчик, который будет писать в файл и читать из него для SSE.

# Только наш логгер — не root, иначе в файл попадает и watchfiles/uvicorn reload
file_handler = logging.FileHandler("logs/service.log")
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)
service_logger = logging.getLogger("boat_station.service")
service_logger.setLevel(logging.INFO)
if not service_logger.handlers:
    service_logger.addHandler(file_handler)
service_logger.propagate = False

# --- ФУНКЦИЯ ДЛЯ ЧТЕНИЯ ЛОГОВ ИЗ ФАЙЛА ---
def tail_log_file(filename, n_lines=10):
    """Читает последние n строк из файла лога."""
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    return lines[-n_lines:]

@router.get("/stream")
async def stream_logs(current_user_id: int = Cookie(None), user_role: str = Cookie(None)):
    if user_role != "owner":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated as superadmin")

    async def event_generator():
        # Читаем последние строки при подключении
        initial_logs = tail_log_file("logs/service.log", 10)
        for log_line in initial_logs:
            yield f"data: {json.dumps({'time': 'N/A', 'level': 'LOG', 'message': log_line.strip(), 'source': 'file'})}\n\n"

        # Запоминаем позицию в файле
        with open("logs/service.log", 'r', encoding='utf-8') as f:
            f.seek(0, 2) # Перейти в конец файла
            while True:
                line = f.readline()
                if line:
                    # Простая обработка строки лога (может потребоваться регулярное выражение для парсинга)
                    # Формат: 2024-05-06 15:00:00,000 - INFO - Some message
                    parts = line.strip().split(' - ', 2)
                    if len(parts) >= 3:
                        timestamp, level, message = parts[0], parts[1], parts[2]
                        log_entry = {"time": timestamp, "level": level, "message": message, "source": "file"}
                    else:
                        log_entry = {"time": "N/A", "level": "UNKNOWN", "message": line.strip(), "source": "file"}

                    yield f"data: {json.dumps(log_entry)}\n\n"
                else:
                    await asyncio.sleep(1) # Ждем новую строку

    # Используем text/plain для SSE (или application/json)
    return StreamingResponse(event_generator(), media_type="text/plain")


# --- ФУНКЦИЯ ДЛЯ ЛОГИРОВАНИЯ В КОНСОЛЬ PYTHON И ФАЙЛ ---
def log_api_call(user_id: int, endpoint: str, method: str):
    """Функция для логирования вызова API."""
    service_logger.info(f"User {user_id}, Method {method}, Endpoint {endpoint}")

# --- ПРИМЕР ИСПОЛЬЗОВАНИЯ В MIDDLEWARE main.py ---
# from fastapi import Request
# import datetime
#
# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     start_time = datetime.datetime.now()
#     response = await call_next(request)
#     process_time = (datetime.datetime.now() - start_time).total_seconds()
#     user_id = request.cookies.get("user_id", "Anonymous")
#     log_api_call(user_id, request.url.path, request.method)
#     return response
#
# @app.exception_handler(Exception)
# async def global_exception_handler(request: Request, exc: Exception):
#     logging.error(f"Unhandled exception: {exc}", exc_info=True)
#     logging.error(f"URL: {request.url}")
#     logging.error(f"Method: {request.method}")
#     return {"detail": "Internal Server Error"}
