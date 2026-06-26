from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class NotificationModel(BaseModel):
    """In-app notification — stored in db.notifications"""
    organization_id: str
    user_id: str                                 # Recipient user ID
    title: str
    message: str
    type: str = "info"                           # info | action | alert
    category: str = "general"                    # general | edit_request | leave | onboarding | performance
    reference_id: Optional[str] = None           # Related document ID (edit_request_id, leave_id, etc.)
    reference_type: Optional[str] = None         # edit_request | leave_request | employee
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "user_id": "65user001abc",
                "title": "Edit Request",
                "message": "Rahul Verma wants to edit bank_details",
                "type": "action",
                "category": "edit_request",
                "reference_id": "65req001abc",
                "reference_type": "edit_request",
                "is_read": False
            }
        }
