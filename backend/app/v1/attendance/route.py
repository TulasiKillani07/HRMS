from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.attendance.schema import *
from app.v1.attendance.service import AttendanceService

router = APIRouter()

def _hr(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user

def _emp(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Only employees")
    return current_user

def _any(current_user: dict = Depends(get_current_user)):
    return current_user


# ===========================================================================
# OFFICE LOCATIONS
# ===========================================================================

@router.post("/locations", status_code=201, summary="Create Office Location", description="""
**Purpose:** HR configures office locations with GPS coordinates and allowed radius. Used to validate employee check-ins.

**Access:** `org_admin`, `hr_admin`

**Request Body:**
```json
{ "name": "Hyderabad Office", "address": "Plot 42, Madhapur, Hyderabad", "latitude": 17.4484, "longitude": 78.3908, "radius_meters": 200, "is_active": true }
```

**Response 201:** Created location with ID.
""")
async def create_location(data: OfficeLocationCreateRequest, organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).create_location(data, current_user, organization_id)

@router.get("/locations", summary="List Office Locations", description="""
**Purpose:** Get all configured office locations for the organization.

**Access:** All authenticated users
""")
async def get_locations(organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AttendanceService(db).get_locations(current_user, organization_id)

@router.put("/locations/{location_id}", summary="Update Office Location", description="""
**Purpose:** Update office location details (name, coordinates, radius, active status).

**Access:** `org_admin`, `hr_admin`
""")
async def update_location(data: OfficeLocationUpdateRequest, location_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).update_location(location_id, data, current_user)

@router.delete("/locations/{location_id}", summary="Delete Office Location", description="""
**Purpose:** Remove an office location.

**Access:** `org_admin`, `hr_admin`
""")
async def delete_location(location_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).delete_location(location_id, current_user)


# ===========================================================================
# EMPLOYEE CHECK-IN / CHECK-OUT
# ===========================================================================

@router.post("/check-in", status_code=201, summary="Employee Check-In", description="""
**Purpose:** Employee punches in. Backend validates GPS against configured office locations. Captures photo for verification.

**Access:** `employee` only

**Request Body:**
```json
{ "latitude": 17.4485, "longitude": 78.3910, "photo_url": "https://res.cloudinary.com/...", "notes": "" }
```

**Backend Validation:**
- Calculates distance between employee GPS and each active office location
- If distance ≤ radius_meters → check-in allowed
- If no match → rejected with error showing nearest office and distance

**Response 201:**
```json
{
  "id": "65att...", "employee_name": "Rahul Verma", "date": "2025-07-15",
  "check_in": "2025-07-15T09:05:32",
  "check_in_location": { "latitude": 17.4485, "longitude": 78.3910, "matched_office": "Hyderabad Office", "distance_meters": 45 },
  "check_in_photo": "https://...", "status": "present", "is_late": true, "late_by_minutes": 5
}
```

**Errors:**
- `400` — Already checked in today
- `403` — Not within any office location (shows nearest office + distance)
""")
async def check_in(data: CheckInRequest, db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await AttendanceService(db).check_in(data, current_user)

@router.post("/check-out", summary="Employee Check-Out", description="""
**Purpose:** Employee punches out. Calculates total working hours and determines status.

**Access:** `employee` only

**Request Body:**
```json
{ "latitude": 17.4485, "longitude": 78.3910, "photo_url": "https://..." }
```

**Status Logic:** `≥ min_hours_full_day` → present, `≥ min_hours_half_day` → half_day, late if was late at check-in

**Response 200:**
```json
{
  "id": "65att...", "date": "2025-07-15",
  "check_in": "2025-07-15T09:05:32", "check_out": "2025-07-15T18:30:00",
  "total_hours": 9.41, "status": "present",
  "check_out_location": { "latitude": 17.4485, "longitude": 78.3910 }
}
```

**Errors:** `400` — Not checked in today / already checked out
""")
async def check_out(data: CheckOutRequest, db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await AttendanceService(db).check_out(data, current_user)

@router.get("/today", summary="Today's Attendance Status", description="""
**Purpose:** Get today's attendance status.

**Access:**
- `employee` — sees own (no param needed)
- `org_admin`, `hr_admin` — pass `?employee_id=` to view specific employee

**Response 200:**
```json
{ "date": "2025-07-15", "status": "checked_in", "check_in": "2025-07-15T09:05:32", "check_out": null, "is_late": true, "late_by_minutes": 5, "check_in_location": { "matched_office": "Hyderabad Office" } }
```
""")
async def get_today(employee_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AttendanceService(db).get_today(current_user, employee_id)

@router.get("/my-history", summary="Attendance History", description="""
**Purpose:** Attendance history.

**Access:**
- `employee` — sees own history (no param needed)
- `org_admin`, `hr_admin` — pass `?employee_id=` to view specific employee

**Query:** employee_id (HR only), month (1-12), year, page, limit
""")
async def get_my_history(employee_id: Optional[str] = Query(None), page: int = Query(1, ge=1), limit: int = Query(31, ge=1, le=100),
    month: Optional[int] = Query(None, ge=1, le=12), year: Optional[int] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AttendanceService(db).get_my_history(current_user, page, limit, month, year, employee_id)

@router.post("/regularize", status_code=201, summary="Request Regularization", description="""
**Purpose:** Employee requests to fix missed/incorrect attendance.

**Access:** `employee` only

**Request Body:**
```json
{ "date": "2025-07-14", "type": "missed_check_in", "proposed_time": "09:00", "reason": "Forgot to punch in" }
```

**Types:** `missed_check_in` | `missed_check_out` | `wrong_time` | `work_from_home`
""")
async def request_regularization(data: RegularizationRequest, db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await AttendanceService(db).request_regularization(data, current_user)


# ===========================================================================
# HR MANAGEMENT
# ===========================================================================

@router.get("/", response_model=AttendanceListResponse, summary="List Attendance Records", description="""
**Purpose:** List all attendance records with filters.

**Access:** `employee` (own) | `org_admin`, `hr_admin` (all in org)

**Query:** date, from_date, to_date, employee_id, department, status, page, limit
""")
async def get_attendance_list(
    date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    from_date: Optional[str] = Query(None), to_date: Optional[str] = Query(None),
    employee_id: Optional[str] = Query(None), department: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="present|absent|late|half_day|on_leave|holiday"),
    organization_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200),
    db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AttendanceService(db).get_attendance_list(
        current_user, page, limit, date, from_date, to_date, employee_id, department, status, organization_id)

@router.get("/summary", summary="Monthly Attendance Summary", description="""
**Purpose:** Monthly summary per employee (present/absent/late/half-day/hours).

**Access:** `org_admin`, `hr_admin`

**Query:** month, year, department, employee_id
""")
async def get_summary(month: Optional[int] = Query(None, ge=1, le=12), year: Optional[int] = Query(None),
    department: Optional[str] = Query(None), employee_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).get_summary(current_user, month, year, department, employee_id, organization_id)

@router.post("/mark", status_code=201, summary="HR Mark Attendance", description="""
**Purpose:** HR manually marks attendance (missed punches, outdoor work, etc.)

**Access:** `org_admin`, `hr_admin`

**Request Body:**
```json
{ "employee_id": "65emp...", "date": "2025-07-14", "status": "present", "check_in": "09:00", "check_out": "18:00", "reason": "Client site" }
```
""")
async def mark_attendance(data: HRMarkAttendanceRequest, db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).mark_attendance(data, current_user)

# ===========================================================================
# CONFIG (must be before /{attendance_id} to avoid route conflict)
# ===========================================================================

@router.get("/config", summary="Get Attendance Config", description="""
**Purpose:** Get org-level attendance configuration (shift times, grace period, etc.)

**Access:** All authenticated users
""")
async def get_config(organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AttendanceService(db).get_config_endpoint(current_user, organization_id)

@router.put("/config", summary="Update Attendance Config", description="""
**Purpose:** Set org-level attendance policies.

**Access:** `org_admin`, `hr_admin`

**Request Body (all optional):**
```json
{
  "shift_start": "09:00", "shift_end": "18:00",
  "grace_period_minutes": 15, "min_hours_full_day": 8, "min_hours_half_day": 4,
  "location_required_for_checkout": false, "photo_required": true,
  "weekend_days": [0, 6], "auto_mark_absent_after": "11:00"
}
```
""")
async def update_config(data: AttendanceConfigRequest, organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).update_config(data, current_user, organization_id)

@router.put("/{attendance_id}", summary="Edit Attendance Record", description="""
**Purpose:** HR edits an existing attendance record.

**Access:** `org_admin`, `hr_admin`

**Request Body (all optional):**
```json
{ "check_in": "09:15", "check_out": "18:30", "status": "late", "notes": "Arrived 15 min late" }
```
""")
async def update_attendance(data: AttendanceUpdateRequest, attendance_id: str = Path(...),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).update_attendance(attendance_id, data, current_user)

@router.get("/regularizations", summary="List Regularization Requests", description="""
**Purpose:** List regularization requests.

**Access:** `employee` (own) | `org_admin`, `hr_admin` (all)

**Query:** status (pending/approved/rejected), employee_id, page, limit
""")
async def get_regularizations(status: Optional[str] = Query(None), employee_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AttendanceService(db).get_regularizations(current_user, status, employee_id, page, limit, organization_id)

@router.patch("/regularizations/{reg_id}/approve", summary="Approve Regularization", description="""
**Purpose:** HR approves — creates/updates attendance record.

**Access:** `org_admin`, `hr_admin`
""")
async def approve_regularization(reg_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).approve_regularization(reg_id, current_user)

@router.patch("/regularizations/{reg_id}/reject", summary="Reject Regularization", description="""
**Purpose:** HR rejects with reason.

**Access:** `org_admin`, `hr_admin`

**Request Body:** `{ "reason": "No evidence" }`
""")
async def reject_regularization(data: RegularizationRejectRequest, reg_id: str = Path(...),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).reject_regularization(reg_id, data.reason, current_user)


# ===========================================================================
# REPORTS
# ===========================================================================

@router.get("/reports/daily", summary="Daily Attendance Report", description="""
**Purpose:** Shows who's present and absent on a date. Includes GPS location and late info.

**Access:** `org_admin`, `hr_admin`

**Query:** date (YYYY-MM-DD, default: today)

**Response 200:**
```json
{
  "date": "2025-07-15", "total_employees": 50, "present_count": 42, "absent_count": 8,
  "present": [{ "name": "Rahul", "status": "present", "check_in": "09:05", "is_late": true, "check_in_location": {...} }],
  "absent": [{ "name": "Priya", "department": "Design", "status": "absent" }]
}
```
""")
async def report_daily(date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).report_daily(current_user, date, organization_id)

@router.get("/reports/monthly", summary="Monthly Report by Department", description="""
**Purpose:** Monthly attendance breakdown by department.

**Access:** `org_admin`, `hr_admin`

**Query:** month, year, department

**Response 200:**
```json
{
  "year": 2025, "month": 7,
  "departments": [{ "department": "Engineering", "present_days": 450, "absent_days": 20, "late_days": 15, "total_hours": 3800 }]
}
```
""")
async def report_monthly(month: Optional[int] = Query(None, ge=1, le=12), year: Optional[int] = Query(None),
    department: Optional[str] = Query(None), organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AttendanceService(db).report_monthly(current_user, month, year, department, organization_id)
