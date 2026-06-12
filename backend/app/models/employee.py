from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class EmployeeModel(BaseModel):
    """Employee database model"""
    employee_id: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    date_of_birth: datetime
    gender: str
    address: str
    department_id: Optional[str] = None
    designation: str
    joining_date: datetime
    employment_type: str = "full-time"  # full-time, part-time, contract
    status: str = "active"  # active, inactive, terminated
    salary: float
    bank_account: Optional[str] = None
    emergency_contact: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "EMP001",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890",
                "date_of_birth": "1990-01-01",
                "gender": "Male",
                "address": "123 Main St",
                "designation": "Software Engineer",
                "joining_date": "2024-01-01",
                "salary": 50000.0
            }
        }
