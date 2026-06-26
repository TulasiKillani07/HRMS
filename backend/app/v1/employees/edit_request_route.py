from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.employees.edit_request_schema import (
    EditRequestCreateSchema, EditRequestApproveSchema,
    EditRequestRejectSchema, EditRequestResponse,
    EditRequestListResponse,
)
from app.v1.employees.edit_request_service import EditRequestService

router = APIRouter()


def _require_hr(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


def _require_employee(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Only employees can use this endpoint")
    return current_user


def _require_any(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post(
    "/",
    response_model=EditRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request Edit Permission",
    description="""
**Purpose:** Employee requests permission to edit a section of their profile after onboarding is complete.
The request goes to all HR admins in the organization. Any one HR can approve.

**Access:** `employee` only

**Editable Sections:**
`personal_details` | `address` | `emergency_contact` | `bank_details` | `government_ids` | `education` | `experience`

**Request Body:**
```json
{
  "section": "bank_details",
  "reason": "Changed bank account, need to update IFSC and account number"
}
```

**Flow:**
1. Employee submits edit request
2. All HR admins see it in their pending requests
3. Any HR approves (with time window, default 3 hours)
4. Employee edits and saves within the time window
5. After window expires, edit is no longer possible

**Errors:**
- `400` — Already has pending/active request for this section
- `403` — Only employees can request
- `404` — Employee record not found
""",
)
async def create_edit_request(
    data: EditRequestCreateSchema,
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee)
):
    return await EditRequestService(db).create_edit_request(data, current_user)


@router.get(
    "/",
    response_model=EditRequestListResponse,
    summary="List Edit Requests",
    description="""
**Purpose:** List profile edit requests.

**Access:**
- `employee` — sees their own requests
- `org_admin`, `hr_admin` — sees all in organization

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| page | int | Page number (default: 1) |
| limit | int | Items per page (default: 10) |
| status | string | Filter: pending / approved / rejected / expired |
| employee_id | string | HR: filter by employee |
""",
)
async def list_edit_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="pending | approved | rejected | expired"),
    employee_id: Optional[str] = Query(None, description="HR: filter by employee"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await EditRequestService(db).get_edit_requests(
        current_user, page, limit, status, employee_id
    )


@router.patch(
    "/{request_id}/approve",
    response_model=EditRequestResponse,
    summary="Approve Edit Request",
    description="""
**Purpose:** HR approves an employee's edit request. Employee can then edit anytime.
The response shows who approved it. A notification is sent to the employee.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `request_id` — MongoDB ObjectId

**Request Body:** None required.

**Response 200:** Updated request with `approved_by_name`, `approved_at`

**Errors:**
- `400` — Not in pending status
- `404` — Request not found
""",
)
async def approve_edit_request(
    request_id: str = Path(..., description="Edit request MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr)
):
    return await EditRequestService(db).approve_edit_request(request_id, current_user)


@router.patch(
    "/{request_id}/reject",
    response_model=EditRequestResponse,
    summary="Reject Edit Request",
    description="""
**Purpose:** HR rejects an employee's edit request with a reason.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `request_id` — MongoDB ObjectId

**Request Body:**
```json
{ "reason": "Bank details can only be changed during salary processing window" }
```

**Errors:**
- `400` — Not in pending status
- `404` — Request not found
""",
)
async def reject_edit_request(
    data: EditRequestRejectSchema,
    request_id: str = Path(..., description="Edit request MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr)
):
    return await EditRequestService(db).reject_edit_request(request_id, data.reason, current_user)


@router.put(
    "/{request_id}/save",
    summary="Save Edit (Within Time Window)",
    description="""
**Purpose:** Employee saves their profile edit within the approved time window.
The system records who approved the edit and when it was completed.

**Access:** `employee` only

**Path Parameter:** `request_id` — The approved edit request MongoDB ObjectId

**Request Body:** Section data (same format as onboarding submission)

**Example (bank_details):**
```json
{
  "account_number": "9876543210",
  "ifsc": "SBIN0001234",
  "bank_name": "SBI",
  "branch": "Gachibowli",
  "account_type": "savings"
}
```

**Example (address):**
```json
{
  "current": { "line1": "New Address", "city": "Bangalore", "state": "Karnataka", "pincode": "560001" },
  "permanent": { "line1": "Home", "city": "Vizag", "state": "AP", "pincode": "530002" }
}
```

**Response 200:**
```json
{
  "message": "Section 'bank_details' updated successfully",
  "section": "bank_details",
  "edit_request_id": "65req...",
  "approved_by": "Pranavi",
  "completed_at": "2025-07-15T12:30:00"
}
```

**Errors:**
- `400` — Time window expired
- `404` — No approved edit request found
""",
)
async def save_edit(
    body: dict,
    request_id: str = Path(..., description="Approved edit request MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee)
):
    return await EditRequestService(db).save_edit(request_id, body, current_user)


@router.get(
    "/can-edit/{section}",
    summary="Check Edit Permission",
    description="""
**Purpose:** Check if employee currently has permission to edit a specific section.
Frontend calls this to enable/disable edit buttons.

**Access:** `employee`

**Path Parameter:** `section` — Section name

**Response 200 (has permission):**
```json
{
  "can_edit": true,
  "request_id": "65req...",
  "section": "bank_details",
  "approved_by": "Pranavi",
  "edit_allowed_until": "2025-07-15T15:00:00",
  "time_remaining_minutes": 145
}
```

**Response 200 (no permission):**
```json
{
  "can_edit": false,
  "section": "bank_details",
  "message": "No active edit permission. Submit a new request."
}
```
""",
)
async def can_edit_section(
    section: str = Path(..., description="Section name to check"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee)
):
    return await EditRequestService(db).can_edit_section(section, current_user)
