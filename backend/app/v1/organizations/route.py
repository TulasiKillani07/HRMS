from fastapi import APIRouter, Depends, Query, Path, status
from typing import List
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.organizations.schema import (
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    OrganizationResponse
)
from app.v1.organizations.service import OrganizationService

router = APIRouter()

def check_superadmin(current_user: dict = Depends(get_current_user)):
    """Check if current user is superadmin"""
    if current_user.get("role") != "superadmin":
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin can perform this action"
        )
    return current_user

@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Organization",
    description="""
    **Purpose:** Create a new organization with automatic admin user setup
    
    **Access:** Superadmin only
    
    **Details:**
    - Creates organization in database
    - Automatically creates org_admin user account
    - Generates secure temporary password
    - Sends invitation email to admin with credentials
    - Sends welcome email to organization
    - Sends SMS notification to admin
    - Links admin user to organization
    - Sets admin user access limit (default: 2)
    
    **🎭 Roles & Access Limits:**
    
    The system has 4 roles with 2 separate access limits:
    
    **Admin Users (Limited by `admin_user_access_limit`):**
    1. **`org_admin`** - Organization Administrator
       - Full organization access
       - Auto-created with this endpoint (counts as 1)
       - Can manage departments, employees, hr_admins
       
    2. **`hr_admin`** - HR Administrator
       - HR operations access
       - Created by org_admin
       - Manages payroll, attendance, leaves
    
    **Regular Users (Limited by `emp_count_for_access`):**
    3. **`employee`** - Regular Employee
       - Self-service access
       - Apply leave, mark attendance, view payslips
    
    **System Level (No Limit):**
    4. **`superadmin`** - System Administrator
       - Full system access
       - Not tied to organizations
    
    **Access Limits:**
    - **`emp_count_for_access`**: Maximum number of employees allowed
    - **`admin_user_access_limit`**: Maximum number of admin users (org_admin + hr_admin) allowed (default: 2)
    
    **Example Scenario:**
    ```
    Create organization with:
    - emp_count_for_access: 100 (can add 100 employees)
    - admin_user_access_limit: 3 (can have 3 admin users total)
    
    After creation:
    - 1 org_admin created automatically
    - Can add 2 more admin users (org_admin or hr_admin)
    - Can add 100 employees
    ```
    
    **Actions Performed:**
    1. Validates organization email (must be unique)
    2. Validates admin email (must be unique)
    3. Creates org_admin user with default password **"Welcome1"**
    4. Creates organization record with access limits
    5. Links user and organization
    6. Sends email & SMS notifications
    
    **Admin User Created With:**
    - Email: admin_email from request
    - Password: **"Welcome1"** (default, always)
    - Role: org_admin
    - requires_password_change: true
    
    **Request Example:**
    ```json
    {
      "org_name": "Tech Solutions Inc",
      "email": "contact@techsolutions.com",
      "emp_count_for_access": 100,
      "admin_user_access_limit": 2,
      "industry": "Information Technology",
      "country": "India",
      "state": "Karnataka",
      "admin_name": "Rajesh Kumar",
      "admin_email": "admin@techsolutions.com",
      "admin_phone": "+919876543210",
      "org_address": "123 MG Road, Bangalore"
    }
    ```
    
    **Response:**
    - Returns organization details
    - Includes `temp_admin_password: "Welcome1"` in response
    - notification_sent flag indicates success
    
    **Check Admin User Limit:**
    After creation, use `GET /organizations/{org_id}/admin-user-limit` to check:
    - Current count of admin users
    - Remaining slots available
    - Whether more admin users can be added
    """,
    responses={
        201: {"description": "Organization created successfully with admin user"},
        400: {"description": "Validation error, duplicate email, or invalid data"},
        401: {"description": "Not authenticated"},
        403: {"description": "User is not superadmin"},
        422: {"description": "Invalid request format"}
    }
)
async def create_organization(
    data: OrganizationCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(check_superadmin)
):
    service = OrganizationService(db)
    organization = await service.create_organization(data)
    return organization

