from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Phase 1: Company Payroll Settings (one per org)
# ---------------------------------------------------------------------------

class CompanyPayrollSettingsModel(BaseModel):
    """One document per company — stored in db.company_payroll_settings"""
    organization_id: str

    # Section 1: Salary Structure
    salary_structure: dict = {
        "basic_percentage": 40,
        "hra_percentage": 20,
        "special_allowance_percentage": 15,
        "other_percentage": 0
        # Note: total must = 100
    }

    # Section 2: Provident Fund (PF)
    pf: dict = {
        "enabled": True,
        "employee_percentage": 12,
        "employer_percentage": 12,
        "pf_applicable_on": "full_basic",    # full_basic | pf_wage_ceiling
        "pf_wage_ceiling": 15000,
        "employer_pf_included_in_ctc": True
    }

    # Section 3: Employee State Insurance (ESI)
    esi: dict = {
        "enabled": True,
        "employee_percentage": 0.75,
        "employer_percentage": 3.25,
        "salary_limit": 21000,
        "employer_esi_included_in_ctc": True
    }

    # Section 4: Professional Tax (PT)
    professional_tax: dict = {
        "enabled": True,
        "state": "Telangana",
        "amount": 200
        # Future: slabs support
    }

    # Section 5: Loss of Pay (LOP)
    lop: dict = {
        "calculation": "working_days",          # working_days | calendar_days
        "deduction_basis": "gross"              # gross | basic | ctc
    }

    # Section 6: Payroll Schedule
    payroll_schedule: dict = {
        "pay_day": 28,
        "lock_after_processing": True,          # Lock payroll after processing
        "allow_reprocessing": False             # Allow re-running payroll for a month
    }

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Phase 2: Payroll Run
# ---------------------------------------------------------------------------

class PayrollRunModel(BaseModel):
    """Payroll run — stored in db.payroll_runs"""
    organization_id: str
    month: int
    year: int
    status: str = "draft"                        # draft | processed | approved | paid
    total_gross: float = 0
    total_deductions: float = 0
    total_net: float = 0
    employee_count: int = 0
    processed_by: Optional[str] = None
    processed_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Phase 2: Payslip
# ---------------------------------------------------------------------------

class PayslipModel(BaseModel):
    """Employee payslip — stored in db.payslips"""
    organization_id: str
    payroll_run_id: str
    employee_id: str
    employee_name: str
    employee_code: str
    department: str
    month: int
    year: int
    monthly_ctc: float = 0
    working_days: int = 0
    days_worked: int = 0
    lop_days: int = 0
    earnings: dict = {}
    gross_salary: float = 0
    lop_deduction: float = 0
    gross_after_lop: float = 0
    deductions: dict = {}
    total_deductions: float = 0
    employer_contributions: dict = {}
    total_employer_cost: float = 0
    net_pay: float = 0
    # Phase 5: History fields
    pf_employee: float = 0
    esi_employee: float = 0
    professional_tax: float = 0
    pf_employer: float = 0
    esi_employer: float = 0
    status: str = "processed"                    # processed | approved | paid
    generated_by: Optional[str] = None
    generated_by_name: Optional[str] = None
    generated_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Payroll Adjustment
# ---------------------------------------------------------------------------

class PayrollAdjustmentModel(BaseModel):
    """Bonus/deduction for next payroll — stored in db.payroll_adjustments"""
    organization_id: str
    employee_id: str
    employee_name: str
    type: str                                    # bonus | deduction | reimbursement
    amount: float
    description: str
    month: int
    year: int
    applied: bool = False
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
