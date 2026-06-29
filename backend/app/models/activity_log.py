from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ActivityLogModel(BaseModel):
    """Activity log entry — stored in db.activity_logs"""
    organization_id: Optional[str] = None        # null for superadmin-level actions
    user_id: str
    user_name: str
    user_role: str                               # superadmin | org_admin | hr_admin | employee
    action: str                                  # created | updated | deleted | approved | rejected | login | etc.
    module: str                                  # employee | leave | attendance | department | organization | auth | etc.
    description: str                             # Human-readable description
    target_id: Optional[str] = None              # ID of affected record
    target_name: Optional[str] = None            # Name of affected record (employee name, dept name, etc.)
    target_type: Optional[str] = None            # employee | leave_request | department | etc.
    metadata: Optional[dict] = None              # Extra context (old/new values, etc.)
    ip_address: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
