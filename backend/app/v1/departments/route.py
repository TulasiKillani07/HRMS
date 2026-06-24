from fastapi import APIRouter, Depends, status
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.departments.schema import DepartmentCreateRequest, DepartmentResponse
from app.v1.departments.service import DepartmentService

router = APIRouter()


@router.post(
    "/",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Department",
    description="""
**Purpose:** Create a new department inside the caller's organization.

**Access:** `org_admin`, `hr_admin` — organization is auto-inferred from token.

**Request Body:**
```json
{
  "name": "Engineering",
  "code": "ENG",
  "description": "Software Engineering Department",
  "manager_id": null
}
```

| Field | Required | Notes |
|---|---|---|
| name | ✅ | Department display name |
| code | ✅ | Short unique code within the org (e.g. ENG, HR, FIN). Auto-uppercased. |
| description | ❌ | |
| manager_id | ❌ | MongoDB ObjectId of the employee who manages this department |

**Response 201:**
```json
{
  "id": "65abc...",
  "name": "Engineering",
  "code": "ENG",
  "description": "Software Engineering Department",
  "manager_id": null,
  "status": "active"
}
```

**Errors:**
- `400` — Department code already exists in this organization
- `401` — Not authenticated
- `403` — Not org_admin or hr_admin
""",
)
async def create_department(
    data: DepartmentCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    return await DepartmentService(db).create_department(data, current_user)
