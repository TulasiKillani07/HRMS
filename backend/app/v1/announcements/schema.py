from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=300)
    content: str = Field(..., min_length=2, max_length=5000)
    type: str = Field("general", description="general | urgent | event | policy | celebration")
    priority: str = Field("normal", description="low | normal | high")
    target_departments: List[str] = Field(default=[], description="Empty = all employees")
    is_pinned: bool = False
    expires_at: Optional[str] = Field(None, description="YYYY-MM-DD or null")

    class Config:
        json_schema_extra = {"example": {
            "title": "Office Closed on July 4th",
            "content": "The office will remain closed on account of Independence Day.",
            "type": "general", "priority": "normal",
            "target_departments": [], "is_pinned": False, "expires_at": "2025-07-05"
        }}


class AnnouncementUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=300)
    content: Optional[str] = Field(None, min_length=2, max_length=5000)
    type: Optional[str] = None
    priority: Optional[str] = None
    target_departments: Optional[List[str]] = None
    is_pinned: Optional[bool] = None
    expires_at: Optional[str] = None


class AnnouncementListResponse(BaseModel):
    announcements: List[Any]
    total: int
    page: int
    pages: int
