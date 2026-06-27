from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId
from app.database import get_database
from app.models.announcement import AnnouncementModel
from app.utils.helpers import paginate_query
from app.utils.logger import logger
from app.v1.notifications.service import NotificationService


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


class AnnouncementService:
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

    async def create(self, data, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)

        # Count total recipients
        emp_query = {"organization_id": org_id, "is_deleted": False, "status": "active"}
        if data.target_departments:
            emp_query["department"] = {"$in": data.target_departments}
        total_recipients = await self.db.employees.count_documents(emp_query)

        ann = AnnouncementModel(
            organization_id=org_id, title=data.title, content=data.content,
            type=data.type, priority=data.priority,
            target_departments=data.target_departments,
            is_pinned=data.is_pinned, expires_at=data.expires_at,
            created_by=str(current_user["_id"]),
            created_by_name=current_user.get("full_name", current_user.get("email", "")),
            is_deleted=False, read_by=[],
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        result = await self.db.announcements.insert_one(ann.model_dump())
        d = ann.model_dump()
        d["_id"] = result.inserted_id
        d["read_count"] = 0
        d["total_recipients"] = total_recipients

        # Send notification to all targeted employees
        notif_service = NotificationService(self.db)
        emp_query_notif = {"organization_id": org_id, "is_deleted": False, "status": "active"}
        if data.target_departments:
            emp_query_notif["department"] = {"$in": data.target_departments}
        employees = await self.db.employees.find(emp_query_notif, {"user_id": 1}).to_list(500)
        for emp in employees:
            if emp.get("user_id"):
                await notif_service.create_notification(
                    organization_id=org_id, user_id=emp["user_id"],
                    title=f"New Announcement: {data.title}",
                    message=data.content[:100] + ("..." if len(data.content) > 100 else ""),
                    type="info" if data.priority != "high" else "alert",
                    category="announcement",
                    reference_id=str(result.inserted_id),
                    reference_type="announcement"
                )

        logger.info(f"Announcement '{data.title}' created for org {org_id}")
        return _serialize(d)

    async def get_list(self, current_user: dict, page: int = 1, limit: int = 20,
                       type_filter: str = None, is_pinned: str = None,
                       search: str = None, department: str = None, org_id_param: str = None) -> dict:
        role = current_user.get("role")
        org_id = self._org_id(current_user, org_id_param)
        skip, limit = paginate_query(page, limit)
        user_id = str(current_user["_id"])
        today = datetime.utcnow().strftime("%Y-%m-%d")

        query = {"organization_id": org_id, "is_deleted": False}

        # Filter expired
        query["$or"] = [{"expires_at": None}, {"expires_at": ""}, {"expires_at": {"$gte": today}}]

        # Employee sees only their department or all-targeted
        if role == "employee":
            emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
            if emp:
                dept = emp.get("department", "")
                query["$and"] = [
                    {"$or": [
                        {"target_departments": {"$size": 0}},
                        {"target_departments": dept}
                    ]}
                ]

        if type_filter:
            query["type"] = type_filter
        if is_pinned == "true":
            query["is_pinned"] = True
        if department:
            query["target_departments"] = department
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"content": {"$regex": search, "$options": "i"}}
            ]

        total = await self.db.announcements.count_documents(query)
        cursor = self.db.announcements.find(query).skip(skip).limit(limit).sort([("is_pinned", -1), ("created_at", -1)])
        anns = await cursor.to_list(length=limit)

        results = []
        for a in anns:
            _serialize(a)
            a["read_count"] = len(a.get("read_by", []))
            a["is_read"] = user_id in a.get("read_by", [])
            # Count recipients
            eq = {"organization_id": org_id, "is_deleted": False, "status": "active"}
            if a.get("target_departments"):
                eq["department"] = {"$in": a["target_departments"]}
            a["total_recipients"] = await self.db.employees.count_documents(eq)
            a.pop("read_by", None)  # Don't expose full list
            results.append(a)

        return {"announcements": results, "total": total, "page": page, "pages": (total + limit - 1) // limit}

    async def get_by_id(self, announcement_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        user_id = str(current_user["_id"])
        try:
            obj_id = ObjectId(announcement_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid announcement ID")

        ann = await self.db.announcements.find_one({"_id": obj_id, "organization_id": org_id, "is_deleted": False})
        if not ann:
            raise HTTPException(status_code=404, detail="Announcement not found")

        # Auto-mark as read
        if user_id not in ann.get("read_by", []):
            await self.db.announcements.update_one(
                {"_id": obj_id}, {"$addToSet": {"read_by": user_id}}
            )
            ann["read_by"].append(user_id)

        _serialize(ann)
        ann["read_count"] = len(ann.get("read_by", []))
        ann["is_read"] = True
        ann.pop("read_by", None)
        return ann

    async def update(self, announcement_id: str, data, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(announcement_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid announcement ID")

        ann = await self.db.announcements.find_one({"_id": obj_id, "organization_id": org_id, "is_deleted": False})
        if not ann:
            raise HTTPException(status_code=404, detail="Announcement not found")

        update = data.model_dump(exclude_unset=True)
        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")
        update["updated_at"] = datetime.utcnow()

        await self.db.announcements.update_one({"_id": obj_id}, {"$set": update})
        updated = await self.db.announcements.find_one({"_id": obj_id})
        _serialize(updated)
        updated["read_count"] = len(updated.get("read_by", []))
        updated.pop("read_by", None)
        return updated

    async def delete(self, announcement_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(announcement_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid announcement ID")

        ann = await self.db.announcements.find_one({"_id": obj_id, "organization_id": org_id, "is_deleted": False})
        if not ann:
            raise HTTPException(status_code=404, detail="Announcement not found")

        await self.db.announcements.update_one({"_id": obj_id}, {"$set": {"is_deleted": True, "updated_at": datetime.utcnow()}})
        return {"message": "Announcement deleted successfully"}

    async def mark_read(self, announcement_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        user_id = str(current_user["_id"])
        try:
            obj_id = ObjectId(announcement_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid announcement ID")

        ann = await self.db.announcements.find_one({"_id": obj_id, "organization_id": org_id, "is_deleted": False})
        if not ann:
            raise HTTPException(status_code=404, detail="Announcement not found")

        await self.db.announcements.update_one({"_id": obj_id}, {"$addToSet": {"read_by": user_id}})
        return {"message": "Marked as read"}

    async def unread_count(self, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        user_id = str(current_user["_id"])
        role = current_user.get("role")
        today = datetime.utcnow().strftime("%Y-%m-%d")

        query = {"organization_id": org_id, "is_deleted": False,
                 "read_by": {"$nin": [user_id]},
                 "$or": [{"expires_at": None}, {"expires_at": ""}, {"expires_at": {"$gte": today}}]}

        if role == "employee":
            emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
            if emp:
                dept = emp.get("department", "")
                query["$and"] = [{"$or": [{"target_departments": {"$size": 0}}, {"target_departments": dept}]}]

        count = await self.db.announcements.count_documents(query)
        return {"unread_count": count}
