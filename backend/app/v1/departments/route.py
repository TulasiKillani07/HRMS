from fastapi import APIRouter, Depends, status
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.departments.schema import (
    DepartmentCreateRequest,
    DepartmentResponse
)
from app.v1.departments.service import DepartmentService

router = APIRouter()

@router.post(
    "/",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Department",
    description="""
    **Purpose:** Create a new department in the organization
    
    **Access:** Authenticated users (org_admin, hr_admin)
    
    **Details:**
    - Creates new department record
    - Validates unique department code
    - Sets initial status as 'active'
    - Optionally assign department manager
    
    **Required Fields:**
    - name: Department name
    - code: Unique department code (e.g., "ENG", "HR", "FIN")
    
    **Optional Fields:**
    - description: Department description
    - manager_id: Employee ID of department manager
    
    **Response:**
    - Returns created department details
    - Includes department ID, name, code, status
    """,
    responses={
        201: {"description": "Department created successfully"},
        400: {"description": "Department code already exists"},
        401: {"description": "Not authenticated"},
        422: {"description": "Invalid request data"}
    }
)
async def create_department(
    data: DepartmentCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    service = DepartmentService(db)
    department = await service.create_department(data, current_user)
    return department
