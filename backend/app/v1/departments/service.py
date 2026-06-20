from datetime import datetime
from fastapi import HTTPException, status
from app.database import get_database
from app.models.department import DepartmentModel
from app.utils.logger import logger
from app.v1.departments.schema import DepartmentCreateRequest


class DepartmentService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    async def create_department(self, data: DepartmentCreateRequest, current_user: dict):
        """Create a new department scoped to the caller's organization"""
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account is not linked to any organization"
            )

        # Code must be unique within the organization
        existing = await self.db.departments.find_one({
            "code": data.code.upper(),
            "organization_id": org_id
        })
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department code already exists in your organization"
            )

        dept_model = DepartmentModel(
            organization_id=org_id,
            name=data.name,
            code=data.code.upper(),
            description=data.description,
            manager_id=data.manager_id,
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        result = await self.db.departments.insert_one(dept_model.model_dump())
        dept_dict = dept_model.model_dump()
        dept_dict["id"] = str(result.inserted_id)

        logger.info(f"Department '{data.name}' created in org {org_id} by {current_user.get('email')}")
        return dept_dict
