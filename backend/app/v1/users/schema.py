from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    role: str = Field(..., description="Role: org_admin (by superadmin) or hr_admin (by org_admin/superadmin)")
    organization_id: Optional[str] = Field(
        None,
        description="Required when superadmin creates org_admin or hr_admin. org_admin creating hr_admin uses their own org automatically."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email": "hradmin@techsolutions.com",
                "full_name": "HR Manager",
                "phone": "+919876543210",
                "role": "hr_admin",
                "organization_id": "65abc123def456"
            }
        }


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Updated Name",
                "phone": "+919876543211",
                "email": "newemail@techsolutions.com"
            }
        }


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    phone: Optional[str] = None
    status: str                           # "active" | "inactive"
    is_verified: bool
    requires_password_change: bool
    organization_id: Optional[str] = None
    org_name: Optional[str] = None        # Populated for superadmin calls only
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[Any]
    total: int
    page: int
    limit: int
    pages: int
