from fastapi import APIRouter, Depends, status
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.leaves.schema import LeaveCreateRequest, LeaveResponse
from app.v1.leaves.service import LeaveService

router = APIRouter()

@router.post(
    "/",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Leave Request",
    description="""
    **Purpose:** Submit a new leave request for employee
    
    **Access:** Authenticated users (All roles)
    
    **Details:**
    - Creates leave request with pending status
    - Automatically calculates leave days
    - Validates date range (end_date >= start_date)
    - Supports multiple leave types
    
    **Required Fields:**
    - employee_id: Employee identifier
    - leave_type: Type of leave (sick, casual, annual, unpaid)
    - start_date: Leave start date
    - end_date: Leave end date
    - reason: Reason for leave
    
    **Automatic Calculations:**
    - days: Calculated as (end_date - start_date) + 1
    - status: Set to 'pending' by default
    
    **Response:**
    - Leave request details
    - Calculated number of days
    - Request status (pending)
    
    **Leave Types:**
    - sick: Medical leave
    - casual: Short-term casual leave
    - annual: Planned annual leave
    - unpaid: Leave without pay
    """,
    responses={
        201: {"description": "Leave request created successfully"},
        400: {"description": "Invalid date range"},
        401: {"description": "Not authenticated"},
        422: {"description": "Invalid request data"}
    }
)
async def create_leave_request(
    data: LeaveCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    service = LeaveService(db)
    leave = await service.create_leave_request(data)
    return leave
