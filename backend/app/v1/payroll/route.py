from fastapi import APIRouter, Depends, status
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.payroll.schema import PayrollCreateRequest, PayrollResponse
from app.v1.payroll.service import PayrollService

router = APIRouter()

@router.post(
    "/",
    response_model=PayrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Payroll Record",
    description="""
    **Purpose:** Generate payroll record for employee's monthly salary
    
    **Access:** Authenticated users (org_admin, hr_admin)
    
    **Details:**
    - Creates monthly payroll record
    - Automatically calculates gross and net salary
    - Validates no duplicate payroll for same month/year
    - Supports allowances, deductions, overtime, bonuses
    
    **Required Fields:**
    - employee_id: Employee identifier
    - month: Month number (1-12)
    - year: Year (e.g., 2024)
    - basic_salary: Base salary amount
    
    **Optional Fields:**
    - allowances: Dictionary of allowances (HRA, transport, etc.)
    - deductions: Dictionary of deductions (tax, insurance, etc.)
    - overtime_pay: Overtime compensation
    - bonus: Performance or other bonuses
    
    **Automatic Calculations:**
    - gross_salary = basic_salary + allowances + overtime_pay + bonus
    - net_salary = gross_salary - deductions
    - payment_status = "pending"
    
    **Response:**
    - Complete payroll details
    - Calculated gross and net salary
    - Payment status
    
    **Business Rules:**
    - One payroll record per employee per month
    - Payment status starts as 'pending'
    - Can be updated to 'processed' or 'paid' later
    """,
    responses={
        201: {"description": "Payroll record created successfully"},
        400: {"description": "Payroll for this month already exists"},
        401: {"description": "Not authenticated"},
        422: {"description": "Invalid request data"}
    }
)
async def create_payroll(
    data: PayrollCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(get_current_user)
):
    service = PayrollService(db)
    payroll = await service.create_payroll(data)
    return payroll
