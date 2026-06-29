from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.organizations.schema import (
    OrganizationCreateRequest, OrganizationUpdateRequest, OrganizationResponse
)
from app.v1.organizations.service import OrganizationService

router = APIRouter()


def _require_superadmin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Only superadmin can perform this action")
    return current_user


@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization",
    description="""
**Purpose:** Create a new organization. Automatically creates an `org_admin` user account
and sends them a welcome email with login credentials.

**Access:** `superadmin` only.

**Request Body:**
```json
{
  "org_name": "Tech Solutions India",
  "email": "contact@techsolutions.com",
  "emp_count_for_access": 100,
  "admin_user_access_limit": 3,
  "industry": "Information Technology",
  "country": "India",
  "state": "Karnataka",
  "admin_name": "Rajesh Kumar",
  "admin_email": "rajesh@techsolutions.com",
  "admin_phone": "+919876543210",
  "org_address": "123 MG Road, Bangalore"
}
```

| Field | Required | Notes |
|---|---|---|
| org_name | ✅ | |
| email | ✅ | Organization contact email, must be unique |
| emp_count_for_access | ✅ | Max employees allowed (e.g. 50, 100, 500) |
| admin_user_access_limit | ❌ | Max org_admin + hr_admin allowed. Default: 2 |
| industry | ✅ | |
| country, state | ✅ | |
| admin_name, admin_email, admin_phone | ✅ | org_admin contact details |
| org_address | ❌ | |

**What happens automatically:**
1. Organization record created
2. `org_admin` user created with password `Welcome1`
3. Welcome email sent to `admin_email` with login credentials
4. Welcome email sent to org `email`

**Response 201:**
```json
{
  "id": "65abc...",
  "org_name": "Tech Solutions India",
  "status": "active",
  "emp_count_for_access": 100,
  "admin_user_access_limit": 3,
  "temp_admin_password": "Welcome1",
  "notification_sent": true,
  ...
}
```

**Errors:**
- `400` — Organization email or admin email already exists
- `403` — Not superadmin
""",
)
async def create_organization(
    data: OrganizationCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(_require_superadmin)
):
    return await OrganizationService(db).create_organization(data)


@router.get(
    "/",
    response_model=dict,
    summary="List All Organizations",
    description="""
**Purpose:** Get a paginated list of all organizations in the system.

**Access:** `superadmin` only.

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| page | int | 1 | Page number |
| limit | int | 10 | Items per page (max 100) |
| include_deleted | bool | false | Show soft-deleted organizations too |

**Response 200:**
```json
{
  "organizations": [ { "id": "...", "org_name": "...", "status": "active", ... } ],
  "total": 25,
  "page": 1,
  "limit": 10,
  "pages": 3
}
```

**Errors:**
- `403` — Not superadmin
""",
)
async def get_organizations(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    include_deleted: bool = Query(False),
    db=Depends(get_database),
    current_user: dict = Depends(_require_superadmin)
):
    return await OrganizationService(db).get_organizations(page, limit, include_deleted)


@router.get(
    "/me",
    response_model=OrganizationResponse,
    summary="Get My Organization",
    description="""
**Purpose:** Get the organization details for the currently logged-in admin.

**Access:** `org_admin`, `hr_admin` — returns their own organization automatically.

**Response 200:** Full organization object.
""",
)
async def get_my_organization(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    role = current_user.get("role")
    if role not in ["org_admin", "hr_admin"]:
        raise HTTPException(status_code=403, detail="Only org_admin and hr_admin can view organization details")
    org_id = current_user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=404, detail="User is not assigned to any organization")
    return await OrganizationService(db).get_organization_by_id(org_id)


