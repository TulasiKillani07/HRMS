from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class EditRequestModel(BaseModel):
    """Employee profile edit request — stored in db.edit_requests"""
    organization_id: str
    employee_id: str                             # Employee MongoDB ObjectId
    employee_name: str
    department: str
    section: str                                 # Which section to edit: personal_details, address, etc.
    reason: str                                  # Why employee wants to edit
    status: str = "pending"                      # pending | approved | rejected | expired
    # Approval tracking
    approved_by: Optional[str] = None            # User ID of HR who approved
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_by_name: Optional[str] = None
    rejected_at: Optional[datetime] = None
    # Edit window
    edit_allowed_until: Optional[datetime] = None  # Time window to make the edit (e.g., 3 hours)
    edit_completed: bool = False                  # Employee actually saved changes
    edit_completed_at: Optional[datetime] = None
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "employee_id": "65emp001abc",
                "employee_name": "Rahul Verma",
                "department": "Engineering",
                "section": "bank_details",
                "reason": "Changed bank account",
                "status": "pending"
            }
        }
