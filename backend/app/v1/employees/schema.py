from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime
from typing import Optional, Any, List


class EmployeeCreateRequest(BaseModel):
    employee_id: str = Field(..., min_length=1, max_length=50)
    organization_id: Optional[str] = Field(None, description="Required for superadmin. org_admin/hr_admin use their own org automatically.")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=20)
    date_of_birth: date
    gender: str = Field(..., description="Male / Female / Other")
    address: str = Field(..., min_length=5)
    department_id: Optional[str] = None
    designation: str = Field(..., min_length=2, max_length=100)
    joining_date: date
    employment_type: str = Field("full-time", description="full-time | part-time | contract")
    salary: float = Field(..., gt=0)
    bank_account: Optional[str] = None
    emergency_contact: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "EMP001",
                "first_name": "Amit",
                "last_name": "Sharma",
                "email": "amit.sharma@techsolutions.com",
                "phone": "+919876543210",
                "date_of_birth": "1995-06-15",
                "gender": "Male",
                "address": "45 Brigade Road, Bangalore",
                "department_id": None,
                "designation": "Software Engineer",
                "joining_date": "2024-01-15",
                "employment_type": "full-time",
                "salary": 65000.0,
                "bank_account": "HDFC000123456",
                "emergency_contact": {
                    "name": "Priya Sharma",
                    "relation": "Spouse",
                    "phone": "+919876543211"
                }
            }
        }


class EmployeeUpdateRequest(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    address: Optional[str] = None
    department_id: Optional[str] = None
    designation: Optional[str] = Field(None, min_length=2, max_length=100)
    employment_type: Optional[str] = None
    salary: Optional[float] = Field(None, gt=0)
    status: Optional[str] = Field(None, description="active | inactive | terminated")
    bank_account: Optional[str] = None
    emergency_contact: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "designation": "Senior Software Engineer",
                "salary": 80000.0,
                "department_id": "65abc123def456"
            }
        }


class EmployeeResponse(BaseModel):
    id: str
    employee_id: str
    organization_id: str
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
    bank_account: Optional[str] = None
    emergency_contact: Optional[dict] = None
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmployeeListResponse(BaseModel):
    employees: List[Any]
    total: int
    page: int
    limit: int
    pages: int
