from datetime import datetime
from fastapi import HTTPException, status
from app.database import get_database
from app.models.employee import EmployeeModel
from app.utils.helpers import convert_objectid_to_str, paginate_query
from app.v1.employees.schema import EmployeeCreateRequest, EmployeeUpdateRequest

class EmployeeService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()
    
    async def create_employee(self, data: EmployeeCreateRequest):
        """Create a new employee"""
        # Check if employee_id already exists
        existing = await self.db.employees.find_one({"employee_id": data.employee_id})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee ID already exists"
            )
        
        # Check if email already exists
        existing_email = await self.db.employees.find_one({"email": data.email})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        
        # Create employee using EmployeeModel
        employee_model = EmployeeModel(
            employee_id=data.employee_id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            address=data.address,
            department_id=data.department_id,
            designation=data.designation,
            joining_date=data.joining_date,
            employment_type=data.employment_type,
            status="active",
            salary=data.salary,
            bank_account=data.bank_account,
            emergency_contact=data.emergency_contact,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await self.db.employees.insert_one(employee_model.model_dump())
        employee_dict = employee_model.model_dump()
        employee_dict["_id"] = str(result.inserted_id)
        
        return convert_objectid_to_str(employee_dict)

    async def get_employees(self, page: int = 1, limit: int = 10):
        """Get all employees with pagination"""
        skip, limit = paginate_query(page, limit)
        
        cursor = self.db.employees.find().skip(skip).limit(limit)
        employees = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for emp in employees:
            emp["_id"] = str(emp["_id"])
        
        return employees