@router.get(
    "/",
    response_model=dict,
    summary="Get All Organizations",
    description="""
    **Purpose:** Retrieve paginated list of organizations
    
    **Access:** Superadmin only
    
    **Details:**
    - Returns paginated list of organizations
    - By default excludes soft-deleted organizations
    - Supports pagination with page and limit parameters
    - Option to include deleted organizations
    
    **Query Parameters:**
    - page: Page number (default: 1, min: 1)
    - limit: Items per page (default: 10, min: 1, max: 100)
    - include_deleted: Show deleted orgs (default: false)
    
    **Response:**
    - organizations: Array of organization objects
    - total: Total count of organizations
    - page: Current page number
    - limit: Items per page
    - pages: Total number of pages
    """,
    responses={
        200: {"description": "List of organizations retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "User is not superadmin"}
    }
)
async def get_organizations(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    include_deleted: bool = Query(False, description="Include deleted organizations"),
    db=Depends(get_database),
    current_user: dict = Depends(check_superadmin)
):
    service = OrganizationService(db)
    result = await service.get_organizations(page, limit, include_deleted)
    return result

@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get Organization by ID",
    description="""
    **Purpose:** Retrieve detailed information about a specific organization
    
    **Access:** Superadmin only
    
    **Details:**
    - Returns complete organization details
    - Validates organization ID format (MongoDB ObjectId)
    - Excludes soft-deleted organizations
    - Includes admin user reference
    
    **Path Parameters:**
    - org_id: Organization MongoDB ObjectId
    
    **Response:**
    - Complete organization details
    - Organization name, email, industry, location
    - Admin information
    - Status and metadata
    """,
    responses={
        200: {"description": "Organization details retrieved successfully"},
        400: {"description": "Invalid organization ID format"},
        401: {"description": "Not authenticated"},
        403: {"description": "User is not superadmin"},
        404: {"description": "Organization not found or deleted"}
    }
)
async def get_organization(
    org_id: str = Path(..., description="Organization ID"),
    db=Depends(get_database),
    current_user: dict = Depends(check_superadmin)
):
    service = OrganizationService(db)
    organization = await service.get_organization_by_id(org_id)
    return organization

@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update Organization",
    description="""
    **Purpose:** Update organization details and sync admin information
    
    **Access:** Superadmin only
    
    **Details:**
    - Partial updates supported (send only fields to update)
    - Validates unique email if changed
    - Syncs admin details to users collection
    - Updates admin name, email, phone in user record
    
    **Path Parameters:**
    - org_id: Organization MongoDB ObjectId
    
    **Request Body (All fields optional):**
    - org_name: Organization name
    - email: Organization email (must be unique)
    - emp_count_for_access: Employee limit
    - industry, country, state: Location details
    - admin_name, admin_email, admin_phone: Admin info
    - org_address: Organization address
    - status: active or inactive
    
    **Sync Behavior:**
    - Changing admin_email updates user's email
    - Changing admin_name updates user's full_name
    - Changing admin_phone updates user's phone
    """,
    responses={
        200: {"description": "Organization updated successfully"},
        400: {"description": "Validation error or duplicate email"},
        401: {"description": "Not authenticated"},
        403: {"description": "User is not superadmin"},
        404: {"description": "Organization not found"}
    }
)
async def update_organization(
    data: OrganizationUpdateRequest,
    org_id: str = Path(..., description="Organization ID"),
    db=Depends(get_database),
    current_user: dict = Depends(check_superadmin)
):
    service = OrganizationService(db)
    organization = await service.update_organization(org_id, data)
    return organization

@router.delete(
    "/{org_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft Delete Organization",
    description="""
    **Purpose:** Soft delete organization and deactivate admin user
    
    **Access:** Superadmin only
    
    **Details:**
    - Performs soft delete (data retained in database)
    - Sets is_deleted=True on organization
    - Sets status=inactive on organization
    - Records deleted_at timestamp
    - Deactivates admin user (is_active=False)
    - Organization won't appear in default listings
    
    **Path Parameters:**
    - org_id: Organization MongoDB ObjectId
    
    **Actions Performed:**
    1. Validates organization exists and not already deleted
    2. Sets is_deleted flag to True
    3. Changes status to inactive
    4. Records deletion timestamp
    5. Deactivates linked admin user
    
    **Note:**
    - This is a soft delete - data remains in database
    - Can be included in queries with include_deleted=true
    - Admin user cannot login after deletion
    """,
    responses={
        200: {"description": "Organization soft deleted successfully"},
        400: {"description": "Invalid organization ID format"},
        401: {"description": "Not authenticated"},
        403: {"description": "User is not superadmin"},
        404: {"description": "Organization not found or already deleted"}
    }
)
async def delete_organization(
    org_id: str = Path(..., description="Organization ID"),
    db=Depends(get_database),
    current_user: dict = Depends(check_superadmin)
):
    service = OrganizationService(db)
    result = await service.soft_delete_organization(org_id)
    return result

