from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class OrganizationModel(BaseModel):
    """Organization database model"""
    org_name: str
    email: EmailStr
    emp_count_for_access: int  # Employee limit/quota
    industry: str
    country: str
    state: str
    admin_name: str
    admin_email: EmailStr
    admin_phone: str
    org_address: Optional[str] = None
    admin_user_id: Optional[str] = None  # Reference to user in users collection
    status: str = "active"  # active or inactive
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "org_name": "Tech Solutions Inc",
                "email": "contact@techsolutions.com",
                "emp_count_for_access": 100,
                "industry": "Information Technology",
                "country": "USA",
                "state": "California",
                "admin_name": "John Admin",
                "admin_email": "admin@techsolutions.com",
                "admin_phone": "+1234567890",
                "org_address": "123 Tech Street, Silicon Valley",
                "status": "active"
            }
        }
