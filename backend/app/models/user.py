from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class UserModel(BaseModel):
    """User database model"""
    email: EmailStr
    hashed_password: str
    full_name: str
    role: str = "employee"  # superadmin, org_admin, hr_admin, employee
    phone: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    requires_password_change: bool = False
    employee_id: Optional[str] = None
    organization_id: Optional[str] = None  # Reference to organization
    # OTP fields for password reset
    password_reset_otp: Optional[str] = None
    password_reset_otp_expires_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "hashed_password": "hashed_password_here",
                "full_name": "John Doe",
                "role": "employee",
                "is_active": True,
                "is_verified": False
            }
        }
