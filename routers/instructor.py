from fastapi import APIRouter, Depends, HTTPException, status, Request, Cookie
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import auth, schemas, crud
import logging

router = APIRouter()

templates = Jinja2Templates(directory="./templates")

logger = logging.getLogger(__name__)

def get_current_instructor(request: Request, user_id: int = Cookie(None), user_role: str = Cookie(None)):
    if not user_id or user_role not in ["instructor", "owner"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated as instructor")
    return int(user_id)


@router.get("/dashboard")
async def instructor_dashboard(request: Request, current_user_id: int = Depends(get_current_instructor)):
    with crud.db_query() as query:
        instructor_info = crud.get_instructor_by_user_id(current_user_id)
        if not instructor_info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found")

        user_info = crud.get_user_by_id(query, current_user_id)
        conducted_instructions = crud.get_conducted_instructions_for_instructor(instructor_info["id"])
        assigned_requests = crud.get_rental_requests_by_assigned_instructor_id(query, current_user_id)

    return templates.TemplateResponse("instructor/dashboard.html", {
        "request": request,
        "instructor": instructor_info,
        "assigned_requests": assigned_requests or [],
        "conducted_instructions": conducted_instructions,
        "user": user_info,
    })


@router.get("/instructions")
async def instructor_instructions_redirect(current_user_id: int = Depends(get_current_instructor)):
    return RedirectResponse(url="/api/instructor/dashboard", status_code=status.HTTP_302_FOUND)

@router.put("/confirm_instruction/{request_id}")
async def instructor_confirm_instruction(
    request_id: int,
    current_user_id: int = Depends(get_current_instructor)
):
    instructor_info = crud.get_instructor_by_user_id(current_user_id)
    if not instructor_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found")

    request_obj = crud.get_rental_request_by_id(request_id)
    if not request_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if request_obj["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Заявка уже обработана инструктором.")

    if not request_obj.get("instruction_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Инструктор не назначен на заявку.")

    instruction = crud.get_instruction_by_id(request_obj["instruction_id"])
    if not instruction or instruction["instructor_id"] != instructor_info["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не назначены на эту заявку.")

    updated_request = crud.confirm_instruction_for_request(request_id, instructor_info["id"])
    if not updated_request:
        instruction = crud.get_instruction_by_id(request_obj["instruction_id"])
        if instruction and instruction.get("time_conducted"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Инструктаж уже отмечен проведённым. Попросите админа переназначить инструктора на заявку.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось подтвердить инструктаж.",
        )

    return {
        "msg": "Инструктаж проведён. Заявка передана администратору на утверждение.",
        "request": updated_request,
    }
