from datetime import datetime
from fastapi import HTTPException, status
from app.database import get_database
from app.models.leave import LeaveModel
from app.v1.leaves.schema import LeaveCreateRequest

class LeaveService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()
    
    async def create_leave_request(self, data: LeaveCreateRequest):
        """Create a new leave request"""
        days = (data.end_date - data.start_date).days + 1
        
        if days <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date range"
            )
        
        # Create leave using LeaveModel
        leave_model = LeaveModel(
            employee_id=data.employee_id,
            leave_type=data.leave_type,
            start_date=data.start_date,
            end_date=data.end_date,
            days=days,
            reason=data.reason,
            status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await self.db.leaves.insert_one(leave_model.model_dump())
        leave_dict = leave_model.model_dump()
        leave_dict["_id"] = str(result.inserted_id)
        
        return leave_dict
