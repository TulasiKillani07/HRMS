from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field

class PayrollModel(BaseModel):
    """Payroll database model"""
    employee_id: str
    month: int
    year: int
    basic_salary: float
    allowances: Optional[dict] = None  # HRA, transport, etc.
    deductions: Optional[dict] = None  # tax, insurance, etc.
    overtime_pay: Optional[float] = 0.0
    bonus: Optional[float] = 0.0
    gross_salary: float
    net_salary: float
    payment_date: Optional[date] = None
    payment_status: str = "pending"  # pending, processed, paid
    payment_method: Optional[str] = None  # bank_transfer, cash, cheque
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "EMP001",
                "month": 1,
                "year": 2024,
                "basic_salary": 50000.0,
                "allowances": {"hra": 10000, "transport": 2000},
                "deductions": {"tax": 5000, "insurance": 1000},
                "gross_salary": 62000.0,
                "net_salary": 56000.0,
                "payment_status": "pending"
            }
        }
