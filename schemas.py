from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Схемы для RentalRequest
class RentalRequestCreate(BaseModel):
    vessel_id: int
    water_body_id: int
    desired_start: datetime
    desired_end: datetime

class RentalRequestUpdate(BaseModel):
    status: Optional[str] = None
    admin_comment: Optional[str] = None

class RentalRequest(BaseModel):
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
        from_attributes = True

# Схемы для Rent
class RentCreate(BaseModel):
    client_id: int
    instruction_id: int
    vessel_id: int
    water_body_id: int
    start_time: datetime
    return_time: Optional[datetime] = None

class Rent(RentCreate):
    id: int

    class Config:
        from_attributes = True

# Схемы для Vessel
class Vessel(BaseModel):
    id: int
    name: str
    number: str
    type_vessel_id: int
    current_status_id: int

    class Config:
        from_attributes = True

# Схемы для WaterBody
class WaterBody(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

# Схемы для Instruction
class InstructionCreate(BaseModel):
    instructor_id: int
    type_instruction_id: int
    time_conducted: Optional[datetime] = None

class Instruction(InstructionCreate):
    id: int

    class Config:
        from_attributes = True

# Добавьте другие схемы по аналогии...