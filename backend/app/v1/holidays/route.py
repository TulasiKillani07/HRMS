from fastapi import APIRouter, Depends, Query, Path, UploadFile, File, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.holidays.schema import (
    HolidayCreateRequest, HolidayUpdateRequest,
    HolidayResponse, HolidayListResponse,
    HolidayCSVImportResponse,
)
from app.v1.holidays.service import HolidayService

router = APIRouter()


def _require_hr_access(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


def _require_any_auth(current_user: dict = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=HolidayResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Holiday",
    description="""
**Purpose:** Add a single holiday to the organization's calendar.

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Request Body:**
```json
{
  "name": "Republic Day",
  "date": "2025-01-26",
  "state": "All India",
  "type": "mandatory",
  "description": "National holiday"
}
```

| Field | Required | Notes |
|---|---|---|
| name | ✅ | Holiday name |
| date | ✅ | Format: YYYY-MM-DD |
| state | ❌ | State/Location (e.g., "Telangana", "All India") |
| type | ❌ | `mandatory` (default) or `optional` |
| description | ❌ | Additional details |

**Errors:**
- `400` — Duplicate holiday (same name + date), invalid date/type
""",
)
async def create_holiday(
    data: HolidayCreateRequest,
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await HolidayService(db).create_holiday(data, current_user, organization_id)


# ---------------------------------------------------------------------------
# CSV IMPORT
# ---------------------------------------------------------------------------
@router.post(
    "/import",
    response_model=HolidayCSVImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import Holidays via CSV",
    description="""
**Purpose:** Bulk upload holidays from a CSV file.

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Content-Type:** `multipart/form-data` — upload file in field named `file`.

**Required CSV Columns:** `name`, `date`
**Optional CSV Columns:** `state`, `type`, `description`

**CSV Template:**
```
name,date,state,type,description
Republic Day,2025-01-26,All India,mandatory,National holiday
Holi,2025-03-14,All India,mandatory,Festival of colors
Ugadi,2025-03-30,Telangana,optional,Telugu New Year
Eid ul-Fitr,2025-03-31,All India,optional,End of Ramadan
Independence Day,2025-08-15,All India,mandatory,National holiday
Ganesh Chaturthi,2025-08-27,Telangana,optional,Festival
Dussehra,2025-10-02,All India,mandatory,Victory of good over evil
Diwali,2025-10-20,All India,mandatory,Festival of lights
Christmas,2025-12-25,All India,mandatory,Christmas Day
```

**Notes:**
- `type` column defaults to `mandatory` if not provided or invalid
- Duplicate entries (same name + date) are skipped and reported as errors
- Date format must be YYYY-MM-DD

**Response 201:**
```json
{
  "imported": 8,
  "failed": 1,
  "errors": [
    { "row": 5, "name": "Republic Day", "error": "Duplicate: already exists" }
  ]
}
```
""",
)
async def import_holidays_csv(
    file: UploadFile = File(..., description="CSV file with holiday data"),
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    return await HolidayService(db).import_holidays_csv(file, current_user, organization_id)


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=HolidayListResponse,
    summary="List Holidays",
    description="""
**Purpose:** Get the holiday calendar for the organization with optional filters.

**Access:** All authenticated users

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| organization_id | string | null | Required for superadmin |
| year | int | null | Filter by year (e.g., 2025) |
| type | string | null | Filter: `mandatory` or `optional` |
| state | string | null | Filter by state/location (partial match) |
| page | int | 1 | Page number |
| limit | int | 50 | Items per page (max 100) |

**Response 200:**
```json
{
  "holidays": [
    {
      "id": "65abc...",
      "name": "Republic Day",
      "date": "2025-01-26",
      "state": "All India",
      "type": "mandatory",
      "description": "National holiday",
      "year": 2025,
      "created_at": "2025-01-01T09:00:00"
    }
  ],
  "total": 15,
  "page": 1,
  "limit": 50,
  "pages": 1
}
```
""",
)
async def get_holidays(
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    year: Optional[int] = Query(None, description="Filter by year"),
    type: Optional[str] = Query(None, description="mandatory | optional"),
    state: Optional[str] = Query(None, description="Filter by state/location"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any_auth)
):
    return await HolidayService(db).get_holidays(
        current_user, page, limit, year, type, state, organization_id
    )


# ---------------------------------------------------------------------------
# GET SINGLE
# ---------------------------------------------------------------------------
@router.get(
    "/{holiday_id}",
    response_model=HolidayResponse,
    summary="Get Holiday Detail",
    description="""
**Purpose:** Get full details of a single holiday.

**Access:** All authenticated users

**Path Parameter:** `holiday_id` — MongoDB ObjectId

**Errors:**
- `400` — Invalid ID format
- `404` — Holiday not found
""",
)
async def get_holiday(
    holiday_id: str = Path(..., description="Holiday MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any_auth)
):
    return await HolidayService(db).get_holiday_by_id(holiday_id, current_user)


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------
@router.put(
    "/{holiday_id}",
    response_model=HolidayResponse,
    summary="Update Holiday",
    description="""
**Purpose:** Update an existing holiday.

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Path Parameter:** `holiday_id` — MongoDB ObjectId

**Request Body (all fields optional):**
```json
{
  "name": "Republic Day (Updated)",
  "date": "2025-01-26",
  "state": "All India",
  "type": "optional",
  "description": "Updated description"
}
```

**Errors:**
- `400` — Invalid date/type, no fields provided
- `404` — Holiday not found
""",
)
async def update_holiday(
    data: HolidayUpdateRequest,
    holiday_id: str = Path(..., description="Holiday MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await HolidayService(db).update_holiday(holiday_id, data, current_user)


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------
@router.delete(
    "/{holiday_id}",
    summary="Delete Holiday",
    description="""
**Purpose:** Soft-delete a holiday from the calendar.

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Path Parameter:** `holiday_id` — MongoDB ObjectId

**Response 200:**
```json
{ "message": "Holiday 'Republic Day' on 2025-01-26 deleted successfully" }
```

**Errors:**
- `400` — Invalid ID
- `404` — Holiday not found
""",
)
async def delete_holiday(
    holiday_id: str = Path(..., description="Holiday MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await HolidayService(db).delete_holiday(holiday_id, current_user)
