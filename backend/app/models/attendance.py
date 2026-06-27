from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
import math


# ---------------------------------------------------------------------------
# Office Location Model
# ---------------------------------------------------------------------------

class OfficeLocationModel(BaseModel):
    """Office location for GPS validation — stored in db.office_locations"""
    organization_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    radius_meters: int = 200
    is_active: bool = True
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Attendance Configuration Model
# ---------------------------------------------------------------------------

class AttendanceConfigModel(BaseModel):
    """Org-level attendance config — stored in db.attendance_config"""
    organization_id: str
    shift_start: str = "09:00"                   # HH:MM
    shift_end: str = "18:00"                     # HH:MM
    grace_period_minutes: int = 15
    min_hours_full_day: float = 8.0
    min_hours_half_day: float = 4.0
    location_required_for_checkout: bool = False
    photo_required: bool = True
    weekend_days: List[int] = [0, 6]             # 0=Monday...6=Sunday (ISO)
    auto_mark_absent_after: str = "11:00"        # HH:MM
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Attendance Record Model
# ---------------------------------------------------------------------------

class AttendanceModel(BaseModel):
    """Daily attendance record — stored in db.attendance"""
    organization_id: str
    employee_id: str
    employee_name: str
    department: str
    date: str                                    # "YYYY-MM-DD"
    # Check-in
    check_in: Optional[datetime] = None
    check_in_location: Optional[dict] = None     # {latitude, longitude, matched_office, distance_meters}
    check_in_photo: Optional[str] = None         # Base64 or Cloudinary URL
    # Check-out
    check_out: Optional[datetime] = None
    check_out_location: Optional[dict] = None
    check_out_photo: Optional[str] = None
    # Calculated
    total_hours: Optional[float] = None
    status: str = "absent"                       # present | absent | late | half_day | on_leave | holiday
    is_late: bool = False
    late_by_minutes: int = 0
    # Metadata
    source: str = "self"                         # self | hr_manual | regularization
    marked_by: Optional[str] = None
    marked_by_name: Optional[str] = None
    notes: Optional[str] = None
    is_regularized: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Regularization Model
# ---------------------------------------------------------------------------

class RegularizationModel(BaseModel):
    """Attendance regularization request — stored in db.attendance_regularizations"""
    organization_id: str
    employee_id: str
    employee_name: str
    department: str
    attendance_id: Optional[str] = None
    date: str
    type: str = "missed_check_in"                # missed_check_in | missed_check_out | wrong_time | work_from_home
    proposed_time: Optional[str] = None          # HH:MM
    reason: str
    status: str = "pending"                      # pending | approved | rejected
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Haversine distance calculation
# ---------------------------------------------------------------------------

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two GPS points"""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
