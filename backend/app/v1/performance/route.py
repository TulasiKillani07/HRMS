from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.performance.schema import *
from app.v1.performance.service import PerformanceService

router = APIRouter()


def _require_hr_access(current_user: dict = Depends(get_current_user)):
    """Require HR/admin access"""
    if current_user.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


def _require_any(current_user: dict = Depends(get_current_user)):
    """Any authenticated user"""
    return current_user


# ---------------------------------------------------------------------------
# Performance Cycles
# ---------------------------------------------------------------------------

@router.post(
    "/cycles",
    response_model=CycleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Performance Review Cycle",
    description="""
**Purpose:** Create a new performance review cycle (quarter/year).

**Access:** org_admin, hr_admin

**Request Body:**
```json
{
  "name": "Q2 2025",
  "start_date": "2025-04-01",
  "end_date": "2025-06-30"
}
```

**Response 201:**
```json
{
  "id": "...",
  "name": "Q2 2025",
  "status": "active",
  "start_date": "2025-04-01",
  "end_date": "2025-06-30",
  "created_at": "..."
}
```

**Status values:** `draft` | `active` | `review` | `closed`

- `active` — Employees can work on OKRs
- `review` — Cycle closed, reviews in progress
- `closed` — All reviews finalized
"""
)
async def create_cycle(
    data: CycleCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await PerformanceService(db).create_cycle(data, current_user)


@router.get(
    "/cycles",
    response_model=CycleListResponse,
    summary="List Performance Cycles",
    description="""
**Purpose:** Get all performance cycles in the organization.

**Access:** org_admin, hr_admin, employee

**Query Parameters:**
- `status` (optional): Filter by status (active | review | closed)

**Response 200:**
```json
{
  "cycles": [
    {
      "id": "...",
      "name": "Q2 2025",
      "status": "active",
      "start_date": "2025-04-01",
      "end_date": "2025-06-30"
    }
  ],
  "total": 4
}
```
"""
)

async def get_cycles(
    status: Optional[str] = Query(None, description="Filter by status"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await PerformanceService(db).get_cycles(current_user, status)


@router.put(
    "/cycles/{cycle_id}",
    response_model=CycleResponse,
    summary="Update Performance Cycle",
    description="""
**Purpose:** Update cycle details or change status.

**Access:** org_admin, hr_admin

**Use cases:**
- Change cycle to `review` status when quarter ends
- Close cycle after all reviews completed

**Request Body:**
```json
{ "status": "review" }
```

**Errors:**
- `400` — Invalid cycle ID
- `404` — Cycle not found
"""
)
async def update_cycle(
    data: CycleUpdateRequest,
    cycle_id: str = Path(..., description="Cycle MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await PerformanceService(db).update_cycle(cycle_id, data, current_user)


# ---------------------------------------------------------------------------
# OKRs
# ---------------------------------------------------------------------------

@router.post(
    "/okrs",
    response_model=OKRResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create OKR for Employee",
    description="""
**Purpose:** Create Objectives & Key Results for an employee.

**Access:**
- `org_admin`, `hr_admin` — can assign OKRs to any employee (must supply `employee_id`)
- `employee` — can create their own OKR (employee_id auto-inferred)

**Request Body:**
```json
{
  "cycle_id": "ObjectId",
  "employee_id": "ObjectId",
  "objectives": [
    {
      "title": "Improve platform stability",
      "description": "Reduce bugs and improve uptime",
      "weight": 60,
      "key_results": [
        { "title": "Reduce bugs to <5/month", "target": 5, "unit": "bugs/month" },
        { "title": "99.9% uptime", "target": 99.9, "unit": "%" }
      ]
    }
  ]
}
```

**Response 201:**
```json
{
  "id": "...",
  "employee_name": "Rahul Verma",
  "overall_progress": 0,
  "status": "draft"
}
```

**Progress calculation:**
- Each KR progress = `(current / target) × 100`
- Objective progress = average of its KRs
- Overall progress = weighted average of objectives
"""
)
async def create_okr(
    data: OKRCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await PerformanceService(db).create_okr(data, current_user)



@router.get(
    "/okrs",
    response_model=OKRListResponse,
    summary="List OKRs",
    description="""
**Purpose:** Get OKRs with filters.

**Access:**
- `org_admin`, `hr_admin` — see all OKRs in organization
- `employee` — see only their own OKR

**Query Parameters:**
- `cycle_id` (optional): Filter by cycle
- `employee_id` (optional): Filter by employee (HR only)
- `department` (optional): Filter by department
- `status` (optional): Filter by status
- `page` (default: 1)
- `limit` (default: 10, max: 100)

**Response 200:**
```json
{
  "okrs": [
    {
      "id": "...",
      "employee_name": "Rahul Verma",
      "department": "Engineering",
      "overall_progress": 87,
      "status": "in_progress",
      "objectives_count": 2,
      "cycle_name": "Q2 2025"
    }
  ],
  "total": 12,
  "page": 1,
  "pages": 2
}
```
"""
)
async def get_okrs(
    cycle_id: Optional[str] = Query(None),
    employee_id: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await PerformanceService(db).get_okrs(
        current_user, page, limit, cycle_id, employee_id, department, status
    )


@router.get(
    "/okrs/{okr_id}",
    response_model=OKRResponse,
    summary="Get Full OKR Details",
    description="""
**Purpose:** Get complete OKR with all objectives and key results.

**Access:**
- `org_admin`, `hr_admin` — any OKR
- `employee` — own OKR only

**Response 200:** Full OKR object with nested objectives and key results.
"""
)
async def get_okr(
    okr_id: str = Path(..., description="OKR MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await PerformanceService(db).get_okr_by_id(okr_id, current_user)


@router.put(
    "/okrs/{okr_id}",
    response_model=OKRResponse,
    summary="Update OKR",
    description="""
**Purpose:** Update OKR objectives or key result progress.

**Access:**
- `org_admin`, `hr_admin` — any OKR
- `employee` — own OKR only

**Use cases:**

**1. Update KR progress:**
```json
{
  "objectives": [
    {
      "id": "existing-uuid",
      "key_results": [
        { "id": "existing-uuid", "current": 3 }
      ]
    }
  ]
}
```

**2. Add new objective:**
```json
{
  "objectives": [
    {
      "title": "New goal",
      "weight": 20,
      "key_results": [...]
    }
  ]
}
```

**3. Change status:**
```json
{ "status": "in_progress" }
```

Progress auto-recalculates after each update.
"""
)
async def update_okr(
    data: OKRUpdateRequest,
    okr_id: str = Path(..., description="OKR MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await PerformanceService(db).update_okr(okr_id, data, current_user)


@router.delete(
    "/okrs/{okr_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete OKR (Draft Only)",
    description="""
**Purpose:** Delete an OKR that is still in draft status.

**Access:** org_admin, hr_admin

**Only works if status = `draft`**

**Errors:**
- `400` — OKR is not in draft status
- `404` — OKR not found
"""
)
async def delete_okr(
    okr_id: str = Path(..., description="OKR MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await PerformanceService(db).delete_okr(okr_id, current_user)



# ---------------------------------------------------------------------------
# Performance Reviews
# ---------------------------------------------------------------------------

@router.post(
    "/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Performance Review",
    description="""
**Purpose:** Submit self-review or manager review.

**Access:**
- `employee` — submits self-review (employee_id auto-inferred)
- `org_admin`, `hr_admin` — submits manager review (must supply employee_id)

**Self-review (by employee):**
```json
{
  "cycle_id": "ObjectId",
  "self_rating": 4.0,
  "self_comments": "Good quarter overall",
  "competencies": {
    "communication": 4,
    "leadership": 3,
    "problem_solving": 5,
    "teamwork": 4,
    "technical": 5
  }
}
```

**Manager review (by HR/admin):**
```json
{
  "cycle_id": "ObjectId",
  "employee_id": "ObjectId",
  "manager_rating": 4.5,
  "manager_comments": "Excellent work on stability"
}
```

**Response 201:**
```json
{
  "id": "...",
  "employee_name": "Rahul Verma",
  "self_rating": 4.0,
  "manager_rating": 4.5,
  "final_rating": 4.35,
  "status": "manager_reviewed"
}
```

**Final rating calculation:** `(self_rating × 0.3) + (manager_rating × 0.7)`

**Status progression:**
- `pending` → `self_reviewed` (after employee submits)
- `self_reviewed` → `manager_reviewed` (after manager submits)
"""
)
async def submit_review(
    data: ReviewSubmitRequest,
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await PerformanceService(db).submit_review(data, current_user)


@router.get(
    "/reviews",
    response_model=ReviewListResponse,
    summary="List Performance Reviews",
    description="""
**Purpose:** Get reviews with filters.

**Access:**
- `org_admin`, `hr_admin` — all reviews in organization
- `employee` — own review only

**Query Parameters:**
- `cycle_id` (optional)
- `employee_id` (optional, HR only)
- `status` (optional): pending | self_reviewed | manager_reviewed | closed

**Response 200:**
```json
{
  "reviews": [
    {
      "id": "...",
      "employee_name": "Rahul Verma",
      "department": "Engineering",
      "self_rating": 4.0,
      "manager_rating": 4.5,
      "final_rating": 4.35,
      "status": "manager_reviewed"
    }
  ],
  "total": 12
}
```
"""
)
async def get_reviews(
    cycle_id: Optional[str] = Query(None),
    employee_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await PerformanceService(db).get_reviews(current_user, cycle_id, employee_id, status)


@router.get(
    "/reviews/{review_id}",
    summary="Get Review Details",
    description="""
**Purpose:** Get full review with all ratings, comments, and competencies.

**Access:**
- `org_admin`, `hr_admin` — any review
- `employee` — own review only
"""
)
async def get_review(
    review_id: str = Path(..., description="Review MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await PerformanceService(db).get_review_by_id(review_id, current_user)



# ---------------------------------------------------------------------------
# Analytics & Leaderboard
# ---------------------------------------------------------------------------

@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Top Performers Leaderboard",
    description="""
**Purpose:** Get ranked list of top performers.

**Access:** org_admin, hr_admin

**Query Parameters:**
- `cycle_id` (optional): Filter by specific cycle
- `department` (optional): Filter by department
- `limit` (default: 10): Number of top performers to show

**Response 200:**
```json
{
  "leaderboard": [
    {
      "rank": 1,
      "employee_name": "Vikram Singh",
      "employee_id": "...",
      "department": "Engineering",
      "final_rating": 4.8,
      "okr_progress": 95
    },
    {
      "rank": 2,
      "employee_name": "Rahul Verma",
      "department": "Engineering",
      "final_rating": 4.35,
      "okr_progress": 90
    }
  ]
}
```

**Ranking:** Based on `final_rating` (descending).
"""
)
async def get_leaderboard(
    cycle_id: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await PerformanceService(db).get_leaderboard(current_user, cycle_id, department, limit)


@router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    summary="Performance Distribution & Analytics",
    description="""
**Purpose:** Get performance analytics for a cycle.

**Access:** org_admin, hr_admin

**Query Parameters:**
- `cycle_id` (optional): Filter by specific cycle

**Response 200:**
```json
{
  "distribution": {
    "exceeds": 3,
    "meets": 8,
    "below": 1
  },
  "department_avg": {
    "Engineering": 4.2,
    "Design": 3.9,
    "Marketing": 3.5
  },
  "avg_rating": 4.1,
  "total_reviewed": 12
}
```

**Rating categories:**
- `exceeds` — rating >= 4.5
- `meets` — rating 3.0 - 4.49
- `below` — rating < 3.0
"""
)
async def get_analytics(
    cycle_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await PerformanceService(db).get_analytics(current_user, cycle_id)
