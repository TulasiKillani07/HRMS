from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class OrganizationCreateRequest(BaseModel):
    org_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    emp_count_for_access: int = Field(..., gt=0, description="Employee access limit")
    admin_user_access_limit: int = Field(2, gt=0, description="Admin user access limit (org_admin + hr_admin), default is 2")
    industry: str = Field(..., min_length=2, max_length=100, description="Industry type")
    country: str = Field(..., min_length=2)
    state: str = Field(..., min_length=2)
    admin_name: str = Field(..., min_length=2, max_length=100)
    admin_email: EmailStr
    admin_phone: str = Field(..., min_length=10, max_length=20)
    org_address: Optional[str] = Field(None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "org_name": "Tech Solutions Inc",
                "email": "contact@techsolutions.com",
                "emp_count_for_access": 100,
                "admin_user_access_limit": 2,
                "industry": "Information Technology",
                "country": "India",
                "state": "Karnataka",
                "admin_name": "Rajesh Kumar",
                "admin_email": "admin@techsolutions.com",
                "admin_phone": "+919876543210",
                "org_address": "123 MG Road, Bangalore"
            }
        }

class OrganizationUpdateRequest(BaseModel):
    org_name: Optional[str] = Field(None, min_length=2, max_length=200)
    email: Optional[EmailStr] = None
    emp_count_for_access: Optional[int] = Field(None, gt=0)
    admin_user_access_limit: Optional[int] = Field(None, gt=0, description="Admin user access limit")
    industry: Optional[str] = Field(None, min_length=2, max_length=100)
    country: Optional[str] = Field(None, min_length=2)
    state: Optional[str] = Field(None, min_length=2)
    admin_name: Optional[str] = Field(None, min_length=2, max_length=100)
    admin_email: Optional[EmailStr] = None
    admin_phone: Optional[str] = Field(None, min_length=10, max_length=20)
    org_address: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")

class OrganizationResponse(BaseModel):
    id: str
    org_name: str
    email: EmailStr
    emp_count_for_access: int
    admin_user_access_limit: int
    industry: str
    country: str
    state: str
    admin_name: str
    admin_email: EmailStr
    admin_phone: str
    org_address: Optional[str] = None
    admin_user_id: Optional[str] = None
    status: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
