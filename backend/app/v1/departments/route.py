from fastapi import APIRouter, Depends, Query, Path, status, HTTPException, UploadFile, File
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.departments.schema import DepartmentCreateRequest, DepartmentUpdateRequest, DepartmentResponse
from app.v1.departments.service import DepartmentService

router = APIRouter()


def _require_hr(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Department",
    description="""
**Purpose:** Create a new department in the organization.

**Access:** `org_admin`, `hr_admin`

**Request Body:**
```json
{
  "name": "Engineering",
  "code": "ENG",
  "description": "Software development team"
}
```

| Field | Required | Notes |
|---|---|---|
| name | ✅ | Department display name |
| code | ✅ | Short unique code (auto-uppercased) |
| description | ❌ | Optional description |

**Response 201:**
```json
{ "id": "65dept...", "name": "Engineering", "code": "ENG", "description": "Software development team", "status": "active" }
```

**Errors:**
- `400` — Code already exists in this organization
""",
)
async def create_department(
    data: DepartmentCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr)
):
    return await DepartmentService(db).create_department(data, current_user)


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------
@router.get(
    "/",
    summary="List Departments",
    description="""
**Purpose:** Get all departments in the organization.

**Access:** All authenticated users

**Query Parameters:**
| Param | Type | Description |
|---|---|---|
| status | string | Filter: `active` / `inactive` |

**Response 200:**
```json
{
  "departments": [
    { "id": "65dept...", "name": "Engineering", "code": "ENG", "description": "Software dev team", "status": "active" },
    { "id": "65dept...", "name": "Marketing", "code": "MKT", "description": null, "status": "active" }
  ],
  "total": 5
}
```
""",
)
async def get_departments(
    status: Optional[str] = Query(None, description="active | inactive"),
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    return await DepartmentService(db).get_departments(current_user, status)


# ---------------------------------------------------------------------------
# GET SINGLE
# ---------------------------------------------------------------------------
@router.get(
    "/{department_id}",
    summary="Get Department Detail",
    description="""
**Purpose:** Get single department with employee count.

**Access:** All authenticated users

**Response 200:**
```json
{ "id": "65dept...", "name": "Engineering", "code": "ENG", "description": "...", "status": "active", "employee_count": 25 }
```

**Errors:**
- `404` — Department not found
""",
)
async def get_department(
    department_id: str = Path(..., description="Department MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    return await DepartmentService(db).get_department_by_id(department_id, current_user)


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------
@router.put(
    "/{department_id}",
    summary="Update Department",
    description="""
**Purpose:** Update department name, description, or status.

**Access:** `org_admin`, `hr_admin`

**Request Body (all optional):**
```json
{ "name": "Product Engineering", "description": "Updated", "status": "inactive" }
```

| Field | Notes |
|---|---|
| name | New name |
| description | New description |
| status | `active` / `inactive` |

**Errors:**
- `400` — No fields provided
- `404` — Department not found
""",
)
async def update_department(
    data: DepartmentUpdateRequest,
    department_id: str = Path(...),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr)
):
    return await DepartmentService(db).update_department(department_id, data, current_user)


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------
@router.delete(
    "/{department_id}",
    summary="Delete Department",
    description="""
**Purpose:** Deactivate a department. Cannot delete if employees still exist in it.

**Access:** `org_admin`, `hr_admin`

**Response 200:**
```json
{ "message": "Department 'Engineering' deactivated successfully" }
```

**Errors:**
- `400` — Employees still in this department
- `404` — Department not found
""",
)
async def delete_department(
    department_id: str = Path(...),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr)
):
    return await DepartmentService(db).delete_department(department_id, current_user)


# ---------------------------------------------------------------------------
# CSV IMPORT
# ---------------------------------------------------------------------------
@router.post(
    "/import",
    status_code=status.HTTP_201_CREATED,
    summary="Import Departments via CSV",
    description="""
**Purpose:** Bulk create departments by uploading a CSV file.

**Access:** `org_admin`, `hr_admin`

**Content-Type:** `multipart/form-data`

**Required CSV Columns:** `name`, `code`
**Optional CSV Columns:** `description`

**CSV Template:**
```
name,code,description
Engineering,ENG,Software development team
Marketing,MKT,Marketing and communications
Human Resources,HR,People operations
Finance,FIN,Finance and accounts
Design,DES,UI/UX design team
Sales,SALES,Sales and business development
Operations,OPS,Operations management
Quality Assurance,QA,Testing and quality
```

**Response 201:**
```json
{
  "imported": 8,
  "failed": 0,
  "errors": []
}
```

**Errors per row:** Duplicate code, missing name/code
""",
)
async def import_departments_csv(
    file: UploadFile = File(..., description="CSV file with department data"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")
    return await DepartmentService(db).import_departments_csv(file, current_user)
