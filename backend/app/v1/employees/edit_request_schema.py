from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any


class EditRequestCreateSchema(BaseModel):
    """Employee requests permission to edit a section"""
    section: str = Field(..., description="Section to edit: personal_details | address | emergency_contact | bank_details | government_ids | education | experience")
    reason: str = Field(..., min_length=3, max_length=500, description="Why you need to edit")

    class Config:
        json_schema_extra = {
            "example": {
                "section": "bank_details",
                "reason": "I changed my bank account and need to update IFSC and account number"
            }
        }


class EditRequestApproveSchema(BaseModel):
    """HR approves edit request — gives employee a time window"""
    hours: int = Field(3, ge=1, le=72, description="Number of hours employee has to complete the edit (default: 3)")

    class Config:
        json_schema_extra = {
            "example": {
                "hours": 3
            }
        }


class EditRequestRejectSchema(BaseModel):
    """HR rejects edit request"""
    reason: str = Field(..., min_length=3, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Bank details can only be changed during salary processing window"
            }
        }


class EditRequestResponse(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    department: str
    section: str
    reason: str
    status: str
    approved_by_name: Optional[str] = None
    approved_at: Optional[Any] = None
    rejection_reason: Optional[str] = None
    rejected_by_name: Optional[str] = None
    edit_allowed_until: Optional[Any] = None
    edit_completed: bool = False
    edit_completed_at: Optional[Any] = None
    created_at: Any
    updated_at: Any


class EditRequestListResponse(BaseModel):
    requests: List[Any]
    total: int
    page: int
    limit: int
    pages: int