@router.put(
    "/me",
    response_model=OrganizationResponse,
    summary="Update My Organization",
    description="""
**Purpose:** Org admin updates their own organization details.

**Access:** `org_admin`

**Request Body (all optional):**
```json
{
  "org_name": "Updated Company Name",
  "email": "new@company.com",
  "industry": "Technology",
  "country": "India",
  "state": "Telangana",
  "org_address": "New address",
  "admin_name": "New Admin Name",
  "admin_phone": "+919999999999"
}
```

**Note:** `emp_count_for_access` and `admin_user_access_limit` can only be changed by superadmin.

**Response 200:** Updated organization object.
""",
)
async def update_my_organization(
    data: OrganizationUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    role = current_user.get("role")
    if role != "org_admin":
        raise HTTPException(status_code=403, detail="Only org_admin can update organization")
    org_id = current_user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=404, detail="No organization linked")
    return await OrganizationService(db).update_organization(org_id, data)


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get Organization by ID",
    description="""
**Purpose:** Get full details of a specific organization by its ID.

**Access:** `superadmin` only.

**Path Parameter:** `org_id` — MongoDB ObjectId of the organization.

**Response 200:**
```json
{
  "id": "65abc...",
  "org_name": "Tech Solutions India",
  "email": "contact@techsolutions.com",
  "emp_count_for_access": 100,
  "admin_user_access_limit": 3,
  "admin_name": "Rajesh Kumar",
  "admin_email": "rajesh@techsolutions.com",
  "status": "active",
  "is_deleted": false,
  ...
}
```

**Errors:**
- `400` — Invalid org_id format
- `403` — Not superadmin
- `404` — Organization not found or deleted
""",
)
async def get_organization(
    org_id: str = Path(..., description="Organization MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_superadmin)
):
    return await OrganizationService(db).get_organization_by_id(org_id)


@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update Organization",
    description="""
**Purpose:** Update organization details. All fields are optional — send only what needs changing.

**Access:** `superadmin` only.

**Path Parameter:** `org_id` — MongoDB ObjectId of the organization.

**Request Body (all fields optional):**
```json
{
  "org_name": "Tech Solutions India Pvt Ltd",
  "emp_count_for_access": 200,
  "admin_user_access_limit": 5,
  "admin_name": "Rajesh Kumar",
  "admin_email": "rajesh.new@techsolutions.com",
  "admin_phone": "+919876543299",
  "status": "active"
}
```

**Sync behavior:** If `admin_email`, `admin_name`, or `admin_phone` is updated here,
the linked org_admin user record is updated automatically.

**Response 200:** Updated organization object.

**Errors:**
- `400` — Email already taken, no fields provided
- `403` — Not superadmin
- `404` — Organization not found
""",
)
async def update_organization(
    data: OrganizationUpdateRequest,
    org_id: str = Path(..., description="Organization MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_superadmin)
):
    return await OrganizationService(db).update_organization(org_id, data)


@router.delete(
    "/{org_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Organization (Soft Delete)",
    description="""
**Purpose:** Soft delete an organization. Data is retained but the org and its admin are deactivated.

**Access:** `superadmin` only.

**Path Parameter:** `org_id` — MongoDB ObjectId of the organization.

**Request Body:** None.

**What happens:**
- Organization: `is_deleted = true`, `status = inactive`
- Linked org_admin user: `is_active = false` (cannot login)
- Organization disappears from default list unless `include_deleted=true`

**Response 200:**
```json
{ "message": "Organization deleted successfully" }
```

**Errors:**
- `400` — Invalid org_id format
- `403` — Not superadmin
- `404` — Organization not found or already deleted
""",
)
async def delete_organization(
    org_id: str = Path(..., description="Organization MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_superadmin)
):
    return await OrganizationService(db).soft_delete_organization(org_id)


@router.get(
    "/{org_id}/admin-user-limit",
    response_model=dict,
    summary="Check Admin User Limit",
    description="""
**Purpose:** Check how many admin slots (org_admin + hr_admin) are used vs available in an organization.

**Access:** `superadmin` only.

**Path Parameter:** `org_id` — MongoDB ObjectId of the organization.

**Request Body:** None.

**Response 200:**
```json
{
  "limit": 3,
  "current_count": 2,
  "can_add_more": true,
  "remaining": 1
}
```

Use this before creating a new admin user to check if the org has capacity.

**Errors:**
- `403` — Not superadmin
- `404` — Organization not found
""",
)
async def check_admin_user_limit(
    org_id: str = Path(..., description="Organization MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_superadmin)
):
    return await OrganizationService(db).check_admin_user_limit(org_id)
