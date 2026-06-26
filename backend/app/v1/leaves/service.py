import uuid
from datetime import datetime, date
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.leave import (
    LeaveConfigurationModel, LeaveTypeConfig,
    LeaveRequestModel, DEFAULT_LEAVE_TYPES
)
from app.v1.leaves.schema import (
    LeaveTypeCreateRequest, LeaveTypeUpdateRequest,
    LeaveApplyRequest, LeaveRejectRequest
)
from app.utils.helpers import paginate_query
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


# ---------------------------------------------------------------------------
# LeaveService
# ---------------------------------------------------------------------------

class LeaveService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    def _org_id_from_user(self, current_user: dict, explicit_org_id: str = None) -> str:
        role = current_user.get("role")
        if role == "superadmin":
            if not explicit_org_id:
                raise HTTPException(
                    status_code=400,
                    detail="superadmin must supply organization_id"
                )
            return explicit_org_id
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(status_code=400, detail="No organization linked")
        return org_id

    # ------------------------------------------------------------------
    # LEAVE CONFIGURATION CRUD
    # ------------------------------------------------------------------

    async def get_leave_configuration(
        self, current_user: dict, organization_id: str = None, year: int = None
    ) -> dict:
        """Get leave configuration for the organization"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year

        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id, "year": year
        })

        if not config:
            # Auto-create with default leave types
            config = await self._create_default_config(org_id, year, current_user)

        return _serialize(config)

    async def _create_default_config(
        self, org_id: str, year: int, current_user: dict
    ) -> dict:
        """Create default leave configuration with standard leave types"""
        leave_types = []
        for lt in DEFAULT_LEAVE_TYPES:
            lt_entry = {**lt}
            lt_entry["id"] = str(uuid.uuid4())
            lt_entry["created_at"] = datetime.utcnow()
            lt_entry["updated_at"] = datetime.utcnow()
            leave_types.append(lt_entry)

        config_model = LeaveConfigurationModel(
            organization_id=org_id,
            year=year,
            leave_types=leave_types,
            created_by=str(current_user["_id"]),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        result = await self.db.leave_configurations.insert_one(config_model.model_dump())
        config_dict = config_model.model_dump()
        config_dict["_id"] = result.inserted_id

        logger.info(f"Default leave config created for org {org_id}, year {year}")
        return config_dict

    async def add_leave_type(
        self, data: LeaveTypeCreateRequest, current_user: dict,
        organization_id: str = None, year: int = None
    ) -> dict:
        """Add a new leave type to the configuration"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year

        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id, "year": year
        })

        if not config:
            config = await self._create_default_config(org_id, year, current_user)

        # Check duplicate code
        existing_codes = [lt["code"].upper() for lt in config.get("leave_types", [])]
        if data.code.upper() in existing_codes:
            raise HTTPException(
                status_code=400,
                detail=f"Leave type with code '{data.code}' already exists"
            )

        # Check duplicate name
        existing_names = [lt["name"].lower() for lt in config.get("leave_types", [])]
        if data.name.lower() in existing_names:
            raise HTTPException(
                status_code=400,
                detail=f"Leave type with name '{data.name}' already exists"
            )

        new_leave_type = {
            "id": str(uuid.uuid4()),
            "name": data.name,
            "code": data.code.upper(),
            "days_per_year": data.days_per_year,
            "is_paid": data.is_paid,
            "carry_forward": data.carry_forward,
            "max_carry_forward_days": data.max_carry_forward_days,
            "applicable_after_days": data.applicable_after_days,
            "description": data.description,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        await self.db.leave_configurations.update_one(
            {"_id": config["_id"]},
            {
                "$push": {"leave_types": new_leave_type},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        logger.info(f"Leave type '{data.name}' ({data.code}) added for org {org_id}")
        return new_leave_type

    async def update_leave_type(
        self, leave_type_id: str, data: LeaveTypeUpdateRequest,
        current_user: dict, organization_id: str = None, year: int = None
    ) -> dict:
        """Update an existing leave type"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year

        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id, "year": year
        })

        if not config:
            raise HTTPException(status_code=404, detail="Leave configuration not found")

        # Find the leave type
        leave_types = config.get("leave_types", [])
        target_idx = None
        for idx, lt in enumerate(leave_types):
            if lt.get("id") == leave_type_id:
                target_idx = idx
                break

        if target_idx is None:
            raise HTTPException(status_code=404, detail="Leave type not found")

        # Check code duplication if code is being changed
        update_data = data.model_dump(exclude_unset=True)
        if "code" in update_data:
            for idx, lt in enumerate(leave_types):
                if idx != target_idx and lt["code"].upper() == update_data["code"].upper():
                    raise HTTPException(
                        status_code=400,
                        detail=f"Leave type with code '{update_data['code']}' already exists"
                    )
            update_data["code"] = update_data["code"].upper()

        # Check name duplication if name is being changed
        if "name" in update_data:
            for idx, lt in enumerate(leave_types):
                if idx != target_idx and lt["name"].lower() == update_data["name"].lower():
                    raise HTTPException(
                        status_code=400,
                        detail=f"Leave type with name '{update_data['name']}' already exists"
                    )

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        # Apply updates
        update_data["updated_at"] = datetime.utcnow()
        for key, value in update_data.items():
            leave_types[target_idx][key] = value

        await self.db.leave_configurations.update_one(
            {"_id": config["_id"]},
            {"$set": {"leave_types": leave_types, "updated_at": datetime.utcnow()}}
        )

        logger.info(f"Leave type '{leave_type_id}' updated for org {org_id}")
        return leave_types[target_idx]

    async def delete_leave_type(
        self, leave_type_id: str, current_user: dict,
        organization_id: str = None, year: int = None
    ) -> dict:
        """Delete a leave type from the configuration"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year

        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id, "year": year
        })

        if not config:
            raise HTTPException(status_code=404, detail="Leave configuration not found")

        leave_types = config.get("leave_types", [])
        target = None
        for lt in leave_types:
            if lt.get("id") == leave_type_id:
                target = lt
                break

        if not target:
            raise HTTPException(status_code=404, detail="Leave type not found")

        # Check if any approved/pending leaves exist for this type
        leave_count = await self.db.leave_requests.count_documents({
            "organization_id": org_id,
            "leave_type_code": target["code"],
            "status": {"$in": ["pending", "approved"]}
        })

        if leave_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete: {leave_count} active leave request(s) exist for this type. Deactivate instead."
            )

        # Remove from list
        leave_types = [lt for lt in leave_types if lt.get("id") != leave_type_id]

        await self.db.leave_configurations.update_one(
            {"_id": config["_id"]},
            {"$set": {"leave_types": leave_types, "updated_at": datetime.utcnow()}}
        )

        logger.info(f"Leave type '{target['name']}' deleted for org {org_id}")
        return {"message": f"Leave type '{target['name']}' deleted successfully"}

    # ------------------------------------------------------------------
    # LEAVE REQUEST OPERATIONS
    # ------------------------------------------------------------------

    async def apply_leave(
        self, data: LeaveApplyRequest, current_user: dict,
        organization_id: str = None
    ) -> dict:
        """Employee applies for leave"""
        role = current_user.get("role")
        org_id = self._org_id_from_user(current_user, organization_id)

        # Resolve employee
        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({
                "user_id": user_id, "is_deleted": False
            })
            if not emp:
                raise HTTPException(status_code=404, detail="Employee record not found")
        else:
            # HR applying on behalf
            if not data.employee_id:
                raise HTTPException(
                    status_code=400,
                    detail="employee_id is required when HR applies leave on behalf"
                )
            try:
                emp = await self.db.employees.find_one({
                    "_id": ObjectId(data.employee_id),
                    "organization_id": org_id,
                    "is_deleted": False
                })
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid employee_id")
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")

        employee_id = str(emp["_id"])
        employee_name = f"{emp['first_name']} {emp['last_name']}"
        department = emp.get("department", "")

        # Validate leave type exists and is active
        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id,
            "year": datetime.utcnow().year
        })
        if not config:
            raise HTTPException(
                status_code=400,
                detail="Leave configuration not set up for this year"
            )

        leave_type = None
        for lt in config.get("leave_types", []):
            if lt["code"] == data.leave_type_code.upper() and lt.get("is_active", True):
                leave_type = lt
                break

        if not leave_type:
            raise HTTPException(
                status_code=400,
                detail=f"Leave type '{data.leave_type_code}' not found or inactive"
            )

        # Gender-based leave restrictions
        emp_gender = emp.get("gender", "").lower()
        leave_code = data.leave_type_code.upper()
        if leave_code == "ML" and emp_gender != "female":
            raise HTTPException(
                status_code=400,
                detail="Maternity Leave is only available for female employees"
            )
        if leave_code == "PL" and emp_gender != "male":
            raise HTTPException(
                status_code=400,
                detail="Paternity Leave is only available for male employees"
            )

        # Validate dates
        try:
            start = datetime.strptime(data.start_date, "%Y-%m-%d").date()
            end = datetime.strptime(data.end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        if end < start:
            raise HTTPException(status_code=400, detail="end_date cannot be before start_date")

        # Calculate days
        if data.is_half_day:
            if start != end:
                raise HTTPException(
                    status_code=400,
                    detail="Half-day leave must be for a single day (start_date == end_date)"
                )
            if not data.half_day_type or data.half_day_type not in ("first_half", "second_half"):
                raise HTTPException(
                    status_code=400,
                    detail="half_day_type must be 'first_half' or 'second_half'"
                )
            days = 0.5
        else:
            days = (end - start).days + 1

        # Check if any date falls on a holiday
        from datetime import timedelta as td
        current_date = start
        holiday_dates = []
        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")
            holiday = await self.db.holidays.find_one({
                "organization_id": org_id,
                "date": date_str,
                "is_deleted": False,
                "type": "mandatory"
            })
            if holiday:
                holiday_dates.append(f"{date_str} ({holiday['name']})")
            current_date += td(days=1)

        if holiday_dates:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot apply leave on holiday(s): {', '.join(holiday_dates)}"
            )

        # Check for overlapping leaves
        overlap = await self.db.leave_requests.find_one({
            "employee_id": employee_id,
            "status": {"$in": ["pending", "approved"]},
            "$or": [
                {"start_date": {"$lte": data.end_date}, "end_date": {"$gte": data.start_date}}
            ]
        })
        if overlap:
            raise HTTPException(
                status_code=400,
                detail=f"Overlapping leave exists from {overlap['start_date']} to {overlap['end_date']} (status: {overlap['status']})"
            )

        # Check balance (skip for unlimited types like Comp Off)
        if leave_type["days_per_year"] != -1:
            used = await self._get_used_leaves(
                employee_id, data.leave_type_code.upper(), datetime.utcnow().year
            )
            pending = await self._get_pending_leaves(
                employee_id, data.leave_type_code.upper(), datetime.utcnow().year
            )
            available = leave_type["days_per_year"] - used
            if days > available:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient balance for {leave_type['name']}. Available: {available}, Requested: {days}, Already pending: {pending}"
                )

        # Create leave request
        leave_model = LeaveRequestModel(
            organization_id=org_id,
            employee_id=employee_id,
            employee_name=employee_name,
            department=department,
            leave_type_code=data.leave_type_code.upper(),
            leave_type_name=leave_type["name"],
            start_date=data.start_date,
            end_date=data.end_date,
            days=days,
            is_half_day=data.is_half_day,
            half_day_type=data.half_day_type if data.is_half_day else None,
            reason=data.reason,
            status="pending",
            applied_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        result = await self.db.leave_requests.insert_one(leave_model.model_dump())
        leave_dict = leave_model.model_dump()
        leave_dict["id"] = str(result.inserted_id)

        logger.info(
            f"Leave applied: {employee_name} ({data.leave_type_code}) "
            f"{data.start_date} to {data.end_date}, {days} days"
        )
        return leave_dict

    async def _get_used_leaves(
        self, employee_id: str, leave_type_code: str, year: int
    ) -> float:
        """Get total approved leave days for a type in a year"""
        pipeline = [
            {
                "$match": {
                    "employee_id": employee_id,
                    "leave_type_code": leave_type_code,
                    "status": "approved",
                    "start_date": {"$regex": f"^{year}"}
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$days"}}}
        ]
        result = await self.db.leave_requests.aggregate(pipeline).to_list(1)
        return result[0]["total"] if result else 0.0

    async def _get_pending_leaves(
        self, employee_id: str, leave_type_code: str, year: int
    ) -> float:
        """Get total pending leave days for a type in a year"""
        pipeline = [
            {
                "$match": {
                    "employee_id": employee_id,
                    "leave_type_code": leave_type_code,
                    "status": "pending",
                    "start_date": {"$regex": f"^{year}"}
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$days"}}}
        ]
        result = await self.db.leave_requests.aggregate(pipeline).to_list(1)
        return result[0]["total"] if result else 0.0

    # ------------------------------------------------------------------
    # APPROVE / REJECT / CANCEL
    # ------------------------------------------------------------------

    async def approve_leave(
        self, leave_id: str, current_user: dict
    ) -> dict:
        """HR approves a pending leave request"""
        try:
            obj_id = ObjectId(leave_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid leave ID")

        org_id = self._org_id_from_user(current_user)
        leave = await self.db.leave_requests.find_one({
            "_id": obj_id, "organization_id": org_id
        })

        if not leave:
            raise HTTPException(status_code=404, detail="Leave request not found")

        if leave["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve: leave is already '{leave['status']}'"
            )

        await self.db.leave_requests.update_one(
            {"_id": obj_id},
            {"$set": {
                "status": "approved",
                "approved_by": str(current_user["_id"]),
                "approved_by_name": current_user.get("full_name", current_user.get("email")),
                "approved_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )

        logger.info(f"Leave {leave_id} approved by {current_user.get('email')}")
        updated = await self.db.leave_requests.find_one({"_id": obj_id})
        return _serialize(updated)

    async def reject_leave(
        self, leave_id: str, data: LeaveRejectRequest, current_user: dict
    ) -> dict:
        """HR rejects a pending leave request"""
        try:
            obj_id = ObjectId(leave_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid leave ID")

        org_id = self._org_id_from_user(current_user)
        leave = await self.db.leave_requests.find_one({
            "_id": obj_id, "organization_id": org_id
        })

        if not leave:
            raise HTTPException(status_code=404, detail="Leave request not found")

        if leave["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject: leave is already '{leave['status']}'"
            )

        await self.db.leave_requests.update_one(
            {"_id": obj_id},
            {"$set": {
                "status": "rejected",
                "rejection_reason": data.reason,
                "updated_at": datetime.utcnow()
            }}
        )

        logger.info(f"Leave {leave_id} rejected by {current_user.get('email')}")
        updated = await self.db.leave_requests.find_one({"_id": obj_id})
        return _serialize(updated)

    async def cancel_leave(
        self, leave_id: str, current_user: dict
    ) -> dict:
        """Employee cancels their own pending leave"""
        try:
            obj_id = ObjectId(leave_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid leave ID")

        role = current_user.get("role")

        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({
                "user_id": user_id, "is_deleted": False
            })
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
            employee_id = str(emp["_id"])

            leave = await self.db.leave_requests.find_one({
                "_id": obj_id, "employee_id": employee_id
            })
        else:
            org_id = self._org_id_from_user(current_user)
            leave = await self.db.leave_requests.find_one({
                "_id": obj_id, "organization_id": org_id
            })

        if not leave:
            raise HTTPException(status_code=404, detail="Leave request not found")

        if leave["status"] not in ("pending", "approved"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel: leave is already '{leave['status']}'"
            )

        await self.db.leave_requests.update_one(
            {"_id": obj_id},
            {"$set": {
                "status": "cancelled",
                "cancelled_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )

        logger.info(f"Leave {leave_id} cancelled by {current_user.get('email')}")
        updated = await self.db.leave_requests.find_one({"_id": obj_id})
        return _serialize(updated)

    # ------------------------------------------------------------------
    # LIST / GET / BALANCE
    # ------------------------------------------------------------------

    async def get_leaves(
        self, current_user: dict, page: int = 1, limit: int = 10,
        status_filter: str = None, leave_type: str = None,
        employee_id: str = None, department: str = None,
        organization_id: str = None, from_date: str = None,
        to_date: str = None, search: str = None
    ) -> dict:
        """List leave requests (HR sees all in org, employee sees own)"""
        role = current_user.get("role")
        org_id = self._org_id_from_user(current_user, organization_id)
        skip, limit = paginate_query(page, limit)

        query = {"organization_id": org_id}

        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({
                "user_id": user_id, "is_deleted": False
            })
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
            query["employee_id"] = str(emp["_id"])
        elif employee_id:
            query["employee_id"] = employee_id

        if status_filter:
            query["status"] = status_filter
        if leave_type:
            query["leave_type_code"] = leave_type.upper()
        if department:
            query["department"] = {"$regex": department, "$options": "i"}
        if from_date:
            query["start_date"] = query.get("start_date", {})
            query["start_date"]["$gte"] = from_date
        if to_date:
            query["end_date"] = query.get("end_date", {})
            query["end_date"]["$lte"] = to_date
        if search:
            query["$or"] = [
                {"employee_name": {"$regex": search, "$options": "i"}},
                {"leave_type_name": {"$regex": search, "$options": "i"}},
            ]

        total = await self.db.leave_requests.count_documents(query)
        cursor = (
            self.db.leave_requests.find(query)
            .skip(skip).limit(limit).sort("created_at", -1)
        )
        leaves = await cursor.to_list(length=limit)
        for leave in leaves:
            _serialize(leave)

        return {
            "leaves": leaves,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    async def get_leave_by_id(
        self, leave_id: str, current_user: dict
    ) -> dict:
        """Get single leave request detail"""
        try:
            obj_id = ObjectId(leave_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid leave ID")

        role = current_user.get("role")

        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({
                "user_id": user_id, "is_deleted": False
            })
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
            leave = await self.db.leave_requests.find_one({
                "_id": obj_id, "employee_id": str(emp["_id"])
            })
        else:
            org_id = self._org_id_from_user(current_user)
            leave = await self.db.leave_requests.find_one({
                "_id": obj_id, "organization_id": org_id
            })

        if not leave:
            raise HTTPException(status_code=404, detail="Leave request not found")

        return _serialize(leave)

    async def get_leave_balance(
        self, current_user: dict, employee_id: str = None,
        organization_id: str = None
    ) -> dict:
        """Get leave balance for an employee"""
        role = current_user.get("role")
        org_id = self._org_id_from_user(current_user, organization_id)
        year = datetime.utcnow().year

        # Resolve employee
        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({
                "user_id": user_id, "is_deleted": False
            })
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
        else:
            if not employee_id:
                raise HTTPException(
                    status_code=400,
                    detail="employee_id is required for HR to check balance"
                )
            try:
                emp = await self.db.employees.find_one({
                    "_id": ObjectId(employee_id),
                    "organization_id": org_id,
                    "is_deleted": False
                })
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid employee_id")
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")

        emp_id = str(emp["_id"])
        emp_name = f"{emp['first_name']} {emp['last_name']}"

        # Get leave configuration
        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id, "year": year
        })
        if not config:
            raise HTTPException(
                status_code=400,
                detail="Leave configuration not set up for this year"
            )

        balances = []
        for lt in config.get("leave_types", []):
            if not lt.get("is_active", True):
                continue

            total = lt["days_per_year"]
            used = await self._get_used_leaves(emp_id, lt["code"], year)
            pending = await self._get_pending_leaves(emp_id, lt["code"], year)
            adjustments = await self._get_adjustments_net(emp_id, lt["code"], year)

            effective_total = total + adjustments if total != -1 else -1
            balance = effective_total - used if effective_total != -1 else -1

            balances.append({
                "leave_type_code": lt["code"],
                "leave_type_name": lt["name"],
                "total": effective_total,
                "used": used,
                "balance": balance,
                "pending": pending
            })

        return {
            "employee_id": emp_id,
            "employee_name": emp_name,
            "year": year,
            "balances": balances
        }

    # ------------------------------------------------------------------
    # BALANCE ADJUSTMENTS (Credit / Deduct / Reset)
    # ------------------------------------------------------------------

    async def adjust_balance(
        self, data, current_user: dict, organization_id: str = None
    ) -> dict:
        """HR manually adjusts employee leave balance"""
        from app.models.leave import LeaveBalanceAdjustmentModel

        org_id = self._org_id_from_user(current_user, organization_id)
        year = datetime.utcnow().year

        # Validate action
        if data.action not in ("credit", "deduct", "reset"):
            raise HTTPException(
                status_code=400,
                detail="action must be 'credit', 'deduct', or 'reset'"
            )

        # Get employee
        try:
            emp = await self.db.employees.find_one({
                "_id": ObjectId(data.employee_id),
                "organization_id": org_id,
                "is_deleted": False
            })
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid employee_id")

        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        employee_name = f"{emp['first_name']} {emp['last_name']}"

        # Validate leave type exists
        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id, "year": year
        })
        if not config:
            raise HTTPException(status_code=400, detail="Leave configuration not found")

        leave_type = None
        for lt in config.get("leave_types", []):
            if lt["code"] == data.leave_type_code.upper() and lt.get("is_active", True):
                leave_type = lt
                break

        if not leave_type:
            raise HTTPException(
                status_code=400,
                detail=f"Leave type '{data.leave_type_code}' not found or inactive"
            )

        # Calculate current balance before adjustment
        used = await self._get_used_leaves(data.employee_id, data.leave_type_code.upper(), year)
        adjustments_sum = await self._get_adjustments_net(data.employee_id, data.leave_type_code.upper(), year)
        total_entitlement = leave_type["days_per_year"] + adjustments_sum if leave_type["days_per_year"] != -1 else -1
        current_balance = total_entitlement - used if total_entitlement != -1 else -1

        # Determine adjustment days
        if data.action == "reset":
            # Reset = remove all previous adjustments by inserting a counter-adjustment
            # Delete all existing adjustments for this employee+leave_type+year
            await self.db.leave_balance_adjustments.delete_many({
                "organization_id": org_id,
                "employee_id": data.employee_id,
                "leave_type_code": data.leave_type_code.upper(),
                "year": year
            })
            effective_action = "reset"
            adjustment_days = 0
        elif data.action == "credit":
            adjustment_days = data.days
            effective_action = "credit"
        elif data.action == "deduct":
            # Validate not going negative
            if total_entitlement != -1:
                new_balance = current_balance - data.days
                if new_balance < 0:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot deduct {data.days} days. Current balance is {current_balance}"
                    )
            adjustment_days = -data.days
            effective_action = "deduct"

        # Save adjustment record (for audit trail)
        adjustment_model = LeaveBalanceAdjustmentModel(
            organization_id=org_id,
            employee_id=data.employee_id,
            employee_name=employee_name,
            leave_type_code=data.leave_type_code.upper(),
            leave_type_name=leave_type["name"],
            action=effective_action,
            days=data.days if data.action != "reset" else abs(adjustments_sum),
            reason=data.reason,
            adjusted_by=str(current_user["_id"]),
            adjusted_by_name=current_user.get("full_name", current_user.get("email", "")),
            year=year,
            created_at=datetime.utcnow()
        )

        # For reset, we already deleted all adjustments above, so don't insert a new credit/deduct
        # Only insert for credit/deduct actions
        if data.action != "reset":
            result = await self.db.leave_balance_adjustments.insert_one(adjustment_model.model_dump())
            adj_id = str(result.inserted_id)
        else:
            adj_id = "reset-action"

        # Calculate new balance after adjustment
        new_adjustments_sum = await self._get_adjustments_net(data.employee_id, data.leave_type_code.upper(), year)
        new_total = leave_type["days_per_year"] + new_adjustments_sum if leave_type["days_per_year"] != -1 else -1
        new_balance = new_total - used if new_total != -1 else -1

        logger.info(
            f"Balance adjusted: {employee_name} | {leave_type['name']} | "
            f"{data.action} {data.days} days | new_balance={new_balance} | "
            f"by {current_user.get('email')}"
        )

        return {
            "id": adj_id,
            "employee_id": data.employee_id,
            "employee_name": employee_name,
            "leave_type_code": data.leave_type_code.upper(),
            "leave_type_name": leave_type["name"],
            "action": effective_action,
            "days": data.days if data.action != "reset" else abs(adjustments_sum),
            "reason": data.reason,
            "adjusted_by_name": current_user.get("full_name", current_user.get("email", "")),
            "new_balance": new_balance,
            "year": year,
            "created_at": datetime.utcnow()
        }

    async def _get_adjustments_net(
        self, employee_id: str, leave_type_code: str, year: int
    ) -> float:
        """Get net adjustment (credits - deductions) for a leave type in a year"""
        pipeline = [
            {
                "$match": {
                    "employee_id": employee_id,
                    "leave_type_code": leave_type_code,
                    "year": year
                }
            },
            {
                "$group": {
                    "_id": None,
                    "credits": {
                        "$sum": {
                            "$cond": [{"$eq": ["$action", "credit"]}, "$days", 0]
                        }
                    },
                    "deductions": {
                        "$sum": {
                            "$cond": [{"$eq": ["$action", "deduct"]}, "$days", 0]
                        }
                    }
                }
            }
        ]
        result = await self.db.leave_balance_adjustments.aggregate(pipeline).to_list(1)
        if not result:
            return 0.0
        return result[0]["credits"] - result[0]["deductions"]

    async def get_balance_adjustments(
        self, current_user: dict, employee_id: str,
        leave_type_code: str = None, organization_id: str = None
    ) -> dict:
        """Get balance adjustment history for an employee"""
        org_id = self._org_id_from_user(current_user, organization_id)
        year = datetime.utcnow().year

        query = {
            "organization_id": org_id,
            "employee_id": employee_id,
            "year": year
        }
        if leave_type_code:
            query["leave_type_code"] = leave_type_code.upper()

        cursor = self.db.leave_balance_adjustments.find(query).sort("created_at", -1)
        adjustments = await cursor.to_list(length=100)
        for adj in adjustments:
            _serialize(adj)

        return {"adjustments": adjustments, "total": len(adjustments)}

    # ------------------------------------------------------------------
    # FORWARD LEAVE
    # ------------------------------------------------------------------

    async def forward_leave(
        self, leave_id: str, forward_to: str, notes: str, current_user: dict
    ) -> dict:
        """HR forwards a leave request to another approver"""
        try:
            obj_id = ObjectId(leave_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid leave ID")

        org_id = self._org_id_from_user(current_user)
        leave = await self.db.leave_requests.find_one({
            "_id": obj_id, "organization_id": org_id
        })

        if not leave:
            raise HTTPException(status_code=404, detail="Leave request not found")

        if leave["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot forward: leave is already '{leave['status']}'"
            )

        # Resolve forward_to user
        try:
            forward_user = await self.db.users.find_one({"_id": ObjectId(forward_to)})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid forward_to user ID")

        if not forward_user:
            raise HTTPException(status_code=404, detail="Forward-to user not found")

        forward_to_name = forward_user.get("full_name", forward_user.get("email", ""))

        # Add forward entry
        forward_entry = {
            "forwarded_by": str(current_user["_id"]),
            "forwarded_by_name": current_user.get("full_name", current_user.get("email", "")),
            "forwarded_to": forward_to,
            "forwarded_to_name": forward_to_name,
            "notes": notes,
            "forwarded_at": datetime.utcnow()
        }

        await self.db.leave_requests.update_one(
            {"_id": obj_id},
            {
                "$push": {"forwards": forward_entry},
                "$set": {
                    "forwarded_to": forward_to,
                    "forwarded_to_name": forward_to_name,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        logger.info(
            f"Leave {leave_id} forwarded to {forward_to_name} "
            f"by {current_user.get('email')}"
        )

        updated = await self.db.leave_requests.find_one({"_id": obj_id})
        return _serialize(updated)

    # ------------------------------------------------------------------
    # ADD COMMENT
    # ------------------------------------------------------------------

    async def add_comment(
        self, leave_id: str, comment: str, current_user: dict
    ) -> dict:
        """Add a comment to a leave request"""
        try:
            obj_id = ObjectId(leave_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid leave ID")

        role = current_user.get("role")
        org_id = self._org_id_from_user(current_user)

        # Employees can only comment on their own leaves
        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({
                "user_id": user_id, "is_deleted": False
            })
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
            leave = await self.db.leave_requests.find_one({
                "_id": obj_id, "employee_id": str(emp["_id"])
            })
        else:
            leave = await self.db.leave_requests.find_one({
                "_id": obj_id, "organization_id": org_id
            })

        if not leave:
            raise HTTPException(status_code=404, detail="Leave request not found")

        comment_entry = {
            "user_id": str(current_user["_id"]),
            "user_name": current_user.get("full_name", current_user.get("email", "")),
            "role": role,
            "comment": comment,
            "created_at": datetime.utcnow()
        }

        await self.db.leave_requests.update_one(
            {"_id": obj_id},
            {
                "$push": {"comments": comment_entry},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )

        logger.info(f"Comment added to leave {leave_id} by {current_user.get('email')}")

        updated = await self.db.leave_requests.find_one({"_id": obj_id})
        return _serialize(updated)

    # ------------------------------------------------------------------
    # APPROVAL WORKFLOW CONFIGURATION
    # ------------------------------------------------------------------

    async def get_workflow(
        self, current_user: dict, organization_id: str = None
    ) -> dict:
        """Get approval workflow for the organization"""
        from app.models.leave import LeaveApprovalWorkflowModel
        org_id = self._org_id_from_user(current_user, organization_id)

        workflow = await self.db.leave_approval_workflows.find_one({
            "organization_id": org_id, "is_active": True
        })

        if not workflow:
            # Create default: Employee → Reporting Manager → HR
            default = LeaveApprovalWorkflowModel(
                organization_id=org_id,
                name="Default Workflow",
                levels=[
                    {"level": 1, "approver_type": "reporting_manager", "approver_id": None, "approver_name": None, "can_skip": True},
                    {"level": 2, "approver_type": "hr_admin", "approver_id": None, "approver_name": None, "can_skip": False}
                ],
                auto_approval={"enabled": False, "max_days": 0, "leave_types": None},
                is_active=True,
                created_by=str(current_user["_id"]),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            result = await self.db.leave_approval_workflows.insert_one(default.model_dump())
            workflow = default.model_dump()
            workflow["_id"] = result.inserted_id
            logger.info(f"Default approval workflow created for org {org_id}")

        return _serialize(workflow)

    async def create_workflow(
        self, data, current_user: dict, organization_id: str = None
    ) -> dict:
        """Create or replace approval workflow"""
        from app.models.leave import LeaveApprovalWorkflowModel
        org_id = self._org_id_from_user(current_user, organization_id)

        # Validate approver types
        valid_types = ("reporting_manager", "hr_admin", "org_admin", "specific_user")
        for level in data.levels:
            if level.approver_type not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid approver_type '{level.approver_type}' at level {level.level}. Must be one of: {valid_types}"
                )
            if level.approver_type == "specific_user" and not level.approver_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"approver_id is required when approver_type is 'specific_user' (level {level.level})"
                )

        # Deactivate existing workflow
        await self.db.leave_approval_workflows.update_many(
            {"organization_id": org_id, "is_active": True},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )

        # Build levels
        levels = []
        for lvl in data.levels:
            level_dict = {
                "level": lvl.level,
                "approver_type": lvl.approver_type,
                "approver_id": lvl.approver_id,
                "approver_name": lvl.approver_name,
                "can_skip": lvl.can_skip
            }
            # Resolve approver name if specific_user
            if lvl.approver_type == "specific_user" and lvl.approver_id:
                try:
                    user = await self.db.users.find_one({"_id": ObjectId(lvl.approver_id)})
                    if user:
                        level_dict["approver_name"] = user.get("full_name", user.get("email", ""))
                except Exception:
                    pass
            levels.append(level_dict)

        # Build auto approval
        auto_approval = None
        if data.auto_approval:
            auto_approval = {
                "enabled": data.auto_approval.enabled,
                "max_days": data.auto_approval.max_days,
                "leave_types": data.auto_approval.leave_types
            }

        workflow_model = LeaveApprovalWorkflowModel(
            organization_id=org_id,
            name=data.name,
            levels=levels,
            auto_approval=auto_approval,
            is_active=True,
            created_by=str(current_user["_id"]),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        result = await self.db.leave_approval_workflows.insert_one(workflow_model.model_dump())
        workflow_dict = workflow_model.model_dump()
        workflow_dict["_id"] = result.inserted_id

        logger.info(f"Approval workflow '{data.name}' created for org {org_id} with {len(levels)} levels")
        return _serialize(workflow_dict)

    async def update_workflow(
        self, workflow_id: str, data, current_user: dict
    ) -> dict:
        """Update an existing approval workflow"""
        org_id = self._org_id_from_user(current_user)

        try:
            obj_id = ObjectId(workflow_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid workflow ID")

        workflow = await self.db.leave_approval_workflows.find_one({
            "_id": obj_id, "organization_id": org_id
        })

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        update_data = {}

        if data.name is not None:
            update_data["name"] = data.name

        if data.is_active is not None:
            update_data["is_active"] = data.is_active

        if data.levels is not None:
            valid_types = ("reporting_manager", "hr_admin", "org_admin", "specific_user")
            levels = []
            for lvl in data.levels:
                if lvl.approver_type not in valid_types:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid approver_type '{lvl.approver_type}'"
                    )
                level_dict = {
                    "level": lvl.level,
                    "approver_type": lvl.approver_type,
                    "approver_id": lvl.approver_id,
                    "approver_name": lvl.approver_name,
                    "can_skip": lvl.can_skip
                }
                if lvl.approver_type == "specific_user" and lvl.approver_id:
                    try:
                        user = await self.db.users.find_one({"_id": ObjectId(lvl.approver_id)})
                        if user:
                            level_dict["approver_name"] = user.get("full_name", user.get("email", ""))
                    except Exception:
                        pass
                levels.append(level_dict)
            update_data["levels"] = levels

        if data.auto_approval is not None:
            update_data["auto_approval"] = {
                "enabled": data.auto_approval.enabled,
                "max_days": data.auto_approval.max_days,
                "leave_types": data.auto_approval.leave_types
            }

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_data["updated_at"] = datetime.utcnow()

        await self.db.leave_approval_workflows.update_one(
            {"_id": obj_id}, {"$set": update_data}
        )

        logger.info(f"Workflow {workflow_id} updated by {current_user.get('email')}")
        updated = await self.db.leave_approval_workflows.find_one({"_id": obj_id})
        return _serialize(updated)

    async def delete_workflow(
        self, workflow_id: str, current_user: dict
    ) -> dict:
        """Delete (deactivate) an approval workflow"""
        org_id = self._org_id_from_user(current_user)

        try:
            obj_id = ObjectId(workflow_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid workflow ID")

        workflow = await self.db.leave_approval_workflows.find_one({
            "_id": obj_id, "organization_id": org_id
        })

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        await self.db.leave_approval_workflows.update_one(
            {"_id": obj_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )

        logger.info(f"Workflow '{workflow['name']}' deactivated by {current_user.get('email')}")
        return {"message": f"Workflow '{workflow['name']}' deactivated successfully"}

    # ------------------------------------------------------------------
    # REPORTS
    # ------------------------------------------------------------------

    async def report_leave_utilization(
        self, current_user: dict, year: int = None, organization_id: str = None
    ) -> dict:
        """Leave utilization report — how much of total entitlement is used per type"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year

        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id, "year": year
        })
        if not config:
            return {"year": year, "utilization": [], "total_employees": 0}

        emp_count = await self.db.employees.count_documents({
            "organization_id": org_id, "is_deleted": False
        })

        utilization = []
        for lt in config.get("leave_types", []):
            if not lt.get("is_active", True):
                continue

            # Total approved days for this type across all employees
            pipeline = [
                {"$match": {
                    "organization_id": org_id,
                    "leave_type_code": lt["code"],
                    "status": "approved",
                    "start_date": {"$regex": f"^{year}"}
                }},
                {"$group": {"_id": None, "total_used": {"$sum": "$days"}, "request_count": {"$sum": 1}}}
            ]
            result = await self.db.leave_requests.aggregate(pipeline).to_list(1)
            total_used = result[0]["total_used"] if result else 0
            request_count = result[0]["request_count"] if result else 0

            total_entitlement = lt["days_per_year"] * emp_count if lt["days_per_year"] != -1 else -1
            utilization_pct = round((total_used / total_entitlement) * 100, 1) if total_entitlement > 0 else 0

            utilization.append({
                "leave_type_code": lt["code"],
                "leave_type_name": lt["name"],
                "total_entitlement": total_entitlement,
                "total_used": total_used,
                "utilization_percentage": utilization_pct,
                "request_count": request_count
            })

        return {"year": year, "total_employees": emp_count, "utilization": utilization}

    async def report_leave_balance(
        self, current_user: dict, department: str = None,
        year: int = None, organization_id: str = None
    ) -> dict:
        """Leave balance report — all employees with their current balances"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year

        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id, "year": year
        })
        if not config:
            return {"year": year, "employees": []}

        query = {"organization_id": org_id, "is_deleted": False}
        if department:
            query["department"] = {"$regex": department, "$options": "i"}

        employees = await self.db.employees.find(
            query, {"first_name": 1, "last_name": 1, "department": 1, "employee_id": 1}
        ).to_list(length=500)

        result = []
        for emp in employees:
            emp_id = str(emp["_id"])
            emp_balances = []
            for lt in config.get("leave_types", []):
                if not lt.get("is_active", True) or lt["days_per_year"] == -1:
                    continue
                used = await self._get_used_leaves(emp_id, lt["code"], year)
                adj = await self._get_adjustments_net(emp_id, lt["code"], year)
                total = lt["days_per_year"] + adj
                balance = total - used
                emp_balances.append({
                    "code": lt["code"],
                    "total": total,
                    "used": used,
                    "balance": balance
                })

            result.append({
                "employee_id": emp.get("employee_id"),
                "name": f"{emp['first_name']} {emp['last_name']}",
                "department": emp.get("department", ""),
                "balances": emp_balances
            })

        return {"year": year, "employees": result, "total": len(result)}

    async def report_monthly_summary(
        self, current_user: dict, year: int = None, month: int = None,
        organization_id: str = None
    ) -> dict:
        """Monthly leave summary — total leaves taken in a given month"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year
        if not month:
            month = datetime.utcnow().month

        month_str = f"{year}-{month:02d}"

        pipeline = [
            {"$match": {
                "organization_id": org_id,
                "status": "approved",
                "start_date": {"$regex": f"^{month_str}"}
            }},
            {"$group": {
                "_id": "$leave_type_code",
                "total_days": {"$sum": "$days"},
                "request_count": {"$sum": 1},
                "employees": {"$addToSet": "$employee_id"}
            }}
        ]
        results = await self.db.leave_requests.aggregate(pipeline).to_list(length=50)

        summary = []
        total_days = 0
        total_requests = 0
        for r in results:
            summary.append({
                "leave_type_code": r["_id"],
                "total_days": r["total_days"],
                "request_count": r["request_count"],
                "unique_employees": len(r["employees"])
            })
            total_days += r["total_days"]
            total_requests += r["request_count"]

        return {
            "year": year,
            "month": month,
            "total_days": total_days,
            "total_requests": total_requests,
            "breakdown": summary
        }

    async def report_department_wise(
        self, current_user: dict, year: int = None, organization_id: str = None
    ) -> dict:
        """Department-wise leave report"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year

        pipeline = [
            {"$match": {
                "organization_id": org_id,
                "status": "approved",
                "start_date": {"$regex": f"^{year}"}
            }},
            {"$group": {
                "_id": "$department",
                "total_days": {"$sum": "$days"},
                "request_count": {"$sum": 1},
                "employees": {"$addToSet": "$employee_id"}
            }},
            {"$sort": {"total_days": -1}}
        ]
        results = await self.db.leave_requests.aggregate(pipeline).to_list(length=50)

        departments = []
        for r in results:
            emp_count = await self.db.employees.count_documents({
                "organization_id": org_id,
                "department": r["_id"],
                "is_deleted": False
            })
            departments.append({
                "department": r["_id"],
                "total_days": r["total_days"],
                "request_count": r["request_count"],
                "unique_employees_on_leave": len(r["employees"]),
                "total_employees": emp_count,
                "avg_days_per_employee": round(r["total_days"] / len(r["employees"]), 1) if r["employees"] else 0
            })

        return {"year": year, "departments": departments}

    async def report_lop(
        self, current_user: dict, year: int = None, month: int = None,
        organization_id: str = None
    ) -> dict:
        """LOP (Loss of Pay) report — employees with unpaid leave"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year

        # LOP = leaves where leave type is LWP (Leave Without Pay) or balance went negative
        query = {
            "organization_id": org_id,
            "status": "approved",
            "start_date": {"$regex": f"^{year}"}
        }

        # Find LWP/unpaid leaves
        config = await self.db.leave_configurations.find_one({
            "organization_id": org_id, "year": year
        })
        unpaid_codes = []
        if config:
            for lt in config.get("leave_types", []):
                if not lt.get("is_paid", True):
                    unpaid_codes.append(lt["code"])

        if not unpaid_codes:
            unpaid_codes = ["LWP"]

        query["leave_type_code"] = {"$in": unpaid_codes}

        if month:
            month_str = f"{year}-{month:02d}"
            query["start_date"] = {"$regex": f"^{month_str}"}

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$employee_id",
                "employee_name": {"$first": "$employee_name"},
                "department": {"$first": "$department"},
                "total_lop_days": {"$sum": "$days"},
                "lop_count": {"$sum": 1}
            }},
            {"$sort": {"total_lop_days": -1}}
        ]
        results = await self.db.leave_requests.aggregate(pipeline).to_list(length=200)

        employees = []
        total_lop_days = 0
        for r in results:
            employees.append({
                "employee_id": r["_id"],
                "employee_name": r["employee_name"],
                "department": r["department"],
                "total_lop_days": r["total_lop_days"],
                "lop_count": r["lop_count"]
            })
            total_lop_days += r["total_lop_days"]

        return {
            "year": year,
            "month": month,
            "total_lop_days": total_lop_days,
            "total_employees_with_lop": len(employees),
            "employees": employees
        }

    async def report_employee_history(
        self, current_user: dict, employee_id: str,
        year: int = None, organization_id: str = None
    ) -> dict:
        """Employee leave history — full leave record for a single employee"""
        org_id = self._org_id_from_user(current_user, organization_id)
        if not year:
            year = datetime.utcnow().year

        # Verify employee
        try:
            emp = await self.db.employees.find_one({
                "_id": ObjectId(employee_id),
                "organization_id": org_id,
                "is_deleted": False
            })
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid employee_id")

        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get all leaves for this employee in the year
        leaves = await self.db.leave_requests.find({
            "employee_id": employee_id,
            "start_date": {"$regex": f"^{year}"}
        }).sort("start_date", -1).to_list(length=200)

        for leave in leaves:
            _serialize(leave)

        # Summary by type
        type_summary = {}
        for leave in leaves:
            code = leave.get("leave_type_code", "")
            if code not in type_summary:
                type_summary[code] = {
                    "leave_type_name": leave.get("leave_type_name", ""),
                    "approved": 0, "pending": 0, "rejected": 0, "cancelled": 0
                }
            status = leave.get("status", "")
            if status in type_summary[code]:
                type_summary[code][status] += leave.get("days", 0)

        return {
            "employee_id": employee_id,
            "employee_name": f"{emp['first_name']} {emp['last_name']}",
            "department": emp.get("department", ""),
            "year": year,
            "total_leaves": len(leaves),
            "type_summary": type_summary,
            "leaves": leaves
        }
