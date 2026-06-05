from fastapi import APIRouter, Depends, Query, status
from typing import List
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.employees.schema import (
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    EmployeeResponse
)
from app.v1.employees.service import EmployeeService

router = APIRouter()

@router.post(
    "/",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Employee",
    description="""
    **Purpose:** Add a new employee to the organization
    
    **Access:** Authenticated users (org_admin, hr_admin)
    
    **Details:**
    - Creates new employee record
    - Validates unique employee_id and email
    - Sets initial status as 'active'
    - Stores complete employee information
    
    **Required Fields:**
    - employee_id: Unique employee identifier
    - first_name, last_name: Employee name
    - email: Unique email address
    - phone: Contact number
    - date_of_birth, gender: Personal info
    - address: Residential address
    - designation: Job title
    - joining_date: Employment start date
    - salary: Compensation amount
    
    **Optional Fields:**
    - department_id: Link to department
    - employment_type: full-time, part-time, contract
    - bank_account: Banking details
    - emergency_contact: Emergency contact info
    """,
    responses={
        201: {"description": "Employee created successfully"},
        400: {"description": "Employee ID or email already exists"},
        401: {"description": "Not authenticated"},
        422: {"description": "Invalid request data"}
    }
)
async def create_employee(
    data: EmployeeCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    service = EmployeeService(db)
    employee = await service.create_employee(data)
    return employee

@router.get(
    "/",
    response_model=List[EmployeeResponse],
    summary="Get All Employees",
    description="""
    **Purpose:** Retrieve paginated list of employees
    
    **Access:** Authenticated users (All roles)
    
    **Details:**
    - Returns paginated employee list
    - Includes all active employees
    - Supports pagination for large datasets
    
    **Query Parameters:**
    - page: Page number (default: 1, min: 1)
    - limit: Items per page (default: 10, min: 1, max: 100)
    
    **Response:**
    - Array of employee objects
    - Employee details without sensitive data
    """,
    responses={
        200: {"description": "Employee list retrieved successfully"},
        401: {"description": "Not authenticated"}
    }
)
async def get_employees(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    service = EmployeeService(db)
    employees = await service.get_employees(page, limit)
    return employees
