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

# SETTINGS
@router.get("/settings", summary="Get Payroll Settings", description="""
**Purpose:** Get company payroll configuration.

**Access:** `org_admin`, `hr_admin`

**Response 200:**
```json
{
  "salary_structure": {
    "basic_percentage": 40,
    "hra_percentage": 25,
    "special_allowance_percentage": 25,
    "other_percentage": 10
  },
  "pf": {
    "enabled": true,
    "employee_percentage": 12,
    "employer_percentage": 12,
    "pf_applicable_on": "full_basic",
    "pf_wage_ceiling": 15000,
    "employer_pf_included_in_ctc": true
  },
  "esi": {
    "enabled": true,
    "employee_percentage": 0.75,
    "employer_percentage": 3.25,
    "salary_limit": 21000,
    "employer_esi_included_in_ctc": true
  },
  "professional_tax": {
    "enabled": true,
    "state": "Telangana",
    "amount": 200
  },
  "lop": {
    "calculation": "working_days",
    "deduction_basis": "gross"
  },
  "payroll_schedule": {
    "pay_day": 28,
    "lock_after_processing": true,
    "allow_reprocessing": false
  }
}
```
""")
async def get_settings(organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_settings(current_user, organization_id)

@router.put("/settings", summary="Update Payroll Settings", description="""
**Purpose:** Update company payroll configuration. Send only the sections you want to update.

**Access:** `org_admin`

**Important:** `salary_structure` percentages must total exactly 100%.

**Request Body (send any section):**
```json
{
  "salary_structure": {
    "basic_percentage": 50,
    "hra_percentage": 25,
    "special_allowance_percentage": 25,
    "other_percentage": 0
  },
  "pf": {
    "enabled": true,
    "employee_percentage": 12,
    "employer_percentage": 12,
    "pf_applicable_on": "full_basic",
    "pf_wage_ceiling": 15000,
    "employer_pf_included_in_ctc": true
  },
  "esi": {
    "enabled": true,
    "employee_percentage": 0.75,
    "employer_percentage": 3.25,
    "salary_limit": 21000,
    "employer_esi_included_in_ctc": true
  },
  "professional_tax": {
    "enabled": true,
    "state": "Andhra Pradesh",
    "amount": 200
  },
  "lop": {
    "calculation": "working_days",
    "deduction_basis": "gross"
  },
  "payroll_schedule": {
    "pay_day": 28,
    "lock_after_processing": true,
    "allow_reprocessing": false
  }
}
```

**Fields:**
| Section | Field | Values |
|---------|-------|--------|
| salary_structure | basic_percentage, hra_percentage, special_allowance_percentage, other_percentage | Must total 100 |
| pf | enabled, employee_percentage, employer_percentage, pf_applicable_on, pf_wage_ceiling, employer_pf_included_in_ctc | pf_applicable_on: full_basic \| pf_wage_ceiling |
| esi | enabled, employee_percentage, employer_percentage, salary_limit, employer_esi_included_in_ctc | |
| professional_tax | enabled, state, amount | |
| lop | calculation, deduction_basis | calculation: working_days \| calendar_days; deduction_basis: gross \| basic \| ctc |
| payroll_schedule | pay_day, lock_after_processing, allow_reprocessing | |

**Errors:**
- `400` — Salary structure total ≠ 100%
""")
async def update_settings(data: dict, organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_admin)):
    return await PayrollService(db).update_settings(data, current_user, organization_id)

# RUNS
@router.post("/run", status_code=201, summary="Run Payroll", description="**Access:** org_admin, hr_admin\n\nProcess payroll for a month.")
async def run_payroll(data: RunPayrollRequest, organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).run_payroll(data.month, data.year, current_user, organization_id)

@router.get("/runs", summary="List Payroll Runs", description="**Access:** org_admin, hr_admin")
async def get_runs(year: Optional[int] = Query(None), status: Optional[str] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_runs(current_user, year, status, organization_id)

@router.get("/runs/{run_id}", summary="Get Run Detail", description="**Access:** org_admin, hr_admin")
async def get_run_detail(run_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_run_detail(run_id, current_user)

@router.patch("/runs/{run_id}/approve", summary="Approve Payroll", description="**Access:** org_admin")
async def approve_run(run_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_admin)):
    return await PayrollService(db).approve_run(run_id, current_user)

@router.patch("/runs/{run_id}/mark-paid", summary="Mark as Paid", description="**Access:** org_admin")
async def mark_paid(run_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_admin)):
    return await PayrollService(db).mark_paid(run_id, current_user)

# PAYSLIPS
@router.get("/payslips", summary="List Payslips (HR)", description="**Access:** org_admin, hr_admin")
async def get_payslips(month: Optional[int] = Query(None), year: Optional[int] = Query(None), employee_id: Optional[str] = Query(None), department: Optional[str] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_payslips(current_user, month, year, employee_id, department, organization_id)

@router.get("/payslips/me", summary="My Payslips", description="**Access:** employee")
async def get_my_payslips(year: Optional[int] = Query(None), db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await PayrollService(db).get_my_payslips(current_user, year)

@router.get("/payslips/{payslip_id}", summary="Get Payslip Detail", description="**Access:** all (employee sees own only)")
async def get_payslip_detail(payslip_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_any)):
    return await PayrollService(db).get_payslip_detail(payslip_id, current_user)

# ADJUSTMENTS
@router.post("/adjustments", status_code=201, summary="Add Adjustment", description="**Access:** org_admin, hr_admin")
async def add_adjustment(data: AdjustmentRequest, organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).add_adjustment(data.model_dump(), current_user, organization_id)

@router.get("/adjustments", summary="List Adjustments", description="**Access:** org_admin, hr_admin")
async def get_adjustments(employee_id: Optional[str] = Query(None), month: Optional[int] = Query(None), year: Optional[int] = Query(None), type: Optional[str] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).get_adjustments(current_user, employee_id, month, year, type, organization_id)

# REPORTS
@router.get("/reports/summary", summary="Monthly Summary", description="**Access:** org_admin, hr_admin")
async def report_summary(month: Optional[int] = Query(None), year: Optional[int] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).report_summary(current_user, month, year, organization_id)

@router.get("/reports/annual", summary="Annual Statement", description="**Access:** org_admin, hr_admin")
async def report_annual(employee_id: str = Query(...), year: Optional[int] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).report_annual(current_user, employee_id, year, organization_id)


@router.get("/reports/bank-transfer", summary="Bank Transfer Report", description="**Access:** org_admin, hr_admin\n\nList of employees with net pay + bank details for bulk payment.")
async def report_bank_transfer(month: Optional[int] = Query(None), year: Optional[int] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).report_bank_transfer(current_user, month, year, organization_id)


@router.get("/reports/salary-register", summary="Salary Register", description="**Access:** org_admin, hr_admin\n\nDetailed register with all salary components for every employee.")
async def report_salary_register(month: Optional[int] = Query(None), year: Optional[int] = Query(None), department: Optional[str] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).report_salary_register(current_user, month, year, department, organization_id)

@router.get("/reports/department", summary="Department Payroll Summary", description="**Access:** org_admin, hr_admin\n\nDepartment-wise totals (gross, net, PF, ESI, PT, LOP, employer cost).")
async def report_department(month: Optional[int] = Query(None), year: Optional[int] = Query(None), organization_id: Optional[str] = Query(None), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await PayrollService(db).report_department_summary(current_user, month, year, organization_id)
