import io
import csv
from datetime import datetime
from fastapi import HTTPException, status, UploadFile
from bson import ObjectId
from app.database import get_database
from app.models.employee import (
    EmployeeModel, SalaryStructure,
    ONBOARDING_SECTIONS, CRITICAL_SECTIONS,
    SectionStatus, default_onboarding_sections
)
from app.models.user import UserModel
from app.core.security import get_password_hash
from app.utils.helpers import paginate_query
from app.utils.logger import logger
from app.utils.notifications import (
    send_employee_welcome_email,
    send_onboarding_revision_email
)
from app.v1.employees.schema import (
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    VerifyEmployeeRequest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(emp: dict) -> dict:
    emp["id"] = str(emp["_id"])
    del emp["_id"]
    # Remove deprecated documents section from response
    emp.pop("documents", None)
    if "onboarding_sections" in emp and isinstance(emp["onboarding_sections"], dict):
        emp["onboarding_sections"].pop("documents", None)
        # If fresher, mark experience as not_applicable
        if emp.get("is_fresher") and "experience" in emp["onboarding_sections"]:
            if emp["onboarding_sections"]["experience"].get("status") == "pending":
                emp["onboarding_sections"]["experience"]["status"] = "not_applicable"
        # Recalculate progress dynamically
        emp["onboarding_progress"] = _calc_progress(emp["onboarding_sections"])
    return emp


def _calc_progress(sections: dict) -> int:
    if not sections:
        return 0
    # Exclude not_applicable sections from total count
    applicable = {k: v for k, v in sections.items() if v.get("status") != "not_applicable"}
    if not applicable:
        return 100
    completed = sum(
        1 for s in applicable.values()
        if s.get("status") == "completed"
    )
    return round((completed / len(applicable)) * 100)


# ---------------------------------------------------------------------------
# EmployeeService
# ---------------------------------------------------------------------------

class EmployeeService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    # ------------------------------------------------------------------
    # Org resolution
    # ------------------------------------------------------------------

    def _org_id_from_user(self, current_user: dict, explicit_org_id: str = None) -> str:
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

    # ------------------------------------------------------------------
    # Employee limit check
    # ------------------------------------------------------------------

    async def _check_emp_limit(self, org_id: str) -> None:
        org = await self.db.organizations.find_one(
            {"_id": ObjectId(org_id), "is_deleted": False},
            {"emp_count_for_access": 1}
        )
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        limit = org.get("emp_count_for_access", 0)
        current_count = await self.db.employees.count_documents({
            "organization_id": org_id,
            "is_deleted": False
        })
        if current_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Employee limit reached. Limit: {limit}, Current: {current_count}"
            )

    # ------------------------------------------------------------------
    # Internal: create one employee + user account
    # ------------------------------------------------------------------

    async def _create_single_employee(
        self,
        org_id: str,
        data: dict,
        org_name: str
    ) -> tuple[dict, bool]:
        """
        Returns (employee_dict, invite_sent).
        Raises HTTPException on validation errors.
        """
        # Note: UAN is now optional - collected during onboarding in government_ids section
        # No validation needed here

        # Validate department exists in this organization
        dept_name = data.get("department", "").strip()
        if dept_name:
            dept_exists = await self.db.departments.find_one({
                "organization_id": org_id,
                "name": dept_name,
                "status": "active"
            })
            if not dept_exists:
                raise HTTPException(
                    status_code=400,
                    detail=f"Department '{dept_name}' does not exist. Create it first or check the name."
                )

        # Duplicate checks
        dup_id = await self.db.employees.find_one({
            "employee_id": data["employee_id"],
            "organization_id": org_id,
            "is_deleted": False
        })
        if dup_id:
            raise HTTPException(
                status_code=400,
                detail=f"Employee ID '{data['employee_id']}' already exists in this organization"
            )

        dup_email = await self.db.employees.find_one({
            "official_email": data["official_email"],
            "is_deleted": False
        })
        if dup_email:
            raise HTTPException(
                status_code=400,
                detail=f"Email '{data['official_email']}' is already used by another employee"
            )

        # Check users collection — covers org_admin, hr_admin, and existing employee accounts
        dup_user = await self.db.users.find_one({"email": data["official_email"]})
        if dup_user:
            role = dup_user.get("role", "user")
            role_label = {
                "org_admin": "an Organization Admin",
                "hr_admin": "an HR Admin",
                "employee": "an existing employee",
                "superadmin": "a Superadmin"
            }.get(role, f"a {role}")
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Email '{data['official_email']}' is already registered as {role_label}. "
                    f"Each person must have a unique email across the entire system."
                )
            )

        # Create user account
        temp_password = "Welcome1"
        user_model = UserModel(
            email=data["official_email"],
            hashed_password=get_password_hash(temp_password),
            full_name=f"{data['first_name']} {data['last_name']}",
            role="employee",
            phone=data.get("phone"),
            is_active=True,
            is_verified=False,
            requires_password_change=True,
            organization_id=org_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        user_result = await self.db.users.insert_one(user_model.model_dump())
        user_id = str(user_result.inserted_id)

        # Build salary structure
        sal = data.get("salary_structure", {})
        if isinstance(sal, dict):
            salary_structure = SalaryStructure(
                basic=sal.get("basic", 0),
                hra=sal.get("hra", 0),
                special_allowance=sal.get("special_allowance", 0),
                ctc=sal.get("ctc", 0)
            )
        else:
            salary_structure = sal  # already SalaryStructure instance

        # Create employee record
        emp_model = EmployeeModel(
            organization_id=org_id,
            employee_id=data["employee_id"],
            user_id=user_id,
            first_name=data["first_name"],
            last_name=data["last_name"],
            official_email=data["official_email"],
            phone=data.get("phone", ""),
            gender=data.get("gender"),
            department=data.get("department", ""),
            designation=data.get("designation", ""),
            reporting_manager=data.get("reporting_manager"),
            joining_date=data.get("joining_date", ""),
            employment_type=data.get("employment_type", "full-time"),
            shift=data.get("shift"),
            work_location=data.get("work_location"),
            salary_structure=salary_structure,
            is_fresher=data.get("is_fresher"),
            uan_number=data.get("uan_number") if not data.get("is_fresher") else None,
            status="pending_onboarding",
            onboarding_progress=0,
            onboarding_sections=default_onboarding_sections(),
            is_deleted=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # If fresher, auto-mark experience as completed (not applicable)
        if data.get("is_fresher"):
            emp_dict_temp = emp_model.model_dump()
            emp_dict_temp["onboarding_sections"]["experience"]["status"] = "not_applicable"
            emp_model = EmployeeModel(**emp_dict_temp)

        emp_result = await self.db.employees.insert_one(emp_model.model_dump())
        emp_dict = emp_model.model_dump()
        emp_dict["id"] = str(emp_result.inserted_id)

        # Update user with employee reference
        await self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"employee_id": emp_dict["id"], "updated_at": datetime.utcnow()}}
        )

        # Send welcome email
        invite_sent = await send_employee_welcome_email(
            email=data["official_email"],
            first_name=data["first_name"],
            org_name=org_name,
            temp_password=temp_password
        )

        logger.info(
            f"Employee {data['employee_id']} created in org {org_id}, "
            f"user {user_id}, invite_sent={invite_sent}"
        )
        return emp_dict, invite_sent

    # ------------------------------------------------------------------
    # 1. Create employee (manual)
    # ------------------------------------------------------------------

    async def create_employee(
        self, data: EmployeeCreateRequest, current_user: dict
    ) -> dict:
        org_id = self._org_id_from_user(current_user, data.organization_id)
        await self._check_emp_limit(org_id)

        org = await self.db.organizations.find_one(
            {"_id": ObjectId(org_id)}, {"org_name": 1}
        )
        org_name = org.get("org_name", "Your Company") if org else "Your Company"

        emp_dict, invite_sent = await self._create_single_employee(
            org_id=org_id,
            data=data.model_dump(),
            org_name=org_name
        )

        return {
            "id": emp_dict["id"],
            "employee_id": emp_dict["employee_id"],
            "status": emp_dict["status"],
            "onboarding_progress": emp_dict["onboarding_progress"],
            "invite_sent": invite_sent,
            "created_at": emp_dict["created_at"]
        }

    # ------------------------------------------------------------------
    # 2. CSV import
    # ------------------------------------------------------------------

    async def import_employees_csv(
        self, file: UploadFile, current_user: dict
    ) -> dict:
        org_id = self._org_id_from_user(current_user, None
                                        if current_user.get("role") != "superadmin"
                                        else current_user.get("organization_id"))

        org = await self.db.organizations.find_one(
            {"_id": ObjectId(org_id)}, {"org_name": 1, "emp_count_for_access": 1}
        )
        org_name = org.get("org_name", "Your Company") if org else "Your Company"

        # Read CSV content
        content = await file.read()
        try:
            text = content.decode("utf-8-sig")   # handle BOM
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))

        REQUIRED_COLS = {
            "employee_id", "first_name", "last_name", "official_email",
            "phone", "department", "designation", "joining_date", "ctc"
        }

        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV file is empty or has no headers")

        missing_cols = REQUIRED_COLS - {c.strip().lower() for c in reader.fieldnames}
        if missing_cols:
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing required columns: {missing_cols}"
            )

        imported = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):  # row 1 is header
            # Normalise keys
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

            emp_id = row.get("employee_id", "").strip()
            email = row.get("official_email", "").strip()

            # Required field checks
            missing = [f for f in REQUIRED_COLS if not row.get(f)]
            if missing:
                errors.append({
                    "row": row_num,
                    "employee_id": emp_id or None,
                    "email": email or None,
                    "error": f"Missing required fields: {missing}"
                })
                continue

            # Basic email format check
            if "@" not in email or "." not in email.split("@")[-1]:
                errors.append({
                    "row": row_num, "employee_id": emp_id, "email": email,
                    "error": "Invalid email format"
                })
                continue

            # Duplicate check
            dup_id = await self.db.employees.find_one({
                "employee_id": emp_id, "organization_id": org_id, "is_deleted": False
            })
            if dup_id:
                errors.append({
                    "row": row_num, "employee_id": emp_id, "email": email,
                    "error": f"Duplicate: employee_id '{emp_id}' already exists"
                })
                continue

            dup_email = await self.db.employees.find_one({
                "official_email": email, "is_deleted": False
            })
            if dup_email:
                errors.append({
                    "row": row_num, "employee_id": emp_id, "email": email,
                    "error": f"Duplicate: email '{email}' is already used by another employee"
                })
                continue

            # Also check users collection (hr_admin, org_admin, etc.)
            dup_user = await self.db.users.find_one({"email": email})
            if dup_user:
                role = dup_user.get("role", "user")
                role_label = {
                    "org_admin": "an Organization Admin",
                    "hr_admin": "an HR Admin",
                    "employee": "an existing employee",
                    "superadmin": "a Superadmin"
                }.get(role, f"a {role}")
                errors.append({
                    "row": row_num, "employee_id": emp_id, "email": email,
                    "error": f"Email '{email}' is already registered as {role_label}"
                })
                continue

            # CTC parse
            try:
                ctc = float(row.get("ctc", 0))
            except ValueError:
                errors.append({
                    "row": row_num, "employee_id": emp_id, "email": email,
                    "error": "Invalid CTC value"
                })
                continue

            # Check remaining employee limit
            current_count = await self.db.employees.count_documents({
                "organization_id": org_id, "is_deleted": False
            })
            limit = org.get("emp_count_for_access", 0) if org else 0
            if current_count >= limit:
                errors.append({
                    "row": row_num, "employee_id": emp_id, "email": email,
                    "error": "Organization employee limit reached, stopping further imports"
                })
                # Stop processing further rows
                break

            try:
                await self._create_single_employee(
                    org_id=org_id,
                    data={
                        "employee_id": emp_id,
                        "first_name": row.get("first_name", ""),
                        "last_name": row.get("last_name", ""),
                        "official_email": email,
                        "phone": row.get("phone", ""),
                        "department": row.get("department", ""),
                        "designation": row.get("designation", ""),
                        "reporting_manager": row.get("reporting_manager"),
                        "joining_date": row.get("joining_date", ""),
                        "employment_type": row.get("employment_type", "full-time"),
                        "salary_structure": {
                            "basic": ctc * 0.4,
                            "hra": ctc * 0.2,
                            "special_allowance": ctc * 0.15,
                            "ctc": ctc
                        }
                    },
                    org_name=org_name
                )
                imported += 1
            except HTTPException as e:
                errors.append({
                    "row": row_num, "employee_id": emp_id, "email": email,
                    "error": e.detail
                })
            except Exception as e:
                errors.append({
                    "row": row_num, "employee_id": emp_id, "email": email,
                    "error": f"Unexpected error: {str(e)}"
                })

        logger.info(f"CSV import: {imported} imported, {len(errors)} failed for org {org_id}")
        return {
            "imported": imported,
            "failed": len(errors),
            "errors": errors
        }

    # ------------------------------------------------------------------
    # 3. List employees
    # ------------------------------------------------------------------

    async def get_employees(
        self,
        current_user: dict,
        page: int = 1,
        limit: int = 10,
        status_filter: str = None,
        department: str = None,
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
        if department:
            query["department"] = {"$regex": department, "$options": "i"}
        if search:
            query["$or"] = [
                {"first_name":  {"$regex": search, "$options": "i"}},
                {"last_name":   {"$regex": search, "$options": "i"}},
                {"official_email": {"$regex": search, "$options": "i"}},
                {"employee_id": {"$regex": search, "$options": "i"}},
                {"designation": {"$regex": search, "$options": "i"}},
            ]

        total = await self.db.employees.count_documents(query)
        cursor = (
            self.db.employees.find(
                query,
                {
                    "id": 1, "employee_id": 1, "first_name": 1, "last_name": 1,
                    "official_email": 1, "phone": 1, "department": 1,
                    "designation": 1, "status": 1, "onboarding_progress": 1,
                    "joining_date": 1, "is_fresher": 1, "gender": 1, "created_at": 1,
                    "onboarding_sections": 1
                }
            )
            .skip(skip).limit(limit).sort("created_at", -1)
        )
        employees = await cursor.to_list(length=limit)
        for emp in employees:
            _serialize(emp)

        return {
            "employees": employees,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    # ------------------------------------------------------------------
    # 4. Get single employee (full profile)
    # ------------------------------------------------------------------

    async def get_employee_by_id(
        self, employee_id: str, current_user: dict
    ) -> dict:
        role = current_user.get("role")

        try:
            obj_id = ObjectId(employee_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid employee ID format")

        if role == "employee":
            # Employee can only see their own record
            emp = await self.db.employees.find_one({
                "_id": obj_id,
                "user_id": str(current_user["_id"]),
                "is_deleted": False
            })
        elif role == "superadmin":
            emp = await self.db.employees.find_one({"_id": obj_id, "is_deleted": False})
        else:
            org_id = self._org_id_from_user(current_user)
            emp = await self.db.employees.find_one({
                "_id": obj_id,
                "organization_id": org_id,
                "is_deleted": False
            })

        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        return _serialize(emp)

    # ------------------------------------------------------------------
    # 5. Update employee (HR fields)
    # ------------------------------------------------------------------

    async def update_employee(
        self, employee_id: str, data: EmployeeUpdateRequest, current_user: dict
    ) -> dict:
        role = current_user.get("role")

        try:
            obj_id = ObjectId(employee_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid employee ID format")

        query: dict = {"_id": obj_id, "is_deleted": False}
        if role != "superadmin":
            query["organization_id"] = self._org_id_from_user(current_user)

        emp = await self.db.employees.find_one(query)
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        # Serialize nested salary_structure
        if "salary_structure" in update_data and update_data["salary_structure"]:
            update_data["salary_structure"] = update_data["salary_structure"]

        update_data["updated_at"] = datetime.utcnow()
        await self.db.employees.update_one({"_id": obj_id}, {"$set": update_data})

        logger.info(f"Employee {employee_id} updated by {current_user.get('email')}")
        updated = await self.db.employees.find_one({"_id": obj_id})
        return _serialize(updated)

    # ------------------------------------------------------------------
    # 6. Submit onboarding section (employee self or HR on behalf)
    # ------------------------------------------------------------------

    async def submit_onboarding_section(
        self,
        section: str,
        section_data: dict,
        current_user: dict,
        target_employee_id: str = None   # HR passes this; employee omits it
    ) -> dict:
        if section not in ONBOARDING_SECTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid section. Must be one of: {ONBOARDING_SECTIONS}"
            )

        role = current_user.get("role")

        # Resolve which employee record to update
        if role == "employee":
            # Employee always works on their own record
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
            if not emp:
                raise HTTPException(status_code=404, detail="Employee record not found")
        else:
            # HR / org_admin / superadmin acting on behalf of a specific employee
            if not target_employee_id:
                raise HTTPException(
                    status_code=400,
                    detail="employee_id is required when HR fills onboarding on behalf of employee"
                )
            try:
                obj_id = ObjectId(target_employee_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid employee ID format")

            query: dict = {"_id": obj_id, "is_deleted": False}
            if role != "superadmin":
                query["organization_id"] = self._org_id_from_user(current_user)

            emp = await self.db.employees.find_one(query)
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")

        if emp.get("status") == "inactive":
            raise HTTPException(status_code=403, detail="Inactive employee cannot be updated")

        # Special validation for policy_acceptance
        if section == "policy_acceptance":
            if not section_data.get("accepted"):
                raise HTTPException(
                    status_code=400,
                    detail="You must accept company policies to complete this section"
                )
            section_data["accepted_at"] = datetime.utcnow().isoformat()

        # Special validation for government_ids — UAN is now optional for all employees
        # (Previously required for experienced employees, now made optional as per requirement)

        # Special validation for experience — use is_fresher stored at creation
        if section == "experience":
            is_fresher = emp.get("is_fresher")
            entries = section_data.get("entries") or []
            if not is_fresher and len(entries) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="At least one experience entry is required for experienced employees"
                )

        # Get current onboarding sections
        sections = emp.get("onboarding_sections", default_onboarding_sections())

        # Update section
        sec_obj = sections.get(section, SectionStatus().model_dump())
        sec_obj["status"] = "completed"
        sec_obj["verified"] = False  # Reset if resubmitting after needs_revision
        sections[section] = sec_obj

        # Calculate new progress
        progress = _calc_progress(sections)

        # Auto-advance status when all sections done
        all_completed = all(s.get("status") in ("completed", "not_applicable") for s in sections.values())
        new_status = emp.get("status")
        if all_completed and new_status == "pending_onboarding":
            new_status = "onboarding_in_progress"

        filled_by = "hr" if role != "employee" else "employee"

        update_fields: dict = {
            f"onboarding_sections.{section}": sec_obj,
            section: section_data,
            "onboarding_progress": progress,
            "status": new_status,
            "updated_at": datetime.utcnow()
        }

        await self.db.employees.update_one(
            {"_id": emp["_id"]},
            {"$set": update_fields}
        )

        logger.info(
            f"Section '{section}' submitted for employee {emp['employee_id']} "
            f"by {filled_by} ({current_user.get('email')}), progress={progress}%"
        )
        return {
            "section": section,
            "status": "completed",
            "overall_progress": progress,
            "filled_by": filled_by
        }

    # ------------------------------------------------------------------
    # 7. Get my onboarding progress (employee)
    # ------------------------------------------------------------------

    async def get_my_onboarding(self, current_user: dict, target_employee_id: str = None) -> dict:
        role = current_user.get("role")

        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one(
                {"user_id": user_id, "is_deleted": False}
            )
        else:
            try:
                obj_id = ObjectId(target_employee_id)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid employee ID format")
            query: dict = {"_id": obj_id, "is_deleted": False}
            if role != "superadmin":
                query["organization_id"] = self._org_id_from_user(current_user)
            emp = await self.db.employees.find_one(query)

        if not emp:
            raise HTTPException(status_code=404, detail="Employee record not found")

        sections = emp.get("onboarding_sections", default_onboarding_sections())
        # Remove documents section if present
        sections.pop("documents", None)
        # Mark experience as not_applicable for freshers
        if emp.get("is_fresher") and "experience" in sections:
            if sections["experience"].get("status") == "pending":
                sections["experience"]["status"] = "not_applicable"

        # Recalculate progress based on current sections
        progress = _calc_progress(sections)

        return {
            "status": emp.get("status"),
            "progress": progress,
            "is_fresher": emp.get("is_fresher"),
            "sections": sections,
            "hr_notes": emp.get("hr_notes"),
            # HR-filled info at creation
            "employee_id": emp.get("employee_id"),
            "first_name": emp.get("first_name"),
            "last_name": emp.get("last_name"),
            "official_email": emp.get("official_email"),
            "phone": emp.get("phone"),
            "gender": emp.get("gender"),
            "department": emp.get("department"),
            "designation": emp.get("designation"),
            "reporting_manager": emp.get("reporting_manager"),
            "joining_date": emp.get("joining_date"),
            "employment_type": emp.get("employment_type"),
            "shift": emp.get("shift"),
            "work_location": emp.get("work_location"),
            "salary_structure": emp.get("salary_structure"),
            # Employee-filled onboarding data
            "personal_details": emp.get("personal_details"),
            "address": emp.get("address"),
            "emergency_contact": emp.get("emergency_contact"),
            "bank_details": emp.get("bank_details"),
            "government_ids": emp.get("government_ids"),
            "education": emp.get("education"),
            "experience": emp.get("experience"),
            "policy_acceptance": emp.get("policy_acceptance"),
        }

    # ------------------------------------------------------------------
    # 8. Verify / Approve employee (HR)
    # ------------------------------------------------------------------

    async def verify_employee(
        self,
        employee_id: str,
        data: VerifyEmployeeRequest,
        current_user: dict
    ) -> dict:
        role = current_user.get("role")

        try:
            obj_id = ObjectId(employee_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid employee ID format")

        query: dict = {"_id": obj_id, "is_deleted": False}
        if role != "superadmin":
            query["organization_id"] = self._org_id_from_user(current_user)

        emp = await self.db.employees.find_one(query)
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        sections = emp.get("onboarding_sections", default_onboarding_sections())
        # Remove deprecated documents section
        sections.pop("documents", None)
        # Mark experience as not_applicable for freshers
        if emp.get("is_fresher") and "experience" in sections:
            if sections["experience"].get("status") == "pending":
                sections["experience"]["status"] = "not_applicable"

        hr_id = str(current_user["_id"])
        now = datetime.utcnow()

        # --- approve ---
        if data.action == "approve":
            # All sections must be completed or not_applicable
            incomplete = [
                s for s, v in sections.items()
                if v.get("status") not in ("completed", "not_applicable")
            ]
            if incomplete:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot approve — incomplete sections: {incomplete}"
                )
            # Critical sections must be verified
            unverified_critical = [
                s for s in CRITICAL_SECTIONS
                if not sections.get(s, {}).get("verified", False)
            ]
            if unverified_critical:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot approve — unverified critical sections: {unverified_critical}"
                )

            await self.db.employees.update_one(
                {"_id": obj_id},
                {"$set": {
                    "status": "active",
                    "activated_at": now,
                    "updated_at": now
                }}
            )
            logger.info(f"Employee {employee_id} approved and activated by {current_user.get('email')}")
            return {"status": "active", "message": "Employee approved and activated"}

        # --- verify_section ---
        elif data.action == "verify_section":
            if not data.section:
                raise HTTPException(status_code=400, detail="section is required for verify_section action")
            if data.section not in ONBOARDING_SECTIONS:
                raise HTTPException(status_code=400, detail=f"Invalid section: {data.section}")
            if sections.get(data.section, {}).get("status") != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Section '{data.section}' is not completed yet"
                )

            sections[data.section]["verified"] = True
            sections[data.section]["verified_at"] = now.isoformat()
            sections[data.section]["verified_by"] = hr_id

            await self.db.employees.update_one(
                {"_id": obj_id},
                {"$set": {
                    f"onboarding_sections.{data.section}": sections[data.section],
                    "updated_at": now
                }}
            )
            logger.info(f"Section '{data.section}' verified for employee {employee_id}")
            return {
                "status": "verified",
                "section": data.section,
                "message": f"Section '{data.section}' verified successfully"
            }

        # --- request_changes ---
        elif data.action == "request_changes":
            if not data.sections:
                raise HTTPException(status_code=400, detail="sections list is required for request_changes action")

            for sec in data.sections:
                if sec not in ONBOARDING_SECTIONS:
                    raise HTTPException(status_code=400, detail=f"Invalid section: {sec}")
                sections[sec]["status"] = "needs_revision"
                sections[sec]["verified"] = False
                sections[sec]["hr_notes"] = data.notes

            # Recalculate progress
            progress = _calc_progress(sections)

            update_fields: dict = {
                "onboarding_sections": sections,
                "onboarding_progress": progress,
                "hr_notes": data.notes,
                "status": "onboarding_in_progress",
                "updated_at": now
            }
            await self.db.employees.update_one({"_id": obj_id}, {"$set": update_fields})

            # Notify employee
            await send_onboarding_revision_email(
                email=emp["official_email"],
                first_name=emp["first_name"],
                org_name="HR Team",
                sections=data.sections,
                notes=data.notes
            )

            logger.info(f"Changes requested for employee {employee_id}: {data.sections}")
            return {
                "status": "changes_requested",
                "sections": data.sections,
                "message": "Employee notified to update the specified sections"
            }

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid action. Must be: approve | verify_section | request_changes"
            )

    # ------------------------------------------------------------------
    # 9. Soft delete
    # ------------------------------------------------------------------

    async def delete_employee(self, employee_id: str, current_user: dict) -> dict:
        role = current_user.get("role")

        try:
            obj_id = ObjectId(employee_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid employee ID format")

        query: dict = {"_id": obj_id, "is_deleted": False}
        if role != "superadmin":
            query["organization_id"] = self._org_id_from_user(current_user)

        emp = await self.db.employees.find_one(query)
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        now = datetime.utcnow()
        await self.db.employees.update_one(
            {"_id": obj_id},
            {"$set": {"is_deleted": True, "deleted_at": now, "status": "inactive", "updated_at": now}}
        )

        # Deactivate user account
        if emp.get("user_id"):
            await self.db.users.update_one(
                {"_id": ObjectId(emp["user_id"])},
                {"$set": {"is_active": False, "updated_at": now}}
            )

        logger.info(f"Employee {employee_id} soft deleted by {current_user.get('email')}")
        return {"message": "Employee deactivated successfully", "employee_id": employee_id}
