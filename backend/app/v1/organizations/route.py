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
    
    **Actions Performed:**
    1. Validates organization email (must be unique)
    2. Validates admin email (must be unique)
    3. Creates org_admin user with default password **"Welcome1"**
    4. Creates organization record
    5. Links user and organization
    6. Sends email & SMS notifications
    
    **Admin User Created With:**
    - Email: admin_email from request
    - Password: **"Welcome1"** (default, always)
    - Role: org_admin
    - requires_password_change: true
    
    **Response:**
    - Returns organization details
    - Includes `temp_admin_password: "Welcome1"` in response
    - notification_sent flag indicates success
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
