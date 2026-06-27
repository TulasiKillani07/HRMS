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


class ProgramRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    type: str = Field("ongoing", description="ongoing | challenge | event")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    max_participants: Optional[int] = None
    class Config:
        json_schema_extra = {"example": {"name": "Mental Health Support", "description": "Free counseling", "type": "ongoing"}}


# ===========================================================================
# MOOD
# ===========================================================================

@router.post("/mood", status_code=201, summary="Submit Daily Mood", description="""
**Purpose:** Employee submits their daily mood (1-5). One entry per day (upsert).

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
""")
async def submit_mood(data: MoodRequest, db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await WellnessService(db).submit_mood(data.score, data.note, current_user)


@router.get("/mood/history", summary="My Mood History", description="""
**Purpose:** Employee views own mood history.

**Access:** `employee`

**Query:** days (default: 30)

**Response 200:**
```json
{ "entries": [...], "average": 3.8, "streak": 5, "total_entries": 20 }
```
""")
async def get_mood_history(days: int = Query(30, ge=1, le=365), db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await WellnessService(db).get_mood_history(current_user, days)


# ===========================================================================
# DASHBOARD & ANALYTICS (HR)
# ===========================================================================

@router.get("/dashboard", summary="Wellness Dashboard", description="""
**Purpose:** HR sees org-wide wellness overview — mood distribution, weekly trend, department scores, at-risk employees.

**Access:** `org_admin`, `hr_admin`

**Response 200:**
```json
{
  "wellness_score": 78,
  "mood_distribution": { "great": 8, "good": 15, "okay": 5, "low": 2, "terrible": 1 },
  "weekly_trend": [{ "day": "Mon", "avg_score": 3.8 }, ...],
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

**Query:** period (days, default: 30)

**Response 200:**
```json
{
  "avg_score": 3.8, "trend": "improving", "change_vs_last_period": 0.3,
  "happiest_day": "Friday", "lowest_day": "Monday",
  "day_of_week_scores": { "Mon": 3.5, "Fri": 4.3 }
}
```
""")
async def get_analytics(period: int = Query(30, ge=7, le=365), organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await WellnessService(db).get_analytics(current_user, period, organization_id)


# ===========================================================================
# PROGRAMS
# ===========================================================================

@router.post("/programs", status_code=201, summary="Create Wellness Program", description="""
**Purpose:** HR creates a wellness program (mental health support, fitness challenge, etc.)

**Access:** `org_admin`, `hr_admin`

**Request Body:**
```json
{ "name": "Mental Health Support", "description": "Free counseling sessions", "type": "ongoing" }
```
""")
async def create_program(data: ProgramRequest, organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await WellnessService(db).create_program(data.model_dump(), current_user, organization_id)


@router.get("/programs", summary="List Wellness Programs", description="""
**Purpose:** View wellness programs. Shows enrollment status for employees.

**Access:** All authenticated users

**Response 200:**
```json
{ "programs": [{ "name": "Mental Health Support", "total_participants": 18, "participation": 65, "is_enrolled": true }] }
```
""")
async def list_programs(organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_any)):
    return await WellnessService(db).list_programs(current_user, organization_id)


@router.post("/programs/{program_id}/enroll", summary="Enroll in Program", description="""
**Purpose:** Employee enrolls in a wellness program.

**Access:** `employee`
""")
async def enroll_program(program_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await WellnessService(db).enroll_program(program_id, current_user)


@router.delete("/programs/{program_id}/enroll", summary="Unenroll from Program", description="""
**Purpose:** Employee unenrolls from a wellness program.

**Access:** `employee`
""")
async def unenroll_program(program_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await WellnessService(db).unenroll_program(program_id, current_user)
