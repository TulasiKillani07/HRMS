from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from app.database import get_database
from app.models.notification import NotificationModel
from app.utils.helpers import paginate_query
from app.utils.logger import logger


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


class NotificationService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    # ------------------------------------------------------------------
    # CREATE notification (internal helper — used by other services)
    # ------------------------------------------------------------------

    async def create_notification(
        self,
        organization_id: str,
        user_id: str,
        title: str,
        message: str,
        type: str = "info",
        category: str = "general",
        reference_id: str = None,
        reference_type: str = None
    ) -> str:
        """Create a single notification. Returns notification ID."""
        notif = NotificationModel(
            organization_id=organization_id,
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            category=category,
            reference_id=reference_id,
            reference_type=reference_type,
            is_read=False,
            created_at=datetime.utcnow()
        )
        result = await self.db.notifications.insert_one(notif.model_dump())
        return str(result.inserted_id)

    async def notify_org_hrs(
        self,
        organization_id: str,
        title: str,
        message: str,
        type: str = "action",
        category: str = "general",
        reference_id: str = None,
        reference_type: str = None
    ) -> int:
        """Send notification to all HR admins and org admins in an organization"""
        hrs = await self.db.users.find({
            "organization_id": organization_id,
            "role": {"$in": ["hr_admin", "org_admin"]},
            "is_active": True
        }).to_list(length=100)

        count = 0
        for hr in hrs:
            await self.create_notification(
                organization_id=organization_id,
                user_id=str(hr["_id"]),
                title=title,
                message=message,
                type=type,
                category=category,
                reference_id=reference_id,
                reference_type=reference_type
            )
            count += 1

        return count

    # ------------------------------------------------------------------
    # GET notifications for current user
    # ------------------------------------------------------------------

    async def get_my_notifications(
        self, current_user: dict, page: int = 1, limit: int = 20,
        is_read: str = None, category: str = None
    ) -> dict:
        user_id = str(current_user["_id"])
        skip, limit = paginate_query(page, limit)

        query = {"user_id": user_id}
        if is_read == "true":
            query["is_read"] = True
        elif is_read == "false":
            query["is_read"] = False
        if category:
            query["category"] = category

        total = await self.db.notifications.count_documents(query)
        cursor = self.db.notifications.find(query).skip(skip).limit(limit).sort("created_at", -1)
        notifications = await cursor.to_list(length=limit)
        for n in notifications:
            _serialize(n)

        # Unread count
        unread = await self.db.notifications.count_documents({"user_id": user_id, "is_read": False})

        return {
            "notifications": notifications,
            "total": total,
            "unread_count": unread,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    # ------------------------------------------------------------------
    # Mark as read
    # ------------------------------------------------------------------

    async def mark_as_read(self, notification_id: str, current_user: dict) -> dict:
        user_id = str(current_user["_id"])
        try:
            obj_id = ObjectId(notification_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid notification ID")

        notif = await self.db.notifications.find_one({"_id": obj_id, "user_id": user_id})
        if not notif:
            raise HTTPException(status_code=404, detail="Notification not found")

        await self.db.notifications.update_one(
            {"_id": obj_id},
            {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
        )
        return {"message": "Marked as read"}

    async def mark_all_as_read(self, current_user: dict) -> dict:
        user_id = str(current_user["_id"])
        result = await self.db.notifications.update_many(
            {"user_id": user_id, "is_read": False},
            {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
        )
        return {"message": f"{result.modified_count} notifications marked as read"}

    async def get_unread_count(self, current_user: dict) -> dict:
        user_id = str(current_user["_id"])
        count = await self.db.notifications.count_documents({"user_id": user_id, "is_read": False})
        return {"unread_count": count}

    async def delete_notification(self, notification_id: str, current_user: dict) -> dict:
        user_id = str(current_user["_id"])
        try:
            obj_id = ObjectId(notification_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid notification ID")

        notif = await self.db.notifications.find_one({"_id": obj_id, "user_id": user_id})
        if not notif:
            raise HTTPException(status_code=404, detail="Notification not found")

        await self.db.notifications.delete_one({"_id": obj_id})
        return {"message": "Notification deleted"}

    async def clear_all_notifications(self, current_user: dict) -> dict:
        user_id = str(current_user["_id"])
        result = await self.db.notifications.delete_many({"user_id": user_id})
        return {"message": f"{result.deleted_count} notifications cleared"}
