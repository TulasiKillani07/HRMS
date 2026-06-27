from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AnnouncementModel(BaseModel):
    """Announcement — stored in db.announcements"""
    organization_id: str
    title: str
    content: str
    type: str = "general"                        # general | urgent | event | policy | celebration
    priority: str = "normal"                     # low | normal | high
    target_departments: List[str] = []           # Empty = all employees
    is_pinned: bool = False
    expires_at: Optional[str] = None             # "YYYY-MM-DD" or null
    created_by: str
    created_by_name: str
    is_deleted: bool = False
    read_by: List[str] = []                      # List of user_ids who read it
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
