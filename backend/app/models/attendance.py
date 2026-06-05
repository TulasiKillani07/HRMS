from datetime import datetime, date, time
from typing import Optional
from pydantic import BaseModel, Field

class AttendanceModel(BaseModel):
    """Attendance database model"""
    employee_id: str
    date: date
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    status: str = "present"  # present, absent, half-day, leave
    work_hours: Optional[float] = None
    overtime_hours: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "EMP001",
                "date": "2024-01-01",
                "check_in": "2024-01-01T09:00:00",
                "check_out": "2024-01-01T18:00:00",
                "status": "present",
                "work_hours": 9.0
            }
        }
