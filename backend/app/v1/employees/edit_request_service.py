from datetime import datetime
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.edit_request import EditRequestModel
from app.models.employee import ONBOARDING_SECTIONS
from app.utils.helpers import paginate_query
from app.utils.logger import logger
from app.v1.notifications.service import NotificationService


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


EDITABLE_SECTIONS = [
    "personal_details", "address", "emergency_contact",
    "bank_details", "government_ids", "education", "experience"
]


class EditRequestService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    def _org_id_from_user(self, current_user: dict) -> str:
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(status_code=400, detail="No organization linked")
        return org_id

    # ------------------------------------------------------------------
    # Employee: Create edit request
    # ------------------------------------------------------------------

    async def create_edit_request(
        self, data, current_user: dict
    ) -> dict:
        """Employee requests permission to edit a section"""
        user_id = str(current_user["_id"])
        role = current_user.get("role")

        if role != "employee":
            raise HTTPException(status_code=403, detail="Only employees can request edit permission")

        emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee record not found")

        if emp.get("status") != "active":
            raise HTTPException(status_code=400, detail="Only active employees can request edits")

        if data.section not in EDITABLE_SECTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid section. Must be one of: {EDITABLE_SECTIONS}"
            )

        # Check if there's already a pending request for this section
        existing = await self.db.edit_requests.find_one({
            "employee_id": str(emp["_id"]),
            "section": data.section,
            "status": "pending"
        })
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"You already have a pending edit request for '{data.section}'"
            )

        org_id = emp.get("organization_id", "")
        request_model = EditRequestModel(
            organization_id=org_id,
            employee_id=str(emp["_id"]),
            employee_name=f"{emp['first_name']} {emp['last_name']}",
            department=emp.get("department", ""),
            section=data.section,
            reason=data.reason,
            status="pending",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        result = await self.db.edit_requests.insert_one(request_model.model_dump())
        req_dict = request_model.model_dump()
        req_dict["_id"] = result.inserted_id

        # Send notification to all HRs
        notif_service = NotificationService(self.db)
        emp_name = f"{emp['first_name']} {emp['last_name']}"
        await notif_service.notify_org_hrs(
            organization_id=org_id,
            title="Profile Edit Request",
            message=f"{emp_name} wants to edit '{data.section}'. Reason: {data.reason}",
            type="action",
            category="edit_request",
            reference_id=str(result.inserted_id),
            reference_type="edit_request"
        )

        logger.info(f"Edit request created: {emp_name} wants to edit '{data.section}'")
        return _serialize(req_dict)

    # ------------------------------------------------------------------
    # HR: Approve edit request
    # ------------------------------------------------------------------

    async def approve_edit_request(
        self, request_id: str, current_user: dict
    ) -> dict:
        """HR approves — employee can now edit anytime"""
        try:
            obj_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request ID")

        org_id = self._org_id_from_user(current_user)
        req = await self.db.edit_requests.find_one({
            "_id": obj_id, "organization_id": org_id
        })

        if not req:
            raise HTTPException(status_code=404, detail="Edit request not found")

        if req["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Cannot approve: status is '{req['status']}'")

        await self.db.edit_requests.update_one(
            {"_id": obj_id},
            {"$set": {
                "status": "approved",
                "approved_by": str(current_user["_id"]),
                "approved_by_name": current_user.get("full_name", current_user.get("email", "")),
                "approved_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )

        # Notify the employee
        notif_service = NotificationService(self.db)
        # Get employee's user_id
        emp = await self.db.employees.find_one({"_id": ObjectId(req["employee_id"])})
        if emp and emp.get("user_id"):
            approver_name = current_user.get("full_name", current_user.get("email", ""))
            await notif_service.create_notification(
                organization_id=org_id,
                user_id=emp["user_id"],
                title="Edit Request Approved",
                message=f"Your request to edit '{req['section']}' has been approved by {approver_name}. You can now make changes.",
                type="info",
                category="edit_request",
                reference_id=str(obj_id),
                reference_type="edit_request"
            )

        logger.info(f"Edit request {request_id} approved by {current_user.get('email')}")
        updated = await self.db.edit_requests.find_one({"_id": obj_id})
        return _serialize(updated)

    # ------------------------------------------------------------------
    # HR: Reject edit request
    # ------------------------------------------------------------------

    async def reject_edit_request(
        self, request_id: str, reason: str, current_user: dict
    ) -> dict:
        """HR rejects edit request"""
        try:
            obj_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request ID")

        org_id = self._org_id_from_user(current_user)
        req = await self.db.edit_requests.find_one({
            "_id": obj_id, "organization_id": org_id
        })

        if not req:
            raise HTTPException(status_code=404, detail="Edit request not found")

        if req["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Cannot reject: status is '{req['status']}'")

        await self.db.edit_requests.update_one(
            {"_id": obj_id},
            {"$set": {
                "status": "rejected",
                "rejection_reason": reason,
                "rejected_by": str(current_user["_id"]),
                "rejected_by_name": current_user.get("full_name", current_user.get("email", "")),
                "rejected_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )

        # Notify the employee
        notif_service = NotificationService(self.db)
        emp = await self.db.employees.find_one({"_id": ObjectId(req["employee_id"])})
        if emp and emp.get("user_id"):
            rejector_name = current_user.get("full_name", current_user.get("email", ""))
            await notif_service.create_notification(
                organization_id=org_id,
                user_id=emp["user_id"],
                title="Edit Request Rejected",
                message=f"Your request to edit '{req['section']}' was rejected by {rejector_name}. Reason: {reason}",
                type="alert",
                category="edit_request",
                reference_id=str(obj_id),
                reference_type="edit_request"
            )

        logger.info(f"Edit request {request_id} rejected by {current_user.get('email')}")
        updated = await self.db.edit_requests.find_one({"_id": obj_id})
        return _serialize(updated)

    # ------------------------------------------------------------------
    # Employee: Save edit (within time window)
    # ------------------------------------------------------------------

    async def save_edit(
        self, request_id: str, section_data: dict, current_user: dict
    ) -> dict:
        """Employee saves their edit after approval"""
        user_id = str(current_user["_id"])

        emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee record not found")

        try:
            obj_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request ID")

        req = await self.db.edit_requests.find_one({
            "_id": obj_id,
            "employee_id": str(emp["_id"]),
            "status": "approved",
            "edit_completed": False
        })

        if not req:
            raise HTTPException(status_code=404, detail="No approved edit request found")

        section = req["section"]

        # Update the employee's section data
        await self.db.employees.update_one(
            {"_id": emp["_id"]},
            {"$set": {
                section: section_data,
                "updated_at": datetime.utcnow()
            }}
        )

        # Mark edit as completed
        await self.db.edit_requests.update_one(
            {"_id": obj_id},
            {"$set": {
                "edit_completed": True,
                "edit_completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )

        logger.info(
            f"Edit completed: {req['employee_name']} updated '{section}' "
            f"(request {request_id}, approved by {req.get('approved_by_name')})"
        )

        return {
            "message": f"Section '{section}' updated successfully",
            "section": section,
            "edit_request_id": str(obj_id),
            "approved_by": req.get("approved_by_name"),
            "completed_at": datetime.utcnow()
        }

    # ------------------------------------------------------------------
    # List edit requests
    # ------------------------------------------------------------------

    async def get_edit_requests(
        self, current_user: dict, page: int = 1, limit: int = 10,
        status_filter: str = None, employee_id: str = None
    ) -> dict:
        """List edit requests — employee sees own, HR sees all"""
        role = current_user.get("role")
        org_id = self._org_id_from_user(current_user)
        skip, limit = paginate_query(page, limit)

        query = {"organization_id": org_id}

        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
            query["employee_id"] = str(emp["_id"])
        elif employee_id:
            query["employee_id"] = employee_id

        if status_filter:
            query["status"] = status_filter

        total = await self.db.edit_requests.count_documents(query)
        cursor = self.db.edit_requests.find(query).skip(skip).limit(limit).sort("created_at", -1)
        requests = await cursor.to_list(length=limit)
        for req in requests:
            _serialize(req)

        return {
            "requests": requests,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    # ------------------------------------------------------------------
    # Check if employee can edit a section (has active approved request)
    # ------------------------------------------------------------------

    async def can_edit_section(
        self, section: str, current_user: dict
    ) -> dict:
        """Check if employee has an approved edit request for a section"""
        user_id = str(current_user["_id"])
        emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        req = await self.db.edit_requests.find_one({
            "employee_id": str(emp["_id"]),
            "section": section,
            "status": "approved",
            "edit_completed": False
        })

        if req:
            return {
                "can_edit": True,
                "request_id": str(req["_id"]),
                "section": section,
                "approved_by": req.get("approved_by_name"),
                "approved_at": req.get("approved_at")
            }
        else:
            return {
                "can_edit": False,
                "section": section,
                "message": "No active edit permission. Submit a new request."
            }
