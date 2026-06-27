from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DepartmentModel(BaseModel):
    """Department database model"""
    organization_id: str
    name: str
    code: str
    description: Optional[str] = None
    status: str = "active"               # active | inactive
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "name": "Engineering",
                "code": "ENG",
                "description": "Engineering Department",
                "status": "active"
            }
        }
