from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.payroll.service import PayrollService

router = APIRouter()

def _hr(u: dict = Depends(get_current_user)):
    if u.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return u

def _admin(u: dict = Depends(get_current_user)):
    if u.get("role") not in ("superadmin", "org_admin"):
        raise HTTPException(status_code=403, detail="Only org_admin")
    return u

def _emp(u: dict = Depends(get_current_user)):
    if u.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Only employees")
    return u

def _any(u: dict = Depends(get_current_user)):
    return u


# Schemas
class PayrollConfigRequest(BaseModel):
    basic_percentage: Optional[float] = Field(None, gt=0, le=100, description="Basic % of CTC (e.g., 40)")
    hra_percentage: Optional[float] = Field(None, ge=0, le=100, description="HRA % of CTC (e.g., 20)")
    special_allowance_percentage: Optional[float] = Field(None, ge=0, le=100, description="Special Allowance % of CTC (e.g., 15)")
    pf_percentage: Optional[float] = None
    esi_employee_percentage: Optional[float] = None
    esi_employer_percentage: Optional[float] = None
    esi_limit: Optional[float] = None
    professional_tax: Optional[float] = None
    pay_day: Optional[int] = None
    lop_calculation: Optional[str] = None

class RunPayrollRequest(BaseModel):
    month: int = Field(..., ge=1, le=12)
    year: int = Field(...)

class AdjustmentRequest(BaseModel):
    employee_id: str
    type: str = Field(..., description="bonus | deduction | reimbursement")
    amount: float = Field(..., gt=0)
    description: str = ""
    month: int = Field(..., ge=1, le=12)
    year: int

class EditPayslipRequest(BaseModel):
    bonus: Optional[float] = None
    reimbursements: Optional[float] = None
    tds: Optional[float] = None
    other_deductions: Optional[float] = None


# CONFIG
@router.get("/config", summary="Get Payroll Config", description="**Access:** org_admin, hr_admin")
async def get_config(organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_config(current_user, organization_id)

@router.put("/config", summary="Update Payroll Config", description="**Access:** org_admin\n\nSet PF%, ESI%, PT, pay day, LOP calculation method.")
async def update_config(data: PayrollConfigRequest, organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_admin)):
    return await PayrollService(db).update_config(data.model_dump(exclude_unset=True), current_user, organization_id)

# RUNS
@router.post("/run", status_code=201, summary="Run Payroll", description="**Access:** org_admin, hr_admin\n\nProcess payroll for a month. Auto-calculates all payslips.")
async def run_payroll(data: RunPayrollRequest, organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).run_payroll(data.month, data.year, current_user, organization_id)

@router.get("/runs", summary="List Payroll Runs", description="**Access:** org_admin, hr_admin")
async def get_runs(year: Optional[int] = Query(None), status: Optional[str] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_runs(current_user, year, status, organization_id)

@router.get("/runs/{run_id}", summary="Get Run Detail", description="**Access:** org_admin, hr_admin\n\nReturns run + all payslips.")
async def get_run_detail(run_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_run_detail(run_id, current_user)

@router.patch("/runs/{run_id}/approve", summary="Approve Payroll", description="**Access:** org_admin\n\nChanges status: processed → approved")
async def approve_run(run_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_admin)):
    return await PayrollService(db).approve_run(run_id, current_user)

@router.patch("/runs/{run_id}/mark-paid", summary="Mark as Paid", description="**Access:** org_admin\n\nChanges status: approved → paid")
async def mark_paid(run_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_admin)):
    return await PayrollService(db).mark_paid(run_id, current_user)

# PAYSLIPS
@router.get("/payslips", summary="List Payslips (HR)", description="**Access:** org_admin, hr_admin\n\nFilter by month, year, employee, department.")
async def get_payslips(month: Optional[int] = Query(None), year: Optional[int] = Query(None), employee_id: Optional[str] = Query(None), department: Optional[str] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_payslips(current_user, month, year, employee_id, department, organization_id)

@router.get("/payslips/me", summary="My Payslips (Employee)", description="**Access:** employee\n\nView own payslips.")
async def get_my_payslips(year: Optional[int] = Query(None), db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await PayrollService(db).get_my_payslips(current_user, year)

@router.get("/payslips/{payslip_id}", summary="Get Payslip Detail", description="**Access:** org_admin, hr_admin, employee (own only)")
async def get_payslip_detail(payslip_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_any)):
    return await PayrollService(db).get_payslip_detail(payslip_id, current_user)

@router.put("/payslips/{payslip_id}", summary="Edit Payslip", description="**Access:** org_admin, hr_admin\n\nEdit bonus/TDS/deductions before approval. System recalculates net.")
async def edit_payslip(data: EditPayslipRequest, payslip_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).edit_payslip(payslip_id, data.model_dump(exclude_unset=True), current_user)

# ADJUSTMENTS
@router.post("/adjustments", status_code=201, summary="Add Adjustment", description="**Access:** org_admin, hr_admin\n\nAdd bonus/deduction/reimbursement for next payroll run.")
async def add_adjustment(data: AdjustmentRequest, organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).add_adjustment(data.model_dump(), current_user, organization_id)

@router.get("/adjustments", summary="List Adjustments", description="**Access:** org_admin, hr_admin")
async def get_adjustments(employee_id: Optional[str] = Query(None), month: Optional[int] = Query(None), year: Optional[int] = Query(None), type: Optional[str] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_adjustments(current_user, employee_id, month, year, type, organization_id)

# REPORTS
@router.get("/reports/summary", summary="Monthly Payroll Summary", description="**Access:** org_admin, hr_admin\n\nTotal gross/net/deductions + department breakdown.")
async def report_summary(month: Optional[int] = Query(None), year: Optional[int] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).report_summary(current_user, month, year, organization_id)

@router.get("/reports/annual", summary="Annual Statement", description="**Access:** org_admin, hr_admin\n\nEmployee annual earnings + TDS (Form 16 data).")
async def report_annual(employee_id: str = Query(...), year: Optional[int] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).report_annual(current_user, employee_id, year, organization_id)
