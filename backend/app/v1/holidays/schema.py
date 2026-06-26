from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any


# ---------------------------------------------------------------------------
# Holiday CRUD Schemas
# ---------------------------------------------------------------------------

class HolidayCreateRequest(BaseModel):
    """Create a single holiday"""
    name: str = Field(..., min_length=2, max_length=200)
    date: str = Field(..., description="YYYY-MM-DD")
    state: Optional[str] = Field(None, max_length=100, description="State/Location or 'All India'")
    type: str = Field("mandatory", description="mandatory | optional")
    description: Optional[str] = Field(None, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Republic Day",
                "date": "2025-01-26",
                "state": "All India",
                "type": "mandatory",
                "description": "National holiday"
            }
        }


class HolidayUpdateRequest(BaseModel):
    """Update an existing holiday"""
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    date: Optional[str] = Field(None, description="YYYY-MM-DD")
    state: Optional[str] = Field(None, max_length=100)
    type: Optional[str] = Field(None, description="mandatory | optional")
    description: Optional[str] = Field(None, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Republic Day (Updated)",
                "type": "optional"
            }
        }


class HolidayResponse(BaseModel):
    id: str
    name: str
    date: str
    state: Optional[str] = None
    type: str
    description: Optional[str] = None
    year: int
    created_at: datetime
    updated_at: datetime


class HolidayListResponse(BaseModel):
    holidays: List[Any]
    total: int
    page: int
    limit: int
    pages: int


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------

class CSVImportError(BaseModel):
    row: int
    name: Optional[str] = None
    error: str


class HolidayCSVImportResponse(BaseModel):
    imported: int
    failed: int
    errors: List[CSVImportError]