@router.get(
    "/{org_id}/admin-user-limit",
    response_model=dict,
    summary="Check Admin User Access Limit",
    description="""
    **Purpose:** Check how many admin users can be added to an organization
    
    **Access:** Superadmin only
    
    **Details:**
    - Returns admin user limit for organization
    - Shows current count of admin users (org_admin + hr_admin)
    - Indicates if more admin users can be added
    - Shows remaining slots
    
    **Path Parameters:**
    - org_id: Organization MongoDB ObjectId
    
    **Response:**
    - limit: Maximum admin users allowed (from admin_user_access_limit)
    - current_count: Current number of active admin users
    - can_add_more: Boolean indicating if more can be added
    - remaining: Number of remaining slots
    
    **Use Case:**
    - Check before creating new org_admin or hr_admin
    - Validate if organization has reached its admin user quota
    - Display available slots in frontend
    
    **Example Response:**
    ```json
    {
      "limit": 2,
      "current_count": 1,
      "can_add_more": true,
      "remaining": 1
    }
    ```
    """,
    responses={
        200: {"description": "Admin user limit information retrieved"},
        400: {"description": "Invalid organization ID format"},
        401: {"description": "Not authenticated"},
        403: {"description": "User is not superadmin"},
        404: {"description": "Organization not found"}
    }
)
async def check_admin_user_limit(
    org_id: str = Path(..., description="Organization ID"),
    db=Depends(get_database),
    current_user: dict = Depends(check_superadmin)
):
    service = OrganizationService(db)
    result = await service.check_admin_user_limit(org_id)
    return result

@router.get(
    "/me",
    response_model=OrganizationResponse,
    summary="Get My Organization Details",
    description="""
    **Purpose:** Get organization details for the current user's organization
    
    **Access:** org_admin, hr_admin
    
    **Details:**
    - Returns organization details for the user's assigned organization
    - org_admin and hr_admin can view their own organization
    - Automatically uses organization_id from user's profile
    - Cannot view other organizations
    
    **Use Cases:**
    - Display company information in dashboard
    - Show organization profile to admins
    - View organization limits and settings
    
    **Response Includes:**
    - Organization name, email, industry
    - Employee access limit (emp_count_for_access)
    - Admin user access limit (admin_user_access_limit)
    - Organization address and contact details
    - Admin information
    - Organization status
    
    **Example Response:**
    ```json
    {
      "id": "65abc123...",
      "org_name": "Tech Solutions Inc",
      "email": "contact@techsolutions.com",
      "emp_count_for_access": 100,
      "admin_user_access_limit": 2,
      "industry": "Information Technology",
      "country": "India",
      "state": "Karnataka",
      "admin_name": "Rajesh Kumar",
      "admin_email": "admin@techsolutions.com",
      "admin_phone": "+919876543210",
      "org_address": "123 MG Road, Bangalore",
      "status": "active",
      ...
    }
    ```
    
    **Note:**
    - User must have organization_id in their profile
    - Only works for org_admin and hr_admin roles
    - Returns 404 if organization not found or deleted
    """,
    responses={
        200: {"description": "Organization details retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "User does not have permission (must be org_admin or hr_admin)"},
        404: {"description": "Organization not found or user not assigned to any organization"}
    }
)
async def get_my_organization(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database)
):
    # Check if user is org_admin or hr_admin
    user_role = current_user.get("role")
    if user_role not in ["org_admin", "hr_admin"]:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only org_admin and hr_admin can view organization details"
        )
    
    # Get user's organization_id
    org_id = current_user.get("organization_id")
    if not org_id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not assigned to any organization"
        )
    
    # Get organization details
    service = OrganizationService(db)
    organization = await service.get_organization_by_id(org_id)
    return organization


