from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.announcements.schema import (
    AnnouncementCreateRequest, AnnouncementUpdateRequest, AnnouncementListResponse
)
from app.v1.announcements.service import AnnouncementService

router = APIRouter()

def _hr(u: dict = Depends(get_current_user)):
    if u.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return u

def _any(u: dict = Depends(get_current_user)):
    return u


@router.post("/", status_code=201, summary="Create Announcement", description="""
**Purpose:** HR creates a new announcement visible to all employees or specific departments.

**Access:** `org_admin`, `hr_admin`

**Request Body:**
```json
{
  "title": "Office Closed on July 4th",
  "content": "The office will remain closed on account of Independence Day.",
  "type": "general",
  "priority": "normal",
  "target_departments": [],
  "is_pinned": false,
  "expires_at": "2025-07-05"
}
```

| Field | Required | Notes |
|---|---|---|
| title | ✅ | Announcement title |
| content | ✅ | Full body text |
| type | ❌ | general / urgent / event / policy / celebration |
| priority | ❌ | low / normal / high |
| target_departments | ❌ | [] = all employees. Otherwise list of department names |
| is_pinned | ❌ | Pinned stay at top |
| expires_at | ❌ | YYYY-MM-DD, auto-hides after this date |

**Response 201:** Created announcement with read_count and total_recipients.
""")
async def create(data: AnnouncementCreateRequest, organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AnnouncementService(db).create(data, current_user, organization_id)


@router.get("/", response_model=AnnouncementListResponse, summary="List Announcements", description="""
**Purpose:** Get announcements. Employees see only those targeted to their department or all. HR sees everything.

**Access:** All authenticated users

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| page | int | Page (default: 1) |
| limit | int | Items per page (default: 20, max: 50) |
| type | string | general / urgent / event / policy / celebration |
| is_pinned | string | "true" to filter pinned only |
| search | string | Search title/content |

**Response includes `is_read` field** — tells each employee if they've read it.
""")
async def get_list(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=50),
    type: Optional[str] = Query(None), is_pinned: Optional[str] = Query(None),
    search: Optional[str] = Query(None), department: Optional[str] = Query(None, description="Filter by target department"),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AnnouncementService(db).get_list(current_user, page, limit, type, is_pinned, search, department, organization_id)


@router.get("/unread-count", summary="Unread Announcements Count", description="""
**Purpose:** Get count of unread announcements for badge display.

**Access:** All authenticated users

**Response 200:** `{ "unread_count": 3 }`
""")
async def unread_count(db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AnnouncementService(db).unread_count(current_user)


@router.get("/{announcement_id}", summary="Get Announcement Detail", description="""
**Purpose:** Get full announcement. Auto-marks as read for the requesting user.

**Access:** All authenticated users
""")
async def get_by_id(announcement_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AnnouncementService(db).get_by_id(announcement_id, current_user)


@router.put("/{announcement_id}", summary="Update Announcement", description="""
**Purpose:** Edit an existing announcement.

**Access:** `org_admin`, `hr_admin`

**Request Body (all optional):**
```json
{ "title": "Updated", "content": "...", "type": "urgent", "priority": "high", "is_pinned": true, "expires_at": null }
```
""")
async def update(data: AnnouncementUpdateRequest, announcement_id: str = Path(...),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AnnouncementService(db).update(announcement_id, data, current_user)


@router.delete("/{announcement_id}", summary="Delete Announcement", description="""
**Purpose:** Soft-delete an announcement.

**Access:** `org_admin`, `hr_admin`

**Response 200:** `{ "message": "Announcement deleted successfully" }`
""")
async def delete(announcement_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await AnnouncementService(db).delete(announcement_id, current_user)


@router.patch("/{announcement_id}/read", summary="Mark as Read", description="""
**Purpose:** Manually mark an announcement as read (if not auto-marked by detail view).

**Access:** All authenticated users
""")
async def mark_read(announcement_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_any)):
    return await AnnouncementService(db).mark_read(announcement_id, current_user)
