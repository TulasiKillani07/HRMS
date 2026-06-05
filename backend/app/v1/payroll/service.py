from datetime import datetime
from fastapi import HTTPException, status
from app.database import get_database
from app.models.payroll import PayrollModel
from app.v1.payroll.schema import PayrollCreateRequest

class PayrollService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()
    
    async def create_payroll(self, data: PayrollCreateRequest):
        """Create payroll record"""
        # Check if payroll already exists
        existing = await self.db.payroll.find_one({
            "employee_id": data.employee_id,
            "month": data.month,
            "year": data.year
        })
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payroll for this month already exists"
            )
        
        # Calculate gross and net salary
        allowances_total = sum(data.allowances.values()) if data.allowances else 0
        deductions_total = sum(data.deductions.values()) if data.deductions else 0
        
        gross_salary = (
            data.basic_salary + 
            allowances_total + 
            (data.overtime_pay or 0) + 
            (data.bonus or 0)
        )
        net_salary = gross_salary - deductions_total
        
        # Create payroll using PayrollModel
        payroll_model = PayrollModel(
            employee_id=data.employee_id,
            month=data.month,
            year=data.year,
            basic_salary=data.basic_salary,
            allowances=data.allowances,
            deductions=data.deductions,
            overtime_pay=data.overtime_pay,
            bonus=data.bonus,
            gross_salary=gross_salary,
            net_salary=net_salary,
            payment_status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await self.db.payroll.insert_one(payroll_model.model_dump())
        payroll_dict = payroll_model.model_dump()
        payroll_dict["_id"] = str(result.inserted_id)
        
        return payroll_dict
