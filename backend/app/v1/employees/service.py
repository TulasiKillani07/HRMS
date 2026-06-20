from datetime import datetime
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.employee import EmployeeModel
from app.utils.helpers import paginate_query
from app.utils.logger import logger
from app.v1.employees.schema import EmployeeCreateRequest, EmployeeUpdateRequest


class EmployeeService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _serialize(self, emp: dict) -> dict:
        emp["id"] = str(emp["_id"])
        del emp["_id"]
        return emp

    def _org_id_from_user(self, current_user: dict, explicit_org_id: str = None) -> str:
        """
        Resolve organization_id:
        - superadmin: uses explicit_org_id passed in (required)
        - org_admin / hr_admin: uses organization_id from their profile
        """
        role = current_user.get("role")
        if role == "superadmin":
            if not explicit_org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="superadmin must supply organization_id"
                )
            return explicit_org_id
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account is not linked to any organization"
            )
        return org_id

    async def _check_emp_limit(self, org_id: str) -> None:
        """Raise 403 if the org has hit its emp_count_for_access limit."""
        org = await self.db.organizations.find_one(
            {"_id": ObjectId(org_id), "is_deleted": False},
            {"emp_count_for_access": 1}
        )
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        limit = org.get("emp_count_for_access", 0)
        current_count = await self.db.employees.count_documents({
            "organization_id": org_id,
            "is_deleted": False
        })
        if current_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Employee limit reached for this organization. "
                    f"Limit: {limit}, Current: {current_count}"
                )
            )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_employee(self, data: EmployeeCreateRequest, current_user: dict) -> dict:
        org_id = self._org_id_from_user(current_user, data.organization_id)

        # Check employee limit (exclude deleted)
        await self._check_emp_limit(org_id)

        # Unique employee_id within the org (exclude deleted)
        existing_id = await self.db.employees.find_one({
            "employee_id": data.employee_id,
            "organization_id": org_id,
            "is_deleted": False
        })
        if existing_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee ID already exists in this organization"
            )

        # Unique email globally across active employees
        existing_email = await self.db.employees.find_one({
            "email": data.email,
            "is_deleted": False
        })
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )

        # Validate department belongs to same org (if provided)
        if data.department_id:
            dept = await self.db.departments.find_one({
                "_id": ObjectId(data.department_id),
                "organization_id": org_id,
                "status": "active"
            })
            if not dept:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Department not found in your organization"
                )

        employee_model = EmployeeModel(
            employee_id=data.employee_id,
            organization_id=org_id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            date_of_birth=datetime.combine(data.date_of_birth, datetime.min.time()),
            gender=data.gender,
            address=data.address,
            department_id=data.department_id,
            designation=data.designation,
            joining_date=datetime.combine(data.joining_date, datetime.min.time()),
            employment_type=data.employment_type,
            status="active",
            salary=data.salary,
            bank_account=data.bank_account,
            emergency_contact=data.emergency_contact,
            is_deleted=False,
            deleted_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        result = await self.db.employees.insert_one(employee_model.model_dump())
        emp_dict = employee_model.model_dump()
        emp_dict["id"] = str(result.inserted_id)

        logger.info(f"Employee {data.employee_id} created in org {org_id} by {current_user.get('email')}")
        return emp_dict

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def get_employees(
        self,
        current_user: dict,
        page: int = 1,
        limit: int = 10,
        status_filter: str = None,
        department_id: str = None,
        search: str = None,
        include_deleted: bool = False,
        organization_id: str = None
    ) -> dict:
        org_id = self._org_id_from_user(current_user, organization_id)
        skip, limit = paginate_query(page, limit)

        query: dict = {"organization_id": org_id}

        if not include_deleted:
            query["is_deleted"] = False

        if status_filter:
            query["status"] = status_filter
        if department_id:
            query["department_id"] = department_id
        if search:
            query["$or"] = [
                {"first_name": {"$regex": search, "$options": "i"}},
                {"last_name":  {"$regex": search, "$options": "i"}},
                {"email":      {"$regex": search, "$options": "i"}},
                {"employee_id":{"$regex": search, "$options": "i"}},
                {"designation":{"$regex": search, "$options": "i"}},
            ]

        total = await self.db.employees.count_documents(query)
        cursor = self.db.employees.find(query).skip(skip).limit(limit).sort("created_at", -1)
        employees = await cursor.to_list(length=limit)

        for emp in employees:
            self._serialize(emp)

        return {
            "employees": employees,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    # ------------------------------------------------------------------
    # Get single
    # ------------------------------------------------------------------

    async def get_employee_by_id(self, employee_id: str, current_user: dict) -> dict:
        role = current_user.get("role")

        try:
            query: dict = {"_id": ObjectId(employee_id), "is_deleted": False}
            # Non-superadmin: restrict to their org
            if role != "superadmin":
                query["organization_id"] = self._org_id_from_user(current_user)
            emp = await self.db.employees.find_one(query)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid employee ID format"
            )

        if not emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        return self._serialize(emp)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_employee(
        self, employee_id: str, data: EmployeeUpdateRequest, current_user: dict
    ) -> dict:
        role = current_user.get("role")

        try:
            query: dict = {"_id": ObjectId(employee_id), "is_deleted": False}
            if role != "superadmin":
                query["organization_id"] = self._org_id_from_user(current_user)
            emp = await self.db.employees.find_one(query)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid employee ID format"
            )

        if not emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        org_id = emp["organization_id"]  # always use the employee's actual org for dept validation

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided to update"
            )

        # Email uniqueness if changed
        if "email" in update_data and update_data["email"] != emp["email"]:
            existing = await self.db.employees.find_one({"email": update_data["email"]})
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )

        # Validate department belongs to same org if changed
        if "department_id" in update_data and update_data["department_id"]:
            dept = await self.db.departments.find_one({
                "_id": ObjectId(update_data["department_id"]),
                "organization_id": org_id,
                "status": "active"
            })
            if not dept:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Department not found in your organization"
                )

        # Validate status value
        if "status" in update_data:
            valid_statuses = {"active", "inactive", "terminated"}
            if update_data["status"] not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be one of: {valid_statuses}"
                )

        update_data["updated_at"] = datetime.utcnow()

        await self.db.employees.update_one(
            {"_id": ObjectId(employee_id)},
            {"$set": update_data}
        )

        logger.info(f"Employee {employee_id} updated by {current_user.get('email')}")

        updated = await self.db.employees.find_one({"_id": ObjectId(employee_id)})
        return self._serialize(updated)

    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    async def delete_employee(self, employee_id: str, current_user: dict) -> dict:
        role = current_user.get("role")

        try:
            query: dict = {"_id": ObjectId(employee_id), "is_deleted": False}
            if role != "superadmin":
                query["organization_id"] = self._org_id_from_user(current_user)
            emp = await self.db.employees.find_one(query)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid employee ID format"
            )

        if not emp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )

        await self.db.employees.update_one(
            {"_id": ObjectId(employee_id)},
            {
                "$set": {
                    "is_deleted": True,
                    "deleted_at": datetime.utcnow(),
                    "status": "inactive",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(f"Employee {employee_id} soft deleted by {current_user.get('email')}")
        return {"message": "Employee deleted successfully", "employee_id": employee_id}
