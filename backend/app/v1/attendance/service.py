from datetime import datetime, date
from fastapi import HTTPException, status
from app.database import get_database
from app.models.attendance import AttendanceModel

class AttendanceService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()
    
    async def check_in(self, employee_id: str):
        """Record employee check-in"""
        today = date.today()
        
        # Check if already checked in
        existing = await self.db.attendance.find_one({
            "employee_id": employee_id,
            "date": today
        })
        
        if existing and existing.get("check_in"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already checked in today"
            )
        
        # Create attendance using AttendanceModel
        attendance_model = AttendanceModel(
            employee_id=employee_id,
            date=today,
            check_in=datetime.utcnow(),
            status="present",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        if existing:
            await self.db.attendance.update_one(
                {"_id": existing["_id"]},
                {"$set": attendance_model.model_dump()}
            )
            attendance_dict = attendance_model.model_dump()
            attendance_dict["_id"] = str(existing["_id"])
        else:
            result = await self.db.attendance.insert_one(attendance_model.model_dump())
            attendance_dict = attendance_model.model_dump()
            attendance_dict["_id"] = str(result.inserted_id)
        
        return attendance_dict
