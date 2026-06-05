from pydantic import BaseModel
from datetime import date
from typing import Optional

class LeaveCreateRequest(BaseModel):
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    reason: str

class LeaveResponse(BaseModel):
    id: str
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    days: int
    reason: str
    status: str
    
    class Config:
        from_attributes = True
