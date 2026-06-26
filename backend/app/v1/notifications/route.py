from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.notifications.service import NotificationService

router = APIRouter()


@router.get(
    "/",
    summary="Get Notifications",
    description="""
**Purpose:** Get notifications for the current logged-in user.

**Access:** All authenticated users

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| page | int | Page number (default: 1) |
| limit | int | Items per page (default: 20) |
| is_read | string | Filter: "true" or "false" |
| category | string | Filter: general / edit_request / leave / onboarding / performance |

**Response 200:**
```json
{
  "notifications": [
    {
      "id": "65notif...",
      "title": "Edit Request",
      "message": "Rahul Verma wants to edit bank_details",
      "type": "action",
      "category": "edit_request",
      "reference_id": "65req...",
      "reference_type": "edit_request",
      "is_read": false,
      "created_at": "2025-07-15T09:00:00"
    }
  ],
  "total": 5,
  "unread_count": 3,
  "page": 1,
  "limit": 20,
  "pages": 1
}
```
""",
)
async def get_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    is_read: Optional[str] = Query(None, description="true | false"),
    category: Optional[str] = Query(None, description="general | edit_request | leave | onboarding | performance"),
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    return await NotificationService(db).get_my_notifications(current_user, page, limit, is_read, category)


@router.get(
    "/unread-count",
    summary="Get Unread Count",
    description="Returns the unread notification count for badge display.",
)
async def get_unread_count(
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    return await NotificationService(db).get_unread_count(current_user)


@router.put(
    "/{notification_id}/read",
    summary="Mark As Read",
    description="Mark a single notification as read.",
)
async def mark_as_read(
    notification_id: str = Path(..., description="Notification MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    return await NotificationService(db).mark_as_read(notification_id, current_user)


@router.put(
    "/read-all",
    summary="Mark All As Read",
    description="Mark all unread notifications as read for the current user.",
)
async def mark_all_as_read(
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    return await NotificationService(db).mark_all_as_read(current_user)


@router.delete(
    "/clear-all",
    summary="Clear All Notifications",
    description="Delete all notifications for the current user.",
)
async def clear_all_notifications(
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    return await NotificationService(db).clear_all_notifications(current_user)


@router.delete(
    "/{notification_id}",
    summary="Delete Notification",
    description="Delete a single notification.",
)
async def delete_notification(
    notification_id: str = Path(..., description="Notification MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    return await NotificationService(db).delete_notification(notification_id, current_user)
