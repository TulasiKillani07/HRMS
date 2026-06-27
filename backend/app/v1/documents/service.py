from datetime import datetime
from fastapi import HTTPException, UploadFile
from bson import ObjectId
from app.database import get_database
from app.models.document import CompanyDocumentModel, EmployeeDocumentModel, DocumentTemplateModel
from app.utils.helpers import paginate_query
from app.utils.logger import logger
from app.utils.cloudinary_upload import upload_file_to_cloudinary
import json


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


class DocumentService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    def _org_id(self, current_user: dict, explicit: str = None) -> str:
        if current_user.get("role") == "superadmin":
            if not explicit:
                raise HTTPException(status_code=400, detail="superadmin must supply organization_id")
            return explicit
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(status_code=400, detail="No organization linked")
        return org_id

    # ==================================================================
    # COMPANY DOCUMENTS
    # ==================================================================

    async def upload_company_doc(self, file: UploadFile, title: str, category: str,
                                 description: str, target_departments: str,
                                 is_mandatory: bool, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)

        # Upload to cloudinary
        upload_result = await upload_file_to_cloudinary(file)
        if not upload_result:
            raise HTTPException(status_code=500, detail="File upload failed")

        # Parse target departments
        depts = []
        if target_departments:
            try:
                depts = json.loads(target_departments)
            except Exception:
                depts = []

        doc = CompanyDocumentModel(
            organization_id=org_id, title=title,
            category=category or "other", description=description,
            file_url=upload_result.get("url", ""),
            file_name=file.filename or "",
            file_size=upload_result.get("size", 0),
            file_type=file.content_type or "",
            target_departments=depts, is_mandatory=is_mandatory,
            acknowledged_by=[], uploaded_by=str(current_user["_id"]),
            uploaded_by_name=current_user.get("full_name", current_user.get("email", "")),
            is_deleted=False, created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        result = await self.db.company_documents.insert_one(doc.model_dump())
        d = doc.model_dump(); d["_id"] = result.inserted_id
        d["acknowledgement_count"] = 0

        # Count recipients
        eq = {"organization_id": org_id, "is_deleted": False, "status": "active"}
        if depts:
            eq["department"] = {"$in": depts}
        d["total_recipients"] = await self.db.employees.count_documents(eq)

        logger.info(f"Company doc '{title}' uploaded for org {org_id}")
        d.pop("acknowledged_by", None)
        return _serialize(d)

    async def list_company_docs(self, current_user: dict, page: int = 1, limit: int = 20,
                                category: str = None, search: str = None, org_id_param: str = None) -> dict:
        role = current_user.get("role")
        org_id = self._org_id(current_user, org_id_param)
        user_id = str(current_user["_id"])
        skip, limit = paginate_query(page, limit)

        query = {"organization_id": org_id, "is_deleted": False}

        if role == "employee":
            emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
            if emp:
                dept = emp.get("department", "")
                query["$or"] = [{"target_departments": {"$size": 0}}, {"target_departments": dept}]

        if category:
            query["category"] = category
        if search:
            query["$or"] = [{"title": {"$regex": search, "$options": "i"}}, {"description": {"$regex": search, "$options": "i"}}]

        total = await self.db.company_documents.count_documents(query)
        docs = await self.db.company_documents.find(query).skip(skip).limit(limit).sort("created_at", -1).to_list(limit)

        results = []
        for d in docs:
            _serialize(d)
            d["acknowledgement_count"] = len(d.get("acknowledged_by", []))
            d["is_acknowledged"] = user_id in d.get("acknowledged_by", [])
            eq = {"organization_id": org_id, "is_deleted": False, "status": "active"}
            if d.get("target_departments"):
                eq["department"] = {"$in": d["target_departments"]}
            d["total_recipients"] = await self.db.employees.count_documents(eq)
            d.pop("acknowledged_by", None)
            results.append(d)

        return {"documents": results, "total": total, "page": page, "pages": (total + limit - 1) // limit}

    async def acknowledge_doc(self, document_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        user_id = str(current_user["_id"])
        try:
            obj_id = ObjectId(document_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid document ID")

        doc = await self.db.company_documents.find_one({"_id": obj_id, "organization_id": org_id, "is_deleted": False})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        await self.db.company_documents.update_one({"_id": obj_id}, {"$addToSet": {"acknowledged_by": user_id}})
        return {"message": "Document acknowledged"}

    async def update_company_doc(self, document_id: str, data: dict, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(document_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid document ID")

        doc = await self.db.company_documents.find_one({"_id": obj_id, "organization_id": org_id, "is_deleted": False})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        update = {k: v for k, v in data.items() if v is not None}
        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")
        update["updated_at"] = datetime.utcnow()
        await self.db.company_documents.update_one({"_id": obj_id}, {"$set": update})
        updated = await self.db.company_documents.find_one({"_id": obj_id})
        updated.pop("acknowledged_by", None)
        return _serialize(updated)

    async def delete_company_doc(self, document_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(document_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid document ID")
        doc = await self.db.company_documents.find_one({"_id": obj_id, "organization_id": org_id, "is_deleted": False})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        await self.db.company_documents.update_one({"_id": obj_id}, {"$set": {"is_deleted": True}})
        return {"message": "Document deleted successfully"}

    # ==================================================================
    # EMPLOYEE DOCUMENTS
    # ==================================================================

    async def upload_employee_doc(self, file: UploadFile, title: str, category: str,
                                   employee_id: str, current_user: dict, org_id_param: str = None) -> dict:
        role = current_user.get("role")
        org_id = self._org_id(current_user, org_id_param)

        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
        else:
            if not employee_id:
                raise HTTPException(status_code=400, detail="employee_id required for HR")
            try:
                emp = await self.db.employees.find_one({"_id": ObjectId(employee_id), "organization_id": org_id, "is_deleted": False})
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid employee_id")
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")

        upload_result = await upload_file_to_cloudinary(file)
        if not upload_result:
            raise HTTPException(status_code=500, detail="File upload failed")

        doc = EmployeeDocumentModel(
            organization_id=org_id, employee_id=str(emp["_id"]),
            employee_name=f"{emp['first_name']} {emp['last_name']}",
            title=title, category=category or "other",
            file_url=upload_result.get("url", ""),
            file_name=file.filename or "",
            file_size=upload_result.get("size", 0),
            file_type=file.content_type or "",
            uploaded_by=str(current_user["_id"]),
            uploaded_by_name=current_user.get("full_name", current_user.get("email", "")),
            is_deleted=False, created_at=datetime.utcnow()
        )
        result = await self.db.employee_documents.insert_one(doc.model_dump())
        d = doc.model_dump(); d["_id"] = result.inserted_id
        logger.info(f"Employee doc '{title}' uploaded for {emp['first_name']}")
        return _serialize(d)

    async def list_employee_docs(self, current_user: dict, employee_id: str = None,
                                  category: str = None, page: int = 1, limit: int = 20,
                                  org_id_param: str = None) -> dict:
        role = current_user.get("role")
        org_id = self._org_id(current_user, org_id_param)
        skip, limit = paginate_query(page, limit)

        if role == "employee":
            user_id = str(current_user["_id"])
            emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
            if not emp:
                raise HTTPException(status_code=404, detail="Employee not found")
            emp_id = str(emp["_id"])
        else:
            if not employee_id:
                raise HTTPException(status_code=400, detail="employee_id required for HR")
            emp_id = employee_id

        query = {"employee_id": emp_id, "is_deleted": False}
        if category:
            query["category"] = category

        total = await self.db.employee_documents.count_documents(query)
        docs = await self.db.employee_documents.find(query).skip(skip).limit(limit).sort("created_at", -1).to_list(limit)
        for d in docs:
            _serialize(d)
        return {"documents": docs, "total": total, "page": page, "pages": (total + limit - 1) // limit}

    async def delete_employee_doc(self, document_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(document_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid document ID")
        doc = await self.db.employee_documents.find_one({"_id": obj_id, "is_deleted": False})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        await self.db.employee_documents.update_one({"_id": obj_id}, {"$set": {"is_deleted": True}})
        return {"message": "Document deleted successfully"}

    # ==================================================================
    # DOCUMENT TEMPLATES
    # ==================================================================

    async def upload_template(self, file: UploadFile, title: str, description: str,
                              current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)

        upload_result = await upload_file_to_cloudinary(file)
        if not upload_result:
            raise HTTPException(status_code=500, detail="File upload failed")

        tpl = DocumentTemplateModel(
            organization_id=org_id, title=title, description=description,
            file_url=upload_result.get("url", ""),
            file_name=file.filename or "",
            file_type=file.content_type or "",
            download_count=0, uploaded_by=str(current_user["_id"]),
            is_deleted=False, created_at=datetime.utcnow()
        )
        result = await self.db.document_templates.insert_one(tpl.model_dump())
        d = tpl.model_dump(); d["_id"] = result.inserted_id
        return _serialize(d)

    async def list_templates(self, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        docs = await self.db.document_templates.find(
            {"organization_id": org_id, "is_deleted": False}
        ).sort("created_at", -1).to_list(50)
        for d in docs:
            _serialize(d)
        return {"templates": docs}

    async def delete_template(self, template_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(template_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid template ID")
        tpl = await self.db.document_templates.find_one({"_id": obj_id, "organization_id": org_id, "is_deleted": False})
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        await self.db.document_templates.update_one({"_id": obj_id}, {"$set": {"is_deleted": True}})
        return {"message": "Template deleted successfully"}

    # ==================================================================
    # DOCUMENT REQUESTS (HR requests → Employee uploads)
    # ==================================================================

    async def create_doc_request(self, employee_id: str, title: str, description: str,
                                  category: str, due_date: str, current_user: dict,
                                  org_id_param: str = None) -> dict:
        """HR requests a document from an employee"""
        from app.models.document import DocumentRequestModel
        from app.v1.notifications.service import NotificationService

        org_id = self._org_id(current_user, org_id_param)

        try:
            emp = await self.db.employees.find_one({
                "_id": ObjectId(employee_id), "organization_id": org_id, "is_deleted": False
            })
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid employee_id")
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        req = DocumentRequestModel(
            organization_id=org_id, employee_id=employee_id,
            employee_name=f"{emp['first_name']} {emp['last_name']}",
            department=emp.get("department", ""),
            title=title, description=description or None,
            category=category or "other", due_date=due_date or None,
            status="pending",
            requested_by=str(current_user["_id"]),
            requested_by_name=current_user.get("full_name", current_user.get("email", "")),
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        result = await self.db.document_requests.insert_one(req.model_dump())
        d = req.model_dump(); d["_id"] = result.inserted_id

        # Notify employee
        notif = NotificationService(self.db)
        if emp.get("user_id"):
            hr_name = current_user.get("full_name", current_user.get("email", ""))
            await notif.create_notification(
                organization_id=org_id, user_id=emp["user_id"],
                title="Document Requested",
                message=f"{hr_name} has requested you to upload: {title}",
                type="action", category="document",
                reference_id=str(result.inserted_id), reference_type="document_request"
            )

        logger.info(f"Document request '{title}' created for {emp['first_name']}")
        return _serialize(d)

    async def list_doc_requests(self, current_user: dict, employee_id: str = None,
                                 status_filter: str = None, page: int = 1, limit: int = 20,
                                 org_id_param: str = None) -> dict:
        """List document requests"""
        role = current_user.get("role")
        org_id = self._org_id(current_user, org_id_param)
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

        total = await self.db.document_requests.count_documents(query)
        docs = await self.db.document_requests.find(query).skip(skip).limit(limit).sort("created_at", -1).to_list(limit)
        for d in docs:
            _serialize(d)
        return {"requests": docs, "total": total, "page": page, "pages": (total + limit - 1) // limit}

    async def upload_requested_doc(self, request_id: str, file, current_user: dict) -> dict:
        """Employee uploads the requested document"""
        from app.v1.notifications.service import NotificationService

        user_id = str(current_user["_id"])
        emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        try:
            obj_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request ID")

        req = await self.db.document_requests.find_one({
            "_id": obj_id, "employee_id": str(emp["_id"]), "status": "pending"
        })
        if not req:
            raise HTTPException(status_code=404, detail="No pending document request found")

        # Upload file
        upload_result = await upload_file_to_cloudinary(file)
        if not upload_result:
            raise HTTPException(status_code=500, detail="Upload failed")

        now = datetime.utcnow()
        await self.db.document_requests.update_one({"_id": obj_id}, {"$set": {
            "file_url": upload_result.get("url", ""),
            "file_name": file.filename or "",
            "file_size": upload_result.get("size", 0),
            "file_type": file.content_type or "",
            "uploaded_at": now,
            "status": "uploaded",
            "updated_at": now
        }})

        # Notify HR who requested
        notif = NotificationService(self.db)
        emp_name = f"{emp['first_name']} {emp['last_name']}"
        await notif.notify_org_hrs(
            organization_id=req["organization_id"],
            title="Document Uploaded",
            message=f"{emp_name} has uploaded '{req['title']}'",
            type="info", category="document",
            reference_id=str(obj_id), reference_type="document_request"
        )

        logger.info(f"{emp_name} uploaded document for request '{req['title']}'")
        updated = await self.db.document_requests.find_one({"_id": obj_id})
        return _serialize(updated)

    async def review_doc_request(self, request_id: str, action: str, reason: str,
                                  current_user: dict) -> dict:
        """HR approves or rejects uploaded document"""
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request ID")

        req = await self.db.document_requests.find_one({
            "_id": obj_id, "organization_id": org_id, "status": "uploaded"
        })
        if not req:
            raise HTTPException(status_code=404, detail="No uploaded document request found")

        now = datetime.utcnow()
        if action == "approve":
            await self.db.document_requests.update_one({"_id": obj_id}, {"$set": {
                "status": "approved",
                "reviewed_by": str(current_user["_id"]),
                "reviewed_by_name": current_user.get("full_name", current_user.get("email", "")),
                "reviewed_at": now, "updated_at": now
            }})
        elif action == "reject":
            await self.db.document_requests.update_one({"_id": obj_id}, {"$set": {
                "status": "rejected",
                "rejection_reason": reason,
                "reviewed_by": str(current_user["_id"]),
                "reviewed_by_name": current_user.get("full_name", current_user.get("email", "")),
                "reviewed_at": now, "updated_at": now,
                "file_url": None, "file_name": None  # Clear uploaded file on rejection
            }})
            # Re-set to pending so employee can re-upload
            await self.db.document_requests.update_one({"_id": obj_id}, {"$set": {"status": "pending"}})

            # Notify employee
            from app.v1.notifications.service import NotificationService
            notif = NotificationService(self.db)
            emp = await self.db.employees.find_one({"_id": ObjectId(req["employee_id"])})
            if emp and emp.get("user_id"):
                reviewer = current_user.get("full_name", current_user.get("email", ""))
                await notif.create_notification(
                    organization_id=org_id, user_id=emp["user_id"],
                    title="Document Rejected",
                    message=f"Your uploaded '{req['title']}' was rejected by {reviewer}. Reason: {reason}. Please re-upload.",
                    type="alert", category="document",
                    reference_id=str(obj_id), reference_type="document_request"
                )
        else:
            raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

        updated = await self.db.document_requests.find_one({"_id": obj_id})
        return _serialize(updated)
