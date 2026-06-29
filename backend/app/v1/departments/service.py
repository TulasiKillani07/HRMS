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
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        result = await self.db.departments.insert_one(dept_model.model_dump())
        dept_dict = dept_model.model_dump()
        dept_dict["id"] = str(result.inserted_id)

        logger.info(f"Department '{data.name}' created in org {org_id} by {current_user.get('email')}")

        # Activity log
        from app.v1.activity_logs.service import ActivityLogService
        await ActivityLogService(self.db).log(
            user=current_user, action="created", module="department",
            description=f"Created department '{data.name}' ({data.code.upper()})",
            target_id=dept_dict["id"], target_name=data.name, target_type="department"
        )

        return dept_dict

    async def get_departments(self, current_user: dict, status_filter: str = None) -> dict:
        """List all departments in the organization"""
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(status_code=400, detail="No organization linked")

        query = {"organization_id": org_id}
        if status_filter:
            query["status"] = status_filter

        cursor = self.db.departments.find(query).sort("name", 1)
        depts = await cursor.to_list(length=100)
        for d in depts:
            d["id"] = str(d["_id"])
            del d["_id"]

        return {"departments": depts, "total": len(depts)}

    async def get_department_by_id(self, dept_id: str, current_user: dict) -> dict:
        """Get single department"""
        from bson import ObjectId
        org_id = current_user.get("organization_id")
        try:
            obj_id = ObjectId(dept_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid department ID")

        dept = await self.db.departments.find_one({"_id": obj_id, "organization_id": org_id})
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")

        dept["id"] = str(dept["_id"])
        del dept["_id"]

        # Get employee count
        emp_count = await self.db.employees.count_documents({
            "organization_id": org_id, "department": dept["name"], "is_deleted": False
        })
        dept["employee_count"] = emp_count

        return dept

    async def update_department(self, dept_id: str, data, current_user: dict) -> dict:
        """Update department"""
        from bson import ObjectId
        org_id = current_user.get("organization_id")
        try:
            obj_id = ObjectId(dept_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid department ID")

        dept = await self.db.departments.find_one({"_id": obj_id, "organization_id": org_id})
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")

        update = data.model_dump(exclude_unset=True)
        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")

        update["updated_at"] = datetime.utcnow()
        await self.db.departments.update_one({"_id": obj_id}, {"$set": update})

        logger.info(f"Department {dept_id} updated by {current_user.get('email')}")
        updated = await self.db.departments.find_one({"_id": obj_id})
        updated["id"] = str(updated["_id"])
        del updated["_id"]
        return updated

    async def delete_department(self, dept_id: str, current_user: dict) -> dict:
        """Deactivate department"""
        from bson import ObjectId
        org_id = current_user.get("organization_id")
        try:
            obj_id = ObjectId(dept_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid department ID")

        dept = await self.db.departments.find_one({"_id": obj_id, "organization_id": org_id})
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")

        # Check if employees exist in this department
        emp_count = await self.db.employees.count_documents({
            "organization_id": org_id, "department": dept["name"], "is_deleted": False
        })
        if emp_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete: {emp_count} employee(s) still in this department"
            )

        await self.db.departments.update_one(
            {"_id": obj_id}, {"$set": {"status": "inactive", "updated_at": datetime.utcnow()}}
        )
        logger.info(f"Department '{dept['name']}' deactivated by {current_user.get('email')}")
        return {"message": f"Department '{dept['name']}' deactivated successfully"}

    async def import_departments_csv(self, file, current_user: dict) -> dict:
        """Bulk import departments from CSV"""
        import io
        import csv

        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(status_code=400, detail="No organization linked")

        content = await file.read()
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))

        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV is empty or has no headers")

        normalized = {c.strip().lower() for c in reader.fieldnames}
        if "name" not in normalized or "code" not in normalized:
            raise HTTPException(status_code=400, detail="CSV must have 'name' and 'code' columns. Optional: 'description'")

        imported = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            name = row.get("name", "").strip()
            code = row.get("code", "").strip().upper()
            description = row.get("description", "").strip() or None

            if not name:
                errors.append({"row": row_num, "error": "Missing department name"})
                continue
            if not code:
                errors.append({"row": row_num, "error": "Missing department code"})
                continue

            # Duplicate check
            existing = await self.db.departments.find_one({
                "code": code, "organization_id": org_id
            })
            if existing:
                errors.append({"row": row_num, "code": code, "error": f"Code '{code}' already exists"})
                continue

            from app.models.department import DepartmentModel
            dept = DepartmentModel(
                organization_id=org_id, name=name, code=code,
                description=description,
                status="active", created_at=datetime.utcnow(), updated_at=datetime.utcnow()
            )
            await self.db.departments.insert_one(dept.model_dump())
            imported += 1

        logger.info(f"Department CSV import: {imported} imported, {len(errors)} failed for org {org_id}")
        return {"imported": imported, "failed": len(errors), "errors": errors}
