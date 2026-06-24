from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.users.schema import (
    UserCreateRequest, UserUpdateRequest, UserListResponse
)
from app.v1.users.service import UserManagementService

router = APIRouter()


def _require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("superadmin", "org_admin"):
        raise HTTPException(status_code=403, detail="Only superadmin or org_admin can access user management")
    return current_user


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create Admin User",
    description="""
**Purpose:** Create a new admin user (org_admin or hr_admin). Sends a welcome email
with login credentials. Password is always set to `Welcome1`.

**Access:**
- `superadmin` → can create `org_admin` or `hr_admin` (must supply `organization_id`)
- `org_admin` → can only create `hr_admin` (organization auto-inferred from token)

**Checks before creating:**
- Email must be unique
- `admin_user_access_limit` of the organization must not be exceeded

**Request Body — superadmin creating org_admin:**
```json
{
  "email": "admin@techsolutions.com",
  "full_name": "Org Admin",
  "phone": "+919876543210",
  "role": "org_admin",
  "organization_id": "65abc123def456"
}
```

**Request Body — org_admin creating hr_admin** (no organization_id needed):
```json
{
  "email": "hr@techsolutions.com",
  "full_name": "HR Manager",
  "phone": "+919876543211",
  "role": "hr_admin"
}
```

**Response 201:**
```json
{
  "id": "65xyz...",
  "email": "hr@techsolutions.com",
  "full_name": "HR Manager",
  "role": "hr_admin",
  "status": "active",
  "organization_id": "65abc...",
  "requires_password_change": true,
  ...
}
```

**Errors:**
- `400` — Email already exists or missing organization_id
- `403` — Wrong role or admin limit reached
- `404` — Organization not found
""",
)
async def create_user(
    data: UserCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    return await UserManagementService(db).create_user(data, current_user)


@router.get(
    "/",
    response_model=UserListResponse,
    summary="List Admin Users",
    description="""
**Purpose:** Get a paginated list of admin users.

**Access:**
- `superadmin` → sees all `org_admin` and `hr_admin` across all organizations. Each user includes `org_name`.
- `org_admin` → sees only `hr_admin` users in their own organization.

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| page | int | 1 | Page number |
| limit | int | 10 | Items per page (max 100) |
| include_inactive | bool | false | Show deactivated users too |

**Response 200:**
```json
{
  "users": [
    {
      "id": "65xyz...",
      "email": "hr@techsolutions.com",
      "full_name": "HR Manager",
      "role": "hr_admin",
      "status": "active",
      "org_name": "Tech Solutions India",
      "organization_id": "65abc...",
      "last_login": "2025-06-20T10:30:00",
      "created_at": "2025-06-01T09:00:00",
      "updated_at": "2025-06-20T10:30:00"
    }
  ],
  "total": 5,
  "page": 1,
  "limit": 10,
  "pages": 1
}
```

**Errors:**
- `403` — Not superadmin or org_admin
""",
)
async def get_users(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    include_inactive: bool = Query(False, description="Include inactive/deactivated users"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    return await UserManagementService(db).get_users(current_user, page, limit, include_inactive)


@router.get(
    "/{user_id}",
    summary="Get Admin User by ID",
    description="""
**Purpose:** Get full details of a specific admin user.

**Access:**
- `superadmin` → can fetch any `org_admin` or `hr_admin`. Response includes `org_name`.
- `org_admin` → can only fetch `hr_admin` users in their own organization.

**Path Parameter:** `user_id` — MongoDB ObjectId of the user.

**Response 200:**
```json
{
  "id": "65xyz...",
  "email": "hr@techsolutions.com",
  "full_name": "HR Manager",
  "role": "hr_admin",
  "phone": "+919876543211",
  "status": "active",
  "org_name": "Tech Solutions India",
  "organization_id": "65abc...",
  "is_verified": false,
  "requires_password_change": false,
  "last_login": "2025-06-20T10:30:00",
  "created_at": "2025-06-01T09:00:00",
  "updated_at": "2025-06-20T10:30:00"
}
```

**Errors:**
- `400` — Invalid user ID format
- `403` — Access denied (wrong org or wrong target role)
- `404` — User not found
""",
)
async def get_user(
    user_id: str = Path(..., description="User MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    return await UserManagementService(db).get_user_by_id(user_id, current_user)


@router.put(
    "/{user_id}",
    summary="Update Admin User",
    description="""
**Purpose:** Update profile details of an admin user. All fields are optional.

**Access:**
- `superadmin` → can update any `org_admin` or `hr_admin`
- `org_admin` → can only update `hr_admin` users in their own organization

**Path Parameter:** `user_id` — MongoDB ObjectId of the user.

**Request Body (all fields optional):**
```json
{
  "full_name": "Senior HR Manager",
  "phone": "+919876543299",
  "email": "newemail@techsolutions.com",
  "is_active": true
}
```

**Notes:**
- Role and organization cannot be changed after creation
- Email uniqueness is enforced if changed
- Setting `is_active: false` deactivates the user (they cannot login)

**Response 200:** Updated user object (same shape as GET response).

**Errors:**
- `400` — No fields provided, duplicate email, or invalid ID
- `403` — Access denied
- `404` — User not found
""",
)
async def update_user(
    data: UserUpdateRequest,
    user_id: str = Path(..., description="User MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    return await UserManagementService(db).update_user(user_id, data, current_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Deactivate Admin User (Soft Delete)",
    description="""
**Purpose:** Soft delete an admin user — deactivates their account. Data is retained.

**Access:**
- `superadmin` → can deactivate any `org_admin` or `hr_admin`
- `org_admin` → can only deactivate `hr_admin` users in their own organization

**Path Parameter:** `user_id` — MongoDB ObjectId of the user.

**Request Body:** None.

**What happens:**
- Sets `is_active = false`
- User cannot login anymore
- User still appears in list when `include_inactive=true`

**Response 200:**
```json
{ "message": "User deactivated successfully", "user_id": "65xyz..." }
```

**Errors:**
- `400` — User already inactive, invalid ID, or trying to delete yourself
- `403` — Access denied
- `404` — User not found
""",
)
async def delete_user(
    user_id: str = Path(..., description="User MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    return await UserManagementService(db).delete_user(user_id, current_user)
