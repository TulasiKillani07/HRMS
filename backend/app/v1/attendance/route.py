from fastapi import APIRouter, Depends, status
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.attendance.schema import (
    AttendanceCheckInRequest,
    AttendanceResponse
)
from app.v1.attendance.service import AttendanceService

router = APIRouter()

@router.post(
    "/check-in",
    response_model=AttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Employee Check-In",
    description="""
    **Purpose:** Record employee check-in time for attendance tracking
    
    **Access:** Authenticated users (All roles)
    
    **Details:**
    - Records employee check-in timestamp
    - Creates attendance record for current date
    - Prevents duplicate check-ins for same day
    - Automatically sets status as 'present'
    
    **Required Fields:**
    - employee_id: Employee identifier
    
    **Business Logic:**
    - Check-in time recorded as current timestamp
    - Status set to 'present'
    - One check-in per employee per day
    - Creates or updates attendance record
    
    **Response:**
    - Attendance record with check-in time
    - Employee ID, date, status
    - Check-in timestamp
    
    **Use Cases:**
    - Daily employee attendance marking
    - Time tracking for payroll
    - Presence verification
    """,
    responses={
        200: {"description": "Check-in recorded successfully"},
        400: {"description": "Already checked in today"},
        401: {"description": "Not authenticated"},
        422: {"description": "Invalid employee ID"}
    }
)
async def check_in(
    data: AttendanceCheckInRequest,
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    service = AttendanceService(db)
    attendance = await service.check_in(data.employee_id)
    return attendance
