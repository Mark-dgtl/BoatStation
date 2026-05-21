from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

import auth, schemas, crud
from models import UserRegister # Pydantic модель для регистрации

router = APIRouter()

templates = Jinja2Templates(directory="./templates")


from fastapi.responses import RedirectResponse

@router.get("/logout")
async def logout_user(request: Request):
    """
    Эндпоинт для выхода из системы.
    Удаляет куки 'user_id' и 'user_role', затем редиректит на главную страницу.
    """
    # Создаем пустой Response (или RedirectResponse)
    response = RedirectResponse(url="/") # Редирект на главную

    # Удаляем куки, установив их значение в пустую строку и срок действия в прошлое
    response.delete_cookie(key="user_id")
    response.delete_cookie(key="user_role")

    # Опционально: можно добавить сообщение об успешном выходе в flash-сообщение,
    # но для простоты просто редиректим.

    # logger.info(f"User logged out from IP: {request.client.host}") # Логируем выход

    return response
@router.post("/login")  # response_class тут можно не указывать явно, если возвращаете объект
async def login_user(
        login: str = Form(...),
        password: str = Form(...)
):
    user = crud.authenticate_user(login, password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect login or password")

    # Определяем путь в зависимости от роли
    if user['role_name'] == "client":
        redirect_url = "/api/client/profile"
    elif user['role_name'] == "instructor":
        redirect_url = "/api/instructor/dashboard"
    elif user['role_name'] == "admin":
        redirect_url = "/api/admin/rentals"
    elif user['role_name'] == "owner":
        redirect_url = "/api/superadmin/dashboard"
    elif user['role_name'] not in ["client", "instructor", "admin", "owner"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Создаем редирект со статусом 303 (See Other) — это стандарт для POST-запросов
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    # Устанавливаем куки
    response.set_cookie(key="user_id", value=str(user['id']), httponly=True)
    response.set_cookie(key="user_role", value=user['role_name'], httponly=True)


    return response



from fastapi import Request # Добавить импорт

@router.post("/register", response_class=RedirectResponse)
async def register_user(request: Request):
    # Получаем данные формы как словарь
    form_data = await request.form()
    user_data_dict = dict(form_data)

    # Создаем объект Pydantic модели для валидации
    try:
        user_data = UserRegister(**user_data_dict)
    except ValidationError as e: # Импортируйте ValidationError из pydantic
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors())

    # Теперь используем user_data для дальнейшей обработки
    # ... (валидация, создание пользователя в БД и т.д.) ...
    # Ваш код из crud.create_client_and_user(user_data)
    existing_user = crud.get_user_by_login(user_data.login)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    new_client = crud.create_client_and_user(user_data)
    if not new_client:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

    # Автоматический вход после регистрации (как в вашем коде)
    from fastapi.responses import Response
    response = Response()
    # Нужно получить ID пользователя из созданного клиента
    created_user = crud.get_user_by_login(user_data.login) # Это неэффективно, но работает
    if not created_user:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve user after registration")
    response.set_cookie(key="user_id", value=str(created_user['id']), httponly=True)
    response.set_cookie(key="user_role", value=created_user['role_name'], httponly=True)
    response.headers["Location"] = "/api/client/profile"
    return response

# Роут для отображения формы входа
@router.get("/login_form")
async def get_login_form(request: Request):
     return templates.TemplateResponse("login.html", {"request": request})

# Роут для отображения формы регистрации
@router.get("/register_form")
async def get_register_form(request: Request):
     return templates.TemplateResponse("register.html", {"request": request})