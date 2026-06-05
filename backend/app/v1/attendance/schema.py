from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class AttendanceCheckInRequest(BaseModel):
    employee_id: str

class AttendanceCheckOutRequest(BaseModel):
    employee_id: str

class AttendanceResponse(BaseModel):
    id: str
    employee_id: str
    date: date
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    status: str
    work_hours: Optional[float] = None
    
    class Config:
        from_attributes = True
