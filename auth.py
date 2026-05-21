from sqlalchemy.orm import Session
from models import UserLogin
import crud # Импортируем для получения пользователя

def authenticate_user(db: Session, login: str, password: str):
    user = crud.get_user_by_login(db, login)
    if not user or user.password_hash != password: # Для упрощения, не хешируем пароль
        return None
    return user