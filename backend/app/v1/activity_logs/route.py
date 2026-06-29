from fastapi import APIRouter, Depends, Query, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.activity_logs.service import ActivityLogService

router = APIRouter()


def _require_admin(u: dict = Depends(get_current_user)):
    if u.get("role") not in ("superadmin", "org_admin"):
        raise HTTPException(status_code=403, detail="Only superadmin and org_admin")
    return u


@router.get(
    "/",
    summary="Get Activity Logs",
    description="""
**Purpose:** View activity logs — all actions performed in the system.

**Access:**
- `superadmin` — sees all logs across all organizations
- `org_admin` — sees logs for their organization only

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| page | int | Default 1 |
| limit | int | Default 50, max 100 |
| module | string | Filter: employee / leave / attendance / department / organization / auth / announcement / document / wellness / performance |
| action | string | Filter: created / updated / deleted / approved / rejected / login / logout |
| user_id | string | Filter by specific user |
| user_role | string | Filter: superadmin / org_admin / hr_admin / employee |
| from_date | string | From date (YYYY-MM-DD) |
| to_date | string | To date (YYYY-MM-DD) |
| search | string | Search in description |

**Response 200:**
```json
{
  "logs": [
    {
      "id": "65log...",
      "user_name": "Pranavi",
      "user_role": "hr_admin",
      "action": "created",
      "module": "employee",
      "description": "Created employee Rahul Verma (EMP001)",
      "target_id": "65emp...",
      "target_type": "employee",
      "created_at": "2025-07-15T09:05:00"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 50,
  "pages": 3
}
```
""",
)
async def get_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    module: Optional[str] = Query(None, description="employee|leave|attendance|department|organization|auth|announcement|document|wellness|performance"),
    action: Optional[str] = Query(None, description="created|updated|deleted|approved|rejected|login|logout"),
    user_id: Optional[str] = Query(None),
    user_role: Optional[str] = Query(None, description="superadmin|org_admin|hr_admin|employee"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    search: Optional[str] = Query(None, description="Search description"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    return await ActivityLogService(db).get_logs(
        current_user, page, limit, module, action, user_id, user_role, from_date, to_date, search
    )


@router.get(
    "/stats",
    summary="Activity Log Stats",
    description="""
**Purpose:** Quick stats for dashboard — today's activity count by module.

**Access:** `superadmin`, `org_admin`

**Response 200:**
```json
{
  "total_today": 45,
  "total_all": 1250,
  "today_by_module": { "employee": 12, "leave": 8, "attendance": 20, "auth": 5 }
}
```
""",
)
async def get_stats(
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    return await ActivityLogService(db).get_log_stats(current_user)
