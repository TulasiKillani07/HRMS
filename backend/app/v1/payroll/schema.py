from pydantic import BaseModel
from typing import Optional

class PayrollCreateRequest(BaseModel):
    employee_id: str
    month: int
    year: int
    basic_salary: float
    allowances: Optional[dict] = None
    deductions: Optional[dict] = None
    overtime_pay: Optional[float] = 0.0
    bonus: Optional[float] = 0.0

class PayrollResponse(BaseModel):
    id: str
    employee_id: str
    month: int
    year: int
    basic_salary: float
    gross_salary: float
    net_salary: float
    payment_status: str
    
    class Config:
        from_attributes = True
