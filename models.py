from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class UserLogin(BaseModel):
    login: str
    password: str

class UserRegister(BaseModel):
    login: str
    password: str
    surname: str
    address: Optional[str] = None
    passport: Optional[str] = None

class RentalRequestCreate(BaseModel):
    vessel_id: int
    water_body_id: int
    desired_start: datetime
    desired_end: datetime

class RentalRequestUpdateStatus(BaseModel):
    status: str
    admin_comment: Optional[str] = None

class RentCreate(BaseModel):
    client_id: int
    instruction_id: int
    vessel_id: int
    water_body_id: int
    start_time: datetime
    return_time: Optional[datetime] = None

class RentalRequestOut(BaseModel):
    id: int
    client_id: int
    vessel_id: int
    water_body_id: int
    desired_start: datetime
    desired_end: datetime
    status: str
    created_at: datetime
    admin_comment: Optional[str]
    assigned_instructor_id: Optional[int]

    class Config:
        from_attributes = False # Не ORM