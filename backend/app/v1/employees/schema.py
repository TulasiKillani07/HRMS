from pydantic import BaseModel, EmailStr, Field
from datetime import date
from typing import Optional

class EmployeeCreateRequest(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    date_of_birth: date
    gender: str
    address: str
    department_id: Optional[str] = None
    designation: str
    joining_date: date
    employment_type: str = "full-time"
    salary: float
    bank_account: Optional[str] = None
    emergency_contact: Optional[dict] = None

class EmployeeUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    department_id: Optional[str] = None
    designation: Optional[str] = None
    employment_type: Optional[str] = None
    salary: Optional[float] = None
    status: Optional[str] = None
    bank_account: Optional[str] = None
    emergency_contact: Optional[dict] = None

class EmployeeResponse(BaseModel):
    id: str
    employee_id: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    date_of_birth: date
    gender: str
    address: str
    department_id: Optional[str] = None
    designation: str
    joining_date: date
    employment_type: str
    status: str
    salary: float
    
    class Config:
        from_attributes = True
