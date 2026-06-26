from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HolidayModel(BaseModel):
    """Holiday calendar entry — stored in db.holidays"""
    organization_id: str
    name: str                                    # Holiday Name
    date: str                                    # "YYYY-MM-DD"
    state: Optional[str] = None                  # State/Location (e.g., "Telangana", "All India")
    type: str = "mandatory"                      # mandatory | optional
    description: Optional[str] = None
    year: int                                    # Derived from date for easy filtering
    is_deleted: bool = False
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "name": "Republic Day",
                "date": "2025-01-26",
                "state": "All India",
                "type": "mandatory",
                "description": "National holiday celebrating the constitution",
                "year": 2025
            }
        }
