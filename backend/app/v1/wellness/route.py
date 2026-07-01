from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.wellness.service import WellnessService

router = APIRouter()

def _hr(u: dict = Depends(get_current_user)):
    if u.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return u

def _emp(u: dict = Depends(get_current_user)):
    if u.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Only employees")
    return u

def _any(u: dict = Depends(get_current_user)):
    return u


class MoodRequest(BaseModel):
    score: int = Field(..., ge=1, le=5, description="1=terrible, 2=low, 3=okay, 4=good, 5=great")
    note: Optional[str] = Field(None, max_length=500)
    class Config:
        json_schema_extra = {"example": {"score": 4, "note": "Feeling good today"}}


# ===========================================================================
# MOOD
# ===========================================================================

@router.post("/mood", status_code=201, summary="Submit Daily Mood", description="""
**Purpose:** Employee submits their daily mood (1-5). One entry per day — cannot resubmit.

**Access:** `employee`

**Request Body:**
```json
{ "score": 4, "note": "Productive morning" }
```
Score: 1 (terrible) → 5 (great)

**Response 201:**
```json
{ "id": "...", "score": 4, "date": "2025-06-24", "note": "...", "streak": 5 }
```

**Errors:**
- `400` — Mood already submitted for today
""")
async def submit_mood(data: MoodRequest, db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await WellnessService(db).submit_mood(data.score, data.note, current_user)


@router.get("/mood/history", summary="My Mood History", description="""
**Purpose:** Employee views own mood history.

**Access:** `employee`

**Query:** days (default: 30, max: 365)

**Response 200:**
```json
{ "entries": [...], "average": 3.8, "streak": 5, "total_entries": 20 }
```
""")
async def get_mood_history(days: int = Query(30, ge=1, le=365), db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await WellnessService(db).get_mood_history(current_user, days)


# ===========================================================================
# HR DASHBOARD & ANALYTICS
# ===========================================================================

@router.get("/dashboard", summary="Wellness Dashboard", description="""
**Purpose:** HR sees org-wide wellness overview.

**Access:** `org_admin`, `hr_admin`

**Response 200:**
```json
{
  "wellness_score": 78,
  "mood_distribution": { "great": 8, "good": 15, "okay": 5, "low": 2, "terrible": 1 },
  "weekly_trend": [{ "day": "Mon", "avg_score": 3.8 }],
  "department_scores": { "Engineering": 4.1, "Marketing": 3.2 },
  "at_risk_employees": [{ "employee_name": "Sneha", "avg_score_7d": 2.1 }],
  "participation_rate": 75,
  "total_submissions_today": 22
}
```
""")
async def get_dashboard(organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await WellnessService(db).get_dashboard(current_user, organization_id)


@router.get("/analytics", summary="Mood Analytics", description="""
**Purpose:** Deeper mood insights — trends, day-of-week patterns, period comparison.

**Access:** `org_admin`, `hr_admin`

**Query:** period (days, default: 30, min: 7)
""")
async def get_analytics(period: int = Query(30, ge=7, le=365), organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await WellnessService(db).get_analytics(current_user, period, organization_id)


@router.get("/mood/entries", summary="All Mood Entries (HR View)", description="""
**Purpose:** HR and admin view all employee mood entries with full filters.

**Access:** `org_admin`, `hr_admin`

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| employee_id | string | Filter by specific employee |
| department | string | Filter by department |
| date | string | Specific date (YYYY-MM-DD) |
| from_date | string | Range start (YYYY-MM-DD) |
| to_date | string | Range end (YYYY-MM-DD) |
| month | int | Month (1-12) |
| year | int | Year |
| score | int | Filter by score 1-5 |
| page | int | Default 1 |
| limit | int | Default 50 |

**Response 200:**
```json
{
  "entries": [
    { "employee_name": "Rahul Verma", "department": "Engineering", "date": "2025-07-15", "score": 4, "note": "Productive" }
  ],
  "total": 150,
  "summary": {
    "avg_score": 3.8,
    "total_entries": 150,
    "score_distribution": { "terrible": 2, "low": 10, "okay": 45, "good": 70, "great": 23 }
  }
}
```
""")
async def get_mood_entries(
    employee_id: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None),
    score: Optional[int] = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)
):
    return await WellnessService(db).get_mood_entries(
        current_user, page, limit, employee_id, department,
        date, from_date, to_date, month, year, score, organization_id
    )
