from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any


# ---------------------------------------------------------------------------
# Office Location Schemas
# ---------------------------------------------------------------------------

class OfficeLocationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    address: str = Field(..., min_length=5, max_length=500)
    latitude: float = Field(...)
    longitude: float = Field(...)
    radius_meters: int = Field(200, ge=50, le=5000)
    is_active: bool = True

    class Config:
        json_schema_extra = {"example": {
            "name": "Hyderabad Office",
            "address": "Plot 42, Madhapur, Hyderabad, Telangana 500081",
            "latitude": 17.4484, "longitude": 78.3908,
            "radius_meters": 200, "is_active": True
        }}


class OfficeLocationUpdateRequest(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_meters: Optional[int] = Field(None, ge=50, le=5000)
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Check-in / Check-out Schemas
# ---------------------------------------------------------------------------

class CheckInRequest(BaseModel):
    latitude: float = Field(..., description="Employee GPS latitude")
    longitude: float = Field(..., description="Employee GPS longitude")
    photo_url: Optional[str] = Field(None, description="Base64 selfie or Cloudinary URL")
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {"example": {
            "latitude": 17.4485, "longitude": 78.3910,
            "photo_url": "https://res.cloudinary.com/...",
            "notes": ""
        }}


class CheckOutRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    photo_url: Optional[str] = None

    class Config:
        json_schema_extra = {"example": {
            "latitude": 17.4485, "longitude": 78.3910,
            "photo_url": "https://res.cloudinary.com/..."
        }}


# ---------------------------------------------------------------------------
# Regularization Schemas
# ---------------------------------------------------------------------------

class RegularizationRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    type: str = Field("missed_check_in", description="missed_check_in | missed_check_out | wrong_time | work_from_home")
    proposed_time: Optional[str] = Field(None, description="HH:MM")
    reason: str = Field(..., min_length=3, max_length=500)

    class Config:
        json_schema_extra = {"example": {
            "date": "2025-07-14", "type": "missed_check_in",
            "proposed_time": "09:00",
            "reason": "Forgot to punch in, was present in office"
        }}


class RegularizationRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


# ---------------------------------------------------------------------------
# HR Mark Attendance
# ---------------------------------------------------------------------------

class HRMarkAttendanceRequest(BaseModel):
    employee_id: str = Field(...)
    date: str = Field(..., description="YYYY-MM-DD")
    status: str = Field("present", description="present | absent | late | half_day | on_leave | holiday")
    check_in: Optional[str] = Field(None, description="HH:MM")
    check_out: Optional[str] = Field(None, description="HH:MM")
    reason: Optional[str] = None

    class Config:
        json_schema_extra = {"example": {
            "employee_id": "65emp...", "date": "2025-07-14",
            "status": "present", "check_in": "09:00", "check_out": "18:00",
            "reason": "Employee was at client site"
        }}


class AttendanceUpdateRequest(BaseModel):
    check_in: Optional[str] = Field(None, description="HH:MM")
    check_out: Optional[str] = Field(None, description="HH:MM")
    status: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Attendance Config Schema
# ---------------------------------------------------------------------------

class AttendanceConfigRequest(BaseModel):
    shift_start: Optional[str] = Field(None, description="HH:MM")
    shift_end: Optional[str] = Field(None, description="HH:MM")
    grace_period_minutes: Optional[int] = Field(None, ge=0, le=60)
    min_hours_full_day: Optional[float] = Field(None, ge=1, le=24)
    min_hours_half_day: Optional[float] = Field(None, ge=1, le=12)
    location_required_for_checkout: Optional[bool] = None
    photo_required: Optional[bool] = None
    weekend_days: Optional[List[int]] = None
    auto_mark_absent_after: Optional[str] = None

    class Config:
        json_schema_extra = {"example": {
            "shift_start": "09:00", "shift_end": "18:00",
            "grace_period_minutes": 15,
            "min_hours_full_day": 8, "min_hours_half_day": 4,
            "photo_required": True, "weekend_days": [0, 6]
        }}


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class AttendanceListResponse(BaseModel):
    records: List[Any]
    total: int
    page: int
    limit: int
    pages: int
