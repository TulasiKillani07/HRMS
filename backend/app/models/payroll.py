from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PayrollConfigModel(BaseModel):
    """Org-level payroll config — stored in db.payroll_configs"""
    organization_id: str
    # Salary split percentages (of CTC)
    basic_percentage: float = 40.0               # Basic = CTC × 40%
    hra_percentage: float = 20.0                 # HRA = CTC × 20%
    special_allowance_percentage: float = 15.0   # Special = CTC × 15%
    # Statutory deductions
    pf_percentage: float = 12.0
    esi_employee_percentage: float = 0.75
    esi_employer_percentage: float = 3.25
    esi_limit: float = 21000
    professional_tax: float = 200
    pay_day: int = 28
    pay_cycle: str = "monthly"
    lop_calculation: str = "calendar_days"       # calendar_days | working_days
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    working_days: int = 0
    days_worked: int = 0
    lop_days: int = 0
    earnings: dict = {}
    gross_pay: float = 0
    deductions: dict = {}
    total_deductions: float = 0
    net_pay: float = 0
    employer_contributions: dict = {}
    status: str = "processed"                    # processed | approved | paid
    paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    applied: bool = False                        # True after payroll run processes it
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
