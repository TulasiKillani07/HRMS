from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.leaves.schema import (
    LeaveTypeCreateRequest, LeaveTypeUpdateRequest,
    LeaveConfigurationResponse, LeaveTypeResponse,
    LeaveApplyRequest, LeaveRejectRequest,
    LeaveRequestResponse, LeaveListResponse,
    LeaveBalanceResponse, BalanceAdjustRequest,
    BalanceAdjustResponse, BalanceAdjustmentHistoryResponse,
    LeaveForwardRequest, LeaveCommentRequest,
    WorkflowCreateRequest, WorkflowUpdateRequest, WorkflowResponse,
)
from app.v1.leaves.service import LeaveService

router = APIRouter()


def _require_hr_access(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


def _require_employee_or_hr(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("employee", "superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


# ===========================================================================
# LEAVE CONFIGURATION CRUD
# ===========================================================================

@router.get(
    "/configurations",
    response_model=LeaveConfigurationResponse,
    summary="Get Leave Configuration",
    description="""
**Purpose:** Get the leave policy configuration for the organization.
If no configuration exists for the current year, one is auto-created with default leave types.

**Access:** All authenticated users

**Default Leave Types (auto-created, fixed — cannot be edited or deleted):**
- Casual Leave (CL) — Monthly accrual, 1/month, 12/year. Converts to LOP when exhausted.
- Sick Leave (SL) — Monthly accrual, 0.5/month, 6/year. Converts to LOP when exhausted.
- Loss of Pay (LOP) — Unlimited, unpaid. Auto-applied when other balances are zero.

**Additional config fields:**
- `missed_attendance_threshold` — If employee misses X check-in/outs per month → counted as LOP (default: 3)
- `auto_lop_on_missed_attendance` — Enable/disable the above rule (default: true)

**HR can add custom leave types** (e.g., Work From Home, Comp Off) — those CAN be edited/deleted.

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| organization_id | string | Required for superadmin |
| year | int | Year to fetch config for (default: current year) |

**Response 200:** Full configuration with all leave types.
""",
)
async def get_leave_configuration(
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    year: Optional[int] = Query(None, description="Year (default: current year)"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    return await LeaveService(db).get_leave_configuration(current_user, organization_id, year)


@router.post(
    "/configurations/leave-types",
    response_model=LeaveTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Leave Type",
    description="""
**Purpose:** Add a new leave type to the organization's leave configuration.

**Access:** `org_admin`, `hr_admin`

**Request Body:**
```json
{
  "name": "Work From Home",
  "code": "WFH",
  "days_per_year": 24,
  "is_paid": true,
  "carry_forward": false,
  "max_carry_forward_days": 0,
  "applicable_after_days": 0,
  "description": "Remote work days"
}
```

| Field | Required | Notes |
|---|---|---|
| name | ✅ | Unique within org config |
| code | ✅ | Short code (e.g., WFH), unique |
| days_per_year | ❌ | Default 0. Use -1 for unlimited |
| is_paid | ❌ | Default true |
| carry_forward | ❌ | Default false |
| max_carry_forward_days | ❌ | Default 0 |
| applicable_after_days | ❌ | Default 0 (available immediately) |
| description | ❌ | Optional description |

**Errors:**
- `400` — Duplicate code or name
""",
)
async def add_leave_type(
    data: LeaveTypeCreateRequest,
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    year: Optional[int] = Query(None, description="Year (default: current year)"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).add_leave_type(data, current_user, organization_id, year)


@router.put(
    "/configurations/leave-types/{leave_type_id}",
    response_model=LeaveTypeResponse,
    summary="Update Leave Type",
    description="""
**Purpose:** Update an existing leave type in the organization's configuration.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `leave_type_id` — UUID of the leave type (from GET configuration response)

**Request Body (all fields optional):**
```json
{
  "name": "Casual Leave Updated",
  "days_per_year": 15,
  "carry_forward": true,
  "max_carry_forward_days": 5,
  "is_active": false
}
```

| Field | Notes |
|---|---|
| name | New name (must be unique) |
| code | New code (must be unique) |
| days_per_year | New allowance |
| is_paid | true/false |
| carry_forward | true/false |
| max_carry_forward_days | Max days to carry |
| applicable_after_days | Days after joining |
| description | Updated description |
| is_active | Set false to deactivate without deleting |

**Errors:**
- `400` — Duplicate code/name, no fields provided
- `404` — Leave type not found
""",
)
async def update_leave_type(
    data: LeaveTypeUpdateRequest,
    leave_type_id: str = Path(..., description="Leave type UUID"),
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    year: Optional[int] = Query(None, description="Year (default: current year)"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).update_leave_type(
        leave_type_id, data, current_user, organization_id, year
    )


@router.delete(
    "/configurations/leave-types/{leave_type_id}",
    summary="Delete Leave Type",
    description="""
**Purpose:** Delete a leave type from the configuration.
Cannot delete if active leave requests exist for this type — deactivate instead.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `leave_type_id` — UUID of the leave type

**Response 200:**
```json
{ "message": "Leave type 'Work From Home' deleted successfully" }
```

**Errors:**
- `400` — Active leave requests exist for this type
- `404` — Leave type not found
""",
)
async def delete_leave_type(
    leave_type_id: str = Path(..., description="Leave type UUID"),
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    year: Optional[int] = Query(None, description="Year (default: current year)"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).delete_leave_type(
        leave_type_id, current_user, organization_id, year
    )


# ===========================================================================
# LEAVE REQUESTS
# ===========================================================================

@router.post(
    "/apply",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for Leave",
    description="""
**Purpose:** Employee applies for leave. HR can also apply on behalf of an employee.

**Access:**
- `employee` — applies for self (no employee_id needed)
- `org_admin`, `hr_admin` — applies on behalf (must pass employee_id)

**Request Body:**
```json
{
  "leave_type_code": "CL",
  "start_date": "2025-07-10",
  "end_date": "2025-07-11",
  "reason": "Family function",
  "is_half_day": false
}
```

**Half-day leave:**
```json
{
  "leave_type_code": "CL",
  "start_date": "2025-07-10",
  "end_date": "2025-07-10",
  "reason": "Doctor appointment",
  "is_half_day": true,
  "half_day_type": "first_half"
}
```

**Validations:**
- Leave type must exist and be active
- Dates must be valid (end >= start)
- No overlapping leaves
- Sufficient balance (except unlimited types)
- Half-day must be single day with half_day_type specified

**Response 201:** Created leave request with status "pending"

**Errors:**
- `400` — Invalid dates, overlap, insufficient balance, invalid leave type
- `404` — Employee not found
""",
)
async def apply_leave(
    data: LeaveApplyRequest,
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    return await LeaveService(db).apply_leave(data, current_user, organization_id)


@router.get(
    "/",
    response_model=LeaveListResponse,
    summary="List Leave Requests",
    description="""
**Purpose:** List leave requests with filters. HR sees all in org, employee sees own.

**Access:**
- `employee` — sees only their own leave requests
- `org_admin`, `hr_admin` — sees all in organization

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| organization_id | string | Required for superadmin |
| page | int | Page number (default: 1) |
| limit | int | Items per page (default: 10, max: 100) |
| status | string | Filter: pending / approved / rejected / cancelled |
| leave_type | string | Filter by leave type code (CL, SL, etc.) |
| employee_id | string | HR: filter by specific employee |
| department | string | HR: filter by department |
| from_date | string | Filter leaves starting from this date (YYYY-MM-DD) |
| to_date | string | Filter leaves ending up to this date (YYYY-MM-DD) |
| search | string | Search by employee name or leave type |

**Response 200:** Paginated list of leave requests.
""",
)
async def get_leaves(
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="pending | approved | rejected | cancelled"),
    leave_type: Optional[str] = Query(None, description="Leave type code"),
    employee_id: Optional[str] = Query(None, description="Filter by employee"),
    department: Optional[str] = Query(None, description="Filter by department"),
    from_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Search employee name or leave type"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    return await LeaveService(db).get_leaves(
        current_user, page, limit, status, leave_type, employee_id,
        department, organization_id, from_date, to_date, search
    )


@router.get(
    "/balance",
    response_model=LeaveBalanceResponse,
    summary="Get Leave Balance",
    description="""
**Purpose:** Get leave balance for an employee for the current year.
Shows total, used, pending, and available balance for each leave type.

**Access:**
- `employee` — sees their own balance
- `org_admin`, `hr_admin` — must pass `?employee_id=<id>`

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| employee_id | string | Required for HR. MongoDB ObjectId of employee |
| organization_id | string | Required for superadmin |

**Response 200:**
```json
{
  "employee_id": "65abc...",
  "employee_name": "Rahul Verma",
  "year": 2025,
  "balances": [
    { "leave_type_code": "CL", "leave_type_name": "Casual Leave", "total": 12, "used": 3, "balance": 9, "pending": 1 },
    { "leave_type_code": "SL", "leave_type_name": "Sick Leave", "total": 6, "used": 0, "balance": 6, "pending": 0 },
    { "leave_type_code": "EL", "leave_type_name": "Earned Leave", "total": 15, "used": 5, "balance": 10, "pending": 2 }
  ]
}
```

**Note:** `total: -1` means unlimited (e.g., Comp Off).
""",
)
async def get_leave_balance(
    employee_id: Optional[str] = Query(None, description="Required for HR"),
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    return await LeaveService(db).get_leave_balance(current_user, employee_id, organization_id)


# ===========================================================================
# APPROVAL WORKFLOW CONFIGURATION (placed before /{leave_id} to avoid conflicts)
# ===========================================================================

@router.get(
    "/workflow",
    response_model=WorkflowResponse,
    summary="Get Approval Workflow",
    description="""
**Purpose:** Get the leave approval workflow configuration for the organization.
If none exists, a default workflow is auto-created:
- Level 1: Reporting Manager (can skip if not assigned)
- Level 2: HR Admin

**Access:** All authenticated users

**Default Workflow (auto-created):**
```
Employee → Reporting Manager → HR Admin
```

**Response 200:**
```json
{
  "id": "65wf...",
  "organization_id": "65abc...",
  "name": "Default Workflow",
  "levels": [
    { "level": 1, "approver_type": "reporting_manager", "approver_id": null, "can_skip": true },
    { "level": 2, "approver_type": "hr_admin", "approver_id": null, "can_skip": false }
  ],
  "auto_approval": { "enabled": false, "max_days": 0, "leave_types": null },
  "is_active": true
}
```

**Approver Types:**
| Type | Description |
|------|-------------|
| `reporting_manager` | Employee's assigned reporting manager |
| `hr_admin` | Any HR admin in the organization |
| `org_admin` | Organization admin |
| `specific_user` | A specific user (requires `approver_id`) |
""",
)
async def get_workflow(
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    return await LeaveService(db).get_workflow(current_user, organization_id)


@router.post(
    "/workflow",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Approval Workflow",
    description="""
**Purpose:** Create a new approval workflow. Deactivates any existing active workflow.

**Access:** `org_admin`, `hr_admin`

**Request Body:**
```json
{
  "name": "Standard 2-Level Approval",
  "levels": [
    { "level": 1, "approver_type": "reporting_manager", "can_skip": true },
    { "level": 2, "approver_type": "hr_admin", "can_skip": false }
  ],
  "auto_approval": {
    "enabled": true,
    "max_days": 1,
    "leave_types": ["CL"]
  }
}
```

**Example: Simple Manager-only workflow:**
```json
{
  "name": "Manager Only",
  "levels": [
    { "level": 1, "approver_type": "reporting_manager", "can_skip": false }
  ]
}
```

**Example: 3-level workflow with specific user:**
```json
{
  "name": "3-Level Approval",
  "levels": [
    { "level": 1, "approver_type": "reporting_manager", "can_skip": true },
    { "level": 2, "approver_type": "specific_user", "approver_id": "65user...", "can_skip": false },
    { "level": 3, "approver_type": "org_admin", "can_skip": false }
  ]
}
```

**Auto Approval Rules:**
- `enabled: true` — Enables auto-approval for qualifying leaves
- `max_days: 1` — Auto-approve if leave is ≤ 1 day
- `leave_types: ["CL"]` — Only auto-approve Casual Leave. Null = all types

**Errors:**
- `400` — Invalid approver_type, missing approver_id for specific_user
""",
)
async def create_workflow(
    data: WorkflowCreateRequest,
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).create_workflow(data, current_user, organization_id)


@router.put(
    "/workflow/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Update Approval Workflow",
    description="""
**Purpose:** Update an existing approval workflow.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `workflow_id` — MongoDB ObjectId

**Request Body (all fields optional):**
```json
{
  "name": "Updated Workflow",
  "levels": [
    { "level": 1, "approver_type": "reporting_manager", "can_skip": true },
    { "level": 2, "approver_type": "hr_admin", "can_skip": false }
  ],
  "auto_approval": { "enabled": true, "max_days": 2, "leave_types": null },
  "is_active": true
}
```

**Errors:**
- `400` — Invalid approver_type, no fields provided
- `404` — Workflow not found
""",
)
async def update_workflow(
    data: WorkflowUpdateRequest,
    workflow_id: str = Path(..., description="Workflow MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).update_workflow(workflow_id, data, current_user)


@router.delete(
    "/workflow/{workflow_id}",
    summary="Delete (Deactivate) Approval Workflow",
    description="""
**Purpose:** Deactivate an approval workflow. Does not delete data.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `workflow_id` — MongoDB ObjectId

**Response 200:**
```json
{ "message": "Workflow 'Standard 2-Level' deactivated successfully" }
```
""",
)
async def delete_workflow(
    workflow_id: str = Path(..., description="Workflow MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).delete_workflow(workflow_id, current_user)


@router.get(
    "/{leave_id}",
    response_model=LeaveRequestResponse,
    summary="Get Leave Request Detail",
    description="""
**Purpose:** Get full details of a single leave request.

**Access:**
- `employee` — can view only their own
- `org_admin`, `hr_admin` — can view any in org

**Path Parameter:** `leave_id` — MongoDB ObjectId of the leave request.

**Errors:**
- `400` — Invalid leave ID
- `404` — Leave request not found
""",
)
async def get_leave_by_id(
    leave_id: str = Path(..., description="Leave request MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    return await LeaveService(db).get_leave_by_id(leave_id, current_user)


@router.patch(
    "/{leave_id}/approve",
    response_model=LeaveRequestResponse,
    summary="Approve Leave Request",
    description="""
**Purpose:** HR approves a pending leave request.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `leave_id` — MongoDB ObjectId of the leave request.

**Request Body:** None required.

**Response 200:** Updated leave request with status "approved".

**Errors:**
- `400` — Leave is not in "pending" status
- `404` — Leave request not found
""",
)
async def approve_leave(
    leave_id: str = Path(..., description="Leave request MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).approve_leave(leave_id, current_user)


@router.patch(
    "/{leave_id}/reject",
    response_model=LeaveRequestResponse,
    summary="Reject Leave Request",
    description="""
**Purpose:** HR rejects a pending leave request with a reason.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `leave_id` — MongoDB ObjectId of the leave request.

**Request Body:**
```json
{ "reason": "Team is short-staffed this week, please reschedule" }
```

**Response 200:** Updated leave request with status "rejected".

**Errors:**
- `400` — Leave is not in "pending" status
- `404` — Leave request not found
""",
)
async def reject_leave(
    data: LeaveRejectRequest,
    leave_id: str = Path(..., description="Leave request MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).reject_leave(leave_id, data, current_user)


@router.patch(
    "/{leave_id}/cancel",
    response_model=LeaveRequestResponse,
    summary="Cancel Leave Request",
    description="""
**Purpose:** Cancel a leave request. Employee can cancel their own pending/approved leaves.
HR can cancel any leave in the organization.

**Access:**
- `employee` — can cancel only their own (pending or approved)
- `org_admin`, `hr_admin` — can cancel any

**Path Parameter:** `leave_id` — MongoDB ObjectId of the leave request.

**Request Body:** None required.

**Response 200:** Updated leave request with status "cancelled".

**Errors:**
- `400` — Leave is already rejected/cancelled
- `404` — Leave request not found
""",
)
async def cancel_leave(
    leave_id: str = Path(..., description="Leave request MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    return await LeaveService(db).cancel_leave(leave_id, current_user)


# ===========================================================================
# BALANCE MANAGEMENT (HR Actions)
# ===========================================================================

@router.post(
    "/balance/adjust",
    response_model=BalanceAdjustResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adjust Employee Leave Balance",
    description="""
**Purpose:** HR manually adjusts an employee's leave balance.
Used for crediting comp-offs, deducting penalties, or resetting balances.

**Access:** `org_admin`, `hr_admin`

**Actions:**
| Action | Description |
|--------|-------------|
| `credit` | Add extra days to employee's balance |
| `deduct` | Remove days from employee's balance |
| `reset` | Reset balance to policy default (remove all manual adjustments) |

**Request Body (Credit):**
```json
{
  "employee_id": "65emp001abc",
  "leave_type_code": "CL",
  "action": "credit",
  "days": 2,
  "reason": "Comp off for working on Saturday 12th July"
}
```

**Request Body (Deduct):**
```json
{
  "employee_id": "65emp001abc",
  "leave_type_code": "CL",
  "action": "deduct",
  "days": 1,
  "reason": "Unauthorized absence on 10th July"
}
```

**Request Body (Reset):**
```json
{
  "employee_id": "65emp001abc",
  "leave_type_code": "CL",
  "action": "reset",
  "days": 1,
  "reason": "Yearly balance reset"
}
```
> Note: For `reset`, the `days` field is ignored. All prior adjustments are neutralized.

**Response 201:**
```json
{
  "id": "65adj...",
  "employee_id": "65emp001abc",
  "employee_name": "Rahul Verma",
  "leave_type_code": "CL",
  "leave_type_name": "Casual Leave",
  "action": "credit",
  "days": 2,
  "reason": "Comp off for working on Saturday",
  "adjusted_by_name": "Pranavi",
  "new_balance": 14,
  "year": 2025,
  "created_at": "2025-07-15T09:00:00"
}
```

**Balance Calculation:**
`balance = (policy_days + credits - deductions) - approved_leaves`

**Errors:**
- `400` — Invalid action, insufficient balance for deduct, invalid leave type
- `404` — Employee not found
""",
)
async def adjust_balance(
    data: BalanceAdjustRequest,
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).adjust_balance(data, current_user, organization_id)


@router.get(
    "/balance/history",
    response_model=BalanceAdjustmentHistoryResponse,
    summary="Get Balance Adjustment History",
    description="""
**Purpose:** View all manual balance adjustments made for an employee in the current year.

**Access:** `org_admin`, `hr_admin`

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| employee_id | string | ✅ Required. Employee MongoDB ObjectId |
| leave_type_code | string | Optional. Filter by leave type |
| organization_id | string | Required for superadmin |

**Response 200:**
```json
{
  "adjustments": [
    {
      "id": "65adj...",
      "employee_name": "Rahul Verma",
      "leave_type_code": "CL",
      "leave_type_name": "Casual Leave",
      "action": "credit",
      "days": 2,
      "reason": "Comp off for weekend work",
      "adjusted_by_name": "Pranavi",
      "year": 2025,
      "created_at": "2025-07-15T09:00:00"
    }
  ],
  "total": 3
}
```
""",
)
async def get_balance_adjustments(
    employee_id: str = Query(..., description="Employee MongoDB ObjectId"),
    leave_type_code: Optional[str] = Query(None, description="Filter by leave type code"),
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).get_balance_adjustments(
        current_user, employee_id, leave_type_code, organization_id
    )


# ===========================================================================
# FORWARD & COMMENTS
# ===========================================================================

@router.patch(
    "/{leave_id}/forward",
    summary="Forward Leave Request",
    description="""
**Purpose:** Forward a pending leave request to another approver (e.g., reporting manager, HOD).
The leave remains in "pending" status but is assigned to the forwarded-to person.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `leave_id` — MongoDB ObjectId of the leave request.

**Request Body:**
```json
{
  "forward_to": "65user001abc",
  "notes": "Please review this 10-day leave request"
}
```

| Field | Required | Notes |
|---|---|---|
| forward_to | ✅ | User ID of the person to forward to |
| notes | ❌ | Notes for the approver |

**Response 200:** Updated leave request with forward information.

**Errors:**
- `400` — Leave is not pending, invalid user ID
- `404` — Leave or forward-to user not found
""",
)
async def forward_leave(
    data: LeaveForwardRequest,
    leave_id: str = Path(..., description="Leave request MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).forward_leave(
        leave_id, data.forward_to, data.notes or "", current_user
    )


@router.post(
    "/{leave_id}/comments",
    summary="Add Comment to Leave Request",
    description="""
**Purpose:** Add a comment to a leave request. HR can comment on any leave, 
employees can comment on their own. Used for requesting documents, 
clarifying reasons, or any communication around the leave.

**Access:**
- `employee` — can comment on their own leave requests
- `org_admin`, `hr_admin` — can comment on any leave in org

**Path Parameter:** `leave_id` — MongoDB ObjectId of the leave request.

**Request Body:**
```json
{
  "comment": "Please provide medical certificate for sick leave > 2 days"
}
```

**Response 200:** Updated leave request with comments array.

**Errors:**
- `400` — Invalid leave ID
- `404` — Leave request not found
""",
)
async def add_comment(
    data: LeaveCommentRequest,
    leave_id: str = Path(..., description="Leave request MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    return await LeaveService(db).add_comment(leave_id, data.comment, current_user)


# ===========================================================================
# REPORTS
# ===========================================================================

@router.get(
    "/reports/utilization",
    summary="Leave Utilization Report",
    description="""
**Purpose:** Shows how much of total leave entitlement is used across the organization per leave type.

**Access:** `org_admin`, `hr_admin`

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| year | int | Year (default: current year) |
| organization_id | string | Required for superadmin |

**Response 200:**
```json
{
  "year": 2025,
  "total_employees": 50,
  "utilization": [
    { "leave_type_code": "CL", "leave_type_name": "Casual Leave", "total_entitlement": 600, "total_used": 180, "utilization_percentage": 30.0, "request_count": 65 },
    { "leave_type_code": "SL", "leave_type_name": "Sick Leave", "total_entitlement": 300, "total_used": 45, "utilization_percentage": 15.0, "request_count": 20 }
  ]
}
```
""",
)
async def report_utilization(
    year: Optional[int] = Query(None, description="Year (default: current)"),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).report_leave_utilization(current_user, year, organization_id)


@router.get(
    "/reports/balance",
    summary="Leave Balance Report",
    description="""
**Purpose:** Shows current leave balance for all employees. Useful for payroll processing.

**Access:** `org_admin`, `hr_admin`

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| year | int | Year (default: current year) |
| department | string | Filter by department |
| organization_id | string | Required for superadmin |

**Response 200:**
```json
{
  "year": 2025,
  "total": 50,
  "employees": [
    {
      "employee_id": "EMP001",
      "name": "Rahul Verma",
      "department": "Engineering",
      "balances": [
        { "code": "CL", "total": 12, "used": 3, "balance": 9 },
        { "code": "SL", "total": 6, "used": 1, "balance": 5 }
      ]
    }
  ]
}
```
""",
)
async def report_balance(
    year: Optional[int] = Query(None),
    department: Optional[str] = Query(None, description="Filter by department"),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).report_leave_balance(current_user, department, year, organization_id)


@router.get(
    "/reports/monthly",
    summary="Monthly Leave Summary",
    description="""
**Purpose:** Monthly breakdown of leaves taken — total days, requests, and per leave type.

**Access:** `org_admin`, `hr_admin`

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| year | int | Year (default: current) |
| month | int | Month 1-12 (default: current) |
| organization_id | string | Required for superadmin |

**Response 200:**
```json
{
  "year": 2025,
  "month": 7,
  "total_days": 45,
  "total_requests": 18,
  "breakdown": [
    { "leave_type_code": "CL", "total_days": 20, "request_count": 10, "unique_employees": 8 },
    { "leave_type_code": "SL", "total_days": 15, "request_count": 6, "unique_employees": 5 }
  ]
}
```
""",
)
async def report_monthly(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).report_monthly_summary(current_user, year, month, organization_id)


@router.get(
    "/reports/department",
    summary="Department-wise Leave Report",
    description="""
**Purpose:** Leave statistics grouped by department — helps identify high-absence departments.

**Access:** `org_admin`, `hr_admin`

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| year | int | Year (default: current) |
| organization_id | string | Required for superadmin |

**Response 200:**
```json
{
  "year": 2025,
  "departments": [
    {
      "department": "Engineering",
      "total_days": 120,
      "request_count": 45,
      "unique_employees_on_leave": 20,
      "total_employees": 30,
      "avg_days_per_employee": 6.0
    },
    {
      "department": "Marketing",
      "total_days": 40,
      "request_count": 15,
      "unique_employees_on_leave": 8,
      "total_employees": 10,
      "avg_days_per_employee": 5.0
    }
  ]
}
```
""",
)
async def report_department(
    year: Optional[int] = Query(None),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).report_department_wise(current_user, year, organization_id)


@router.get(
    "/reports/lop",
    summary="LOP (Loss of Pay) Report",
    description="""
**Purpose:** Employees who took unpaid leave (Leave Without Pay). Useful for salary deductions.

**Access:** `org_admin`, `hr_admin`

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| year | int | Year (default: current) |
| month | int | Optional month filter (1-12) |
| organization_id | string | Required for superadmin |

**Response 200:**
```json
{
  "year": 2025,
  "month": null,
  "total_lop_days": 15,
  "total_employees_with_lop": 3,
  "employees": [
    { "employee_id": "65emp...", "employee_name": "Rahul Verma", "department": "Engineering", "total_lop_days": 8, "lop_count": 2 },
    { "employee_id": "65emp...", "employee_name": "Priya Sharma", "department": "Design", "total_lop_days": 5, "lop_count": 1 }
  ]
}
```
""",
)
async def report_lop(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).report_lop(current_user, year, month, organization_id)


@router.get(
    "/reports/employee-history",
    summary="Employee Leave History",
    description="""
**Purpose:** Complete leave history for a single employee with type-wise summary.

**Access:** `org_admin`, `hr_admin`

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| employee_id | string | ✅ Required. Employee MongoDB ObjectId |
| year | int | Year (default: current) |
| organization_id | string | Required for superadmin |

**Response 200:**
```json
{
  "employee_id": "65emp...",
  "employee_name": "Rahul Verma",
  "department": "Engineering",
  "year": 2025,
  "total_leaves": 8,
  "type_summary": {
    "CL": { "leave_type_name": "Casual Leave", "approved": 5, "pending": 1, "rejected": 1, "cancelled": 0 },
    "SL": { "leave_type_name": "Sick Leave", "approved": 2, "pending": 0, "rejected": 0, "cancelled": 0 }
  },
  "leaves": [
    { "id": "...", "leave_type_code": "CL", "start_date": "2025-07-10", "end_date": "2025-07-11", "days": 2, "status": "approved", ... }
  ]
}
```
""",
)
async def report_employee_history(
    employee_id: str = Query(..., description="Employee MongoDB ObjectId"),
    year: Optional[int] = Query(None),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await LeaveService(db).report_employee_history(current_user, employee_id, year, organization_id)
