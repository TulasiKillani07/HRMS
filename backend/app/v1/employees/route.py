from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.employees.schema import (
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    EmployeeResponse,
    EmployeeListResponse
)
from app.v1.employees.service import EmployeeService

router = APIRouter()


def _require_employee_access(current_user: dict = Depends(get_current_user)):
    """Allow superadmin, org_admin, and hr_admin."""
    role = current_user.get("role")
    if role not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin, org_admin, or hr_admin can manage employees"
        )
    return current_user


# ---------------------------------------------------------------------------
# POST /employees/  — Create employee
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Employee",
    description="""
**Purpose:** Add a new employee to the organization

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Details:**
- `org_admin` / `hr_admin`: organization auto-inferred from their profile
- `superadmin`: must supply `organization_id` in the request body
- Validates unique `employee_id` within the organization
- Validates unique `email` across all employees
- Validates `department_id` belongs to the same organization (if provided)
- Checks `emp_count_for_access` limit before creating

**Required Fields:**
`employee_id`, `first_name`, `last_name`, `email`, `phone`,
`date_of_birth`, `gender`, `address`, `designation`, `joining_date`, `salary`

**Optional Fields:**
`organization_id` (required for superadmin), `department_id`,
`employment_type` (default: full-time), `bank_account`, `emergency_contact`
""",
    responses={
        201: {"description": "Employee created successfully"},
        400: {"description": "Duplicate employee_id / email, missing organization_id for superadmin, or invalid department"},
        403: {"description": "Access denied or employee limit reached"},
        404: {"description": "Organization not found"},
    }
)
async def create_employee(
    data: EmployeeCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_access)
):
    service = EmployeeService(db)
    employee = await service.create_employee(data, current_user)
    return employee


# ---------------------------------------------------------------------------
# GET /employees/  — List employees
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=EmployeeListResponse,
    summary="List Employees",
    description="""
**Purpose:** Retrieve employees in an organization

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Query Parameters:**
- `organization_id` — **required for superadmin**, ignored for org_admin/hr_admin
- `page` — page number (default: 1)
- `limit` — items per page (default: 10, max: 100)
- `status` — filter: `active` | `inactive` | `terminated`
- `department_id` — filter by department
- `search` — search by name, email, employee_id, or designation
- `include_deleted` — include soft-deleted employees (default: false)
""",
    responses={
        200: {"description": "Employee list retrieved"},
        400: {"description": "superadmin must supply organization_id"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
    }
)
async def get_employees(
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="active | inactive | terminated"),
    department_id: Optional[str] = Query(None, description="Filter by department ID"),
    search: Optional[str] = Query(None, description="Search by name, email, employee_id, designation"),
    include_deleted: bool = Query(False, description="Include soft-deleted employees"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_access)
):
    service = EmployeeService(db)
    result = await service.get_employees(
        current_user, page, limit, status,
        department_id, search, include_deleted, organization_id
    )
    return result


# ---------------------------------------------------------------------------
# GET /employees/{employee_id}  — Get single employee
# ---------------------------------------------------------------------------
@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Get Employee by ID",
    description="""
**Purpose:** Get full details of a specific employee

**Access:** `superadmin`, `org_admin`, `hr_admin`

- `superadmin` can fetch any employee across all orgs
- `org_admin` / `hr_admin` can only fetch employees in their own organization
""",
    responses={
        200: {"description": "Employee details retrieved"},
        400: {"description": "Invalid ID format"},
        403: {"description": "Access denied"},
        404: {"description": "Employee not found"},
    }
)
async def get_employee(
    employee_id: str = Path(..., description="Employee MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_access)
):
    service = EmployeeService(db)
    employee = await service.get_employee_by_id(employee_id, current_user)
    return employee


# ---------------------------------------------------------------------------
# PUT /employees/{employee_id}  — Update employee
# ---------------------------------------------------------------------------
@router.put(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Update Employee",
    description="""
**Purpose:** Update an employee's details

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Updatable Fields:**
`first_name`, `last_name`, `email`, `phone`, `address`, `department_id`,
`designation`, `employment_type`, `salary`, `status`, `bank_account`, `emergency_contact`

**Notes:**
- Partial updates supported — send only fields to change
- `status` must be one of: `active`, `inactive`, `terminated`
- `department_id` must belong to the same organization
- `employee_id` and `organization_id` cannot be changed
- `superadmin` can update employees across all orgs
""",
    responses={
        200: {"description": "Employee updated successfully"},
        400: {"description": "Invalid data, duplicate email, or invalid department/status"},
        403: {"description": "Access denied"},
        404: {"description": "Employee not found"},
    }
)
async def update_employee(
    data: EmployeeUpdateRequest,
    employee_id: str = Path(..., description="Employee MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_access)
):
    service = EmployeeService(db)
    employee = await service.update_employee(employee_id, data, current_user)
    return employee


# ---------------------------------------------------------------------------
# DELETE /employees/{employee_id}  — Soft delete
# ---------------------------------------------------------------------------
@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Employee",
    description="""
**Purpose:** Soft delete an employee (data is retained in the database)

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Details:**
- Sets `is_deleted = True` and records `deleted_at` timestamp
- Sets `status = inactive`
- Employee will not appear in normal list/get queries
- Use `include_deleted=true` in list endpoint to still see them
- `superadmin` can delete employees across all orgs
""",
    responses={
        200: {"description": "Employee deleted successfully"},
        400: {"description": "Invalid ID format"},
        403: {"description": "Access denied"},
        404: {"description": "Employee not found"},
    }
)
async def delete_employee(
    employee_id: str = Path(..., description="Employee MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_access)
):
    service = EmployeeService(db)
    result = await service.delete_employee(employee_id, current_user)
    return result
