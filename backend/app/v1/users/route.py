from fastapi import APIRouter, Depends, Query, Path, status
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.users.schema import (
    UserCreateRequest,
    UserUpdateRequest,
    UserResponse,
    UserListResponse,
)
from app.v1.users.service import UserManagementService

router = APIRouter()


def _require_admin(current_user: dict = Depends(get_current_user)):
    """Allow only superadmin and org_admin."""
    role = current_user.get("role")
    if role not in ("superadmin", "org_admin"):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin or org_admin can access user management"
        )
    return current_user


# ---------------------------------------------------------------------------
# POST /users/  — Create user
# ---------------------------------------------------------------------------
@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create Admin User",
    description="""
**Purpose:** Create a new admin user (org_admin or hr_admin)

**Access:**
- `superadmin` → can create `org_admin` (must supply `organization_id`)
- `org_admin` → can create `hr_admin` (organization auto-inferred from caller)

**Details:**
- Default password `"Welcome1"` is set automatically
- `requires_password_change` is `true` — user must change password on first login
- Invitation email is sent to the new user with login credentials
- Checks `admin_user_access_limit` before creating (enforced for hr_admin by org_admin)

**Request Example (superadmin creating org_admin):**
```json
{
  "email": "orgadmin@company.com",
  "full_name": "Org Admin",
  "phone": "+919876543210",
  "role": "org_admin",
  "organization_id": "65abc123def456"
}
```

**Request Example (org_admin creating hr_admin):**
```json
{
  "email": "hradmin@company.com",
  "full_name": "HR Manager",
  "phone": "+919876543211",
  "role": "hr_admin"
}
```
""",
    responses={
        201: {"description": "User created and invitation email sent"},
        400: {"description": "Email already exists or missing organization_id"},
        403: {"description": "Insufficient permissions or admin limit reached"},
        404: {"description": "Organization not found"},
    }
)
async def create_user(
    data: UserCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    service = UserManagementService(db)
    user = await service.create_user(data, current_user)
    return user


# ---------------------------------------------------------------------------
# GET /users/  — List users
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=UserListResponse,
    summary="List Admin Users",
    description="""
**Purpose:** Retrieve paginated list of admin users

**Access:**
- `superadmin` → sees all `org_admin` and `hr_admin` across all organizations
- `org_admin` → sees only `hr_admin` users in their own organization

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10, max: 100)
- `include_inactive`: Include soft-deleted (inactive) users (default: false)

**Response:** Paginated list with user details (passwords excluded)
""",
    responses={
        200: {"description": "User list retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
    }
)
async def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    include_inactive: bool = Query(False, description="Include inactive users"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    service = UserManagementService(db)
    result = await service.get_users(current_user, page, limit, include_inactive)
    return result


# ---------------------------------------------------------------------------
# GET /users/{user_id}  — Get single user
# ---------------------------------------------------------------------------
@router.get(
    "/{user_id}",
    summary="Get User by ID",
    description="""
**Purpose:** Retrieve details of a specific admin user

**Access:**
- `superadmin` → can fetch any `org_admin` or `hr_admin`
- `org_admin` → can only fetch `hr_admin` users in their own organization

**Path Parameters:**
- `user_id`: MongoDB ObjectId of the user
""",
    responses={
        200: {"description": "User details retrieved"},
        400: {"description": "Invalid user ID format"},
        403: {"description": "Access denied"},
        404: {"description": "User not found"},
    }
)
async def get_user(
    user_id: str = Path(..., description="User ID"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    service = UserManagementService(db)
    user = await service.get_user_by_id(user_id, current_user)
    return user


# ---------------------------------------------------------------------------
# PUT /users/{user_id}  — Update user
# ---------------------------------------------------------------------------
@router.put(
    "/{user_id}",
    summary="Update Admin User",
    description="""
**Purpose:** Update an admin user's profile details

**Access:**
- `superadmin` → can update any `org_admin` or `hr_admin`
- `org_admin` → can only update `hr_admin` users in their own organization

**Updatable Fields:**
- `full_name`, `phone`, `email`, `is_active`

**Notes:**
- All fields are optional (partial update supported)
- Email uniqueness is enforced if changed
- Role and organization cannot be changed via this endpoint
""",
    responses={
        200: {"description": "User updated successfully"},
        400: {"description": "No fields provided, invalid ID, or duplicate email"},
        403: {"description": "Access denied"},
        404: {"description": "User not found"},
    }
)
async def update_user(
    data: UserUpdateRequest,
    user_id: str = Path(..., description="User ID"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    service = UserManagementService(db)
    user = await service.update_user(user_id, data, current_user)
    return user


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}  — Soft delete user
# ---------------------------------------------------------------------------
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Deactivate Admin User",
    description="""
**Purpose:** Soft delete (deactivate) an admin user

**Access:**
- `superadmin` → can deactivate any `org_admin` or `hr_admin`
- `org_admin` → can only deactivate `hr_admin` users in their own organization

**Details:**
- Sets `is_active = False` (soft delete — data retained)
- Deactivated users cannot login
- Cannot deactivate your own account
- Use `include_inactive=true` in list endpoint to still see them
""",
    responses={
        200: {"description": "User deactivated successfully"},
        400: {"description": "Invalid ID, user already inactive, or self-deletion attempt"},
        403: {"description": "Access denied"},
        404: {"description": "User not found"},
    }
)
async def delete_user(
    user_id: str = Path(..., description="User ID"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_admin)
):
    service = UserManagementService(db)
    result = await service.delete_user(user_id, current_user)
    return result
