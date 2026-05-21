import logging
from loguru import logger
import sys

# Удаляем стандартный обработчик
logging.getLogger("uvicorn").handlers.clear()
logging.getLogger("uvicorn.access").handlers.clear()

# Конфигурируем loguru
logger.remove() # Удаляем стандартный обработчик loguru
logger.add(sys.stdout, level="INFO", format="<green>{time}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
logger.add("logs/api.log", rotation="10 MB", retention="10 days", level="DEBUG", format="{time} | {level} | {name}:{function}:{line} - {message}")

# Middleware для логирования запросов и ошибок
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"{request.method} {request.url.path} - Status: {response.status_code} - Process Time: {process_time:.4f}s")
        return response