from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field

class LeaveModel(BaseModel):
    """Leave database model"""
    employee_id: str
    leave_type: str  # sick, casual, annual, unpaid
    start_date: date
    end_date: date
    days: int
    reason: str
    status: str = "pending"  # pending, approved, rejected
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "EMP001",
                "leave_type": "casual",
                "start_date": "2024-01-15",
                "end_date": "2024-01-17",
                "days": 3,
                "reason": "Personal work",
                "status": "pending"
            }
        }
