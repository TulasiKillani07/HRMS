from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId
from app.database import get_database
from app.models.activity_log import ActivityLogModel
from app.utils.helpers import paginate_query


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


class ActivityLogService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    # ------------------------------------------------------------------
    # LOG AN ACTION (internal helper — called by other services)
    # ------------------------------------------------------------------

    async def log(
        self,
        user: dict,
        action: str,
        module: str,
        description: str,
        target_id: str = None,
        target_name: str = None,
        target_type: str = None,
        metadata: dict = None,
        ip_address: str = None
    ):
        """Create an activity log entry"""
        entry = ActivityLogModel(
            organization_id=user.get("organization_id"),
            user_id=str(user["_id"]),
            user_name=user.get("full_name", user.get("email", "")),
            user_role=user.get("role", ""),
            action=action,
            module=module,
            description=description,
            target_id=target_id,
            target_name=target_name,
            target_type=target_type,
            metadata=metadata,
            ip_address=ip_address,
            created_at=datetime.utcnow()
        )
        await self.db.activity_logs.insert_one(entry.model_dump())

    # ------------------------------------------------------------------
    # GET LOGS (superadmin / org_admin)
    # ------------------------------------------------------------------

    async def get_logs(
        self, current_user: dict, page: int = 1, limit: int = 50,
        module: str = None, action: str = None, user_id: str = None,
        user_role: str = None, from_date: str = None, to_date: str = None,
        search: str = None
    ) -> dict:
        role = current_user.get("role")

        if role == "superadmin":
            query = {}  # sees all across orgs
        elif role == "org_admin":
            org_id = current_user.get("organization_id")
            if not org_id:
                raise HTTPException(status_code=400, detail="No organization linked")
            query = {"organization_id": org_id}
        else:
            raise HTTPException(status_code=403, detail="Only superadmin and org_admin can view logs")

        if module:
            query["module"] = module
        if action:
            query["action"] = action
        if user_id:
            query["user_id"] = user_id
        if user_role:
            query["user_role"] = user_role
        if from_date:
            query.setdefault("created_at", {})["$gte"] = datetime.strptime(from_date, "%Y-%m-%d")
        if to_date:
            query.setdefault("created_at", {})["$lte"] = datetime.strptime(to_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
        if search:
            query["description"] = {"$regex": search, "$options": "i"}

        skip, limit = paginate_query(page, limit)
        total = await self.db.activity_logs.count_documents(query)
        cursor = self.db.activity_logs.find(query).skip(skip).limit(limit).sort("created_at", -1)
        logs = await cursor.to_list(length=limit)
        for log in logs:
            _serialize(log)

        return {
            "logs": logs,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    async def get_log_stats(self, current_user: dict) -> dict:
        """Quick stats for dashboard"""
        role = current_user.get("role")
        if role == "superadmin":
            query = {}
        elif role == "org_admin":
            query = {"organization_id": current_user.get("organization_id")}
        else:
            raise HTTPException(status_code=403, detail="Access denied")

        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_query = {**query, "created_at": {"$gte": datetime.strptime(today, "%Y-%m-%d")}}

        total_today = await self.db.activity_logs.count_documents(today_query)
        total_all = await self.db.activity_logs.count_documents(query)

        # Actions by module today
        pipeline = [
            {"$match": today_query},
            {"$group": {"_id": "$module", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_module = await self.db.activity_logs.aggregate(pipeline).to_list(20)

        return {
            "total_today": total_today,
            "total_all": total_all,
            "today_by_module": {r["_id"]: r["count"] for r in by_module}
        }
