from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PayrollConfigModel(BaseModel):
    """Org-level payroll config — stored in db.payroll_configs"""
    organization_id: str
    # Dynamic earning components (each has name + percentage of CTC)
    earning_components: List[dict] = [
        {"name": "Basic", "percentage": 40},
        {"name": "HRA", "percentage": 20},
        {"name": "Special Allowance", "percentage": 15}
    ]
    # Dynamic deduction components
    deduction_components: List[dict] = [
        {"name": "PF", "percentage": 12, "basis": "basic"},         # % of basic
        {"name": "ESI", "percentage": 0.75, "basis": "gross", "limit": 21000},
        {"name": "Professional Tax", "amount": 200, "type": "fixed"},
        {"name": "TDS", "percentage": 0, "basis": "gross_after_lop"}
    ]
    # Dynamic employer contribution components
    employer_components: List[dict] = [
        {"name": "PF Employer", "percentage": 12, "basis": "basic"},
        {"name": "ESI Employer", "percentage": 3.25, "basis": "gross", "limit": 21000},
        {"name": "Gratuity", "percentage": 0, "basis": "basic"},
        {"name": "Insurance", "amount": 0, "type": "fixed"}
    ]
    # LOP settings
    lop_deduction_basis: str = "gross"           # gross | basic | ctc
    lop_calculation: str = "working_days"        # calendar_days | working_days
    # Pay settings
    pay_day: int = 28
    pay_cycle: str = "monthly"
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
