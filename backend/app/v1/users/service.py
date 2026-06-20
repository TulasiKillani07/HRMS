from datetime import datetime
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.user import UserModel
from app.core.security import get_password_hash
from app.utils.helpers import convert_objectid_to_str, paginate_query
from app.utils.notifications import send_invitation_email
from app.utils.logger import logger
from app.v1.users.schema import UserCreateRequest, UserUpdateRequest


ALLOWED_ROLES_BY_CREATOR = {
    "superadmin": ["org_admin", "hr_admin"],
    "org_admin": ["hr_admin"],
}


class UserManagementService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _serialize(self, user: dict) -> dict:
        """Map _id → id, stringify ObjectId, and compute status field."""
        user["id"] = str(user["_id"])
        del user["_id"]
        # Derive human-readable status from is_active flag
        user["status"] = "active" if user.get("is_active", True) else "inactive"
        return user

    async def _attach_org_name(self, user: dict) -> dict:
        """Attach org_name to a user dict by looking up organization_id."""
        org_id = user.get("organization_id")
        if org_id:
            try:
                org = await self.db.organizations.find_one(
                    {"_id": ObjectId(org_id)},
                    {"org_name": 1}
                )
                user["org_name"] = org.get("org_name") if org else None
            except Exception:
                user["org_name"] = None
        else:
            user["org_name"] = None
        return user

    async def _get_organization(self, org_id: str) -> dict:
        """Fetch an active organization or raise 404."""
        try:
            org = await self.db.organizations.find_one({
                "_id": ObjectId(org_id),
                "is_deleted": False
            })
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization ID format"
            )
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        return org

    async def _check_admin_limit(self, org_id: str, org: dict) -> None:
        """Raise 403 if the org has hit its admin_user_access_limit."""
        limit = org.get("admin_user_access_limit", 2)
        current_count = await self.db.users.count_documents({
            "organization_id": org_id,
            "role": {"$in": ["org_admin", "hr_admin"]},
            "is_active": True
        })
        if current_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Admin user limit reached for this organization. "
                    f"Limit: {limit}, Current: {current_count}"
                )
            )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_user(self, data: UserCreateRequest, current_user: dict) -> dict:
        creator_role = current_user.get("role")
        allowed = ALLOWED_ROLES_BY_CREATOR.get(creator_role, [])

        # Validate the role being created is permitted
        if data.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{creator_role} can only create users with role(s): {allowed}"
            )

        # Determine organization context
        if creator_role == "superadmin":
            if not data.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="organization_id is required when superadmin creates an org_admin"
                )
            org_id = data.organization_id
        else:
            # org_admin — use their own organization
            org_id = current_user.get("organization_id")
            if not org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Your account is not linked to any organization"
                )

        # Fetch and validate org
        org = await self._get_organization(org_id)

        # Check admin user limit (applies to both org_admin and hr_admin)
        await self._check_admin_limit(org_id, org)

        # Check email uniqueness
        existing = await self.db.users.find_one({"email": data.email})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists"
            )

        temp_password = "Welcome1"

        user_model = UserModel(
            email=data.email,
            hashed_password=get_password_hash(temp_password),
            full_name=data.full_name,
            role=data.role,
            phone=data.phone,
            is_active=True,
            is_verified=False,
            requires_password_change=True,
            organization_id=org_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        result = await self.db.users.insert_one(user_model.model_dump())
        user_id = str(result.inserted_id)
        logger.info(f"Created user {data.email} with role {data.role} for org {org_id}")

        # Send invitation email
        org_name = org.get("org_name", "Your Organization")
        await send_invitation_email(
            email=data.email,
            admin_name=data.full_name,
            org_name=org_name,
            temp_password=temp_password
        )

        user_dict = user_model.model_dump()
        user_dict["id"] = user_id
        user_dict["status"] = "active"
        return user_dict

    # ------------------------------------------------------------------
    # Read — list
    # ------------------------------------------------------------------

    async def get_users(
        self,
        current_user: dict,
        page: int = 1,
        limit: int = 10,
        include_inactive: bool = False
    ) -> dict:
        creator_role = current_user.get("role")
        skip, limit = paginate_query(page, limit)

        if creator_role == "superadmin":
            # Sees all org_admin and hr_admin users
            query: dict = {"role": {"$in": ["org_admin", "hr_admin"]}}
        elif creator_role == "org_admin":
            # Sees only hr_admins in their org
            org_id = current_user.get("organization_id")
            if not org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Your account is not linked to any organization"
                )
            query = {
                "role": "hr_admin",
                "organization_id": org_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        if not include_inactive:
            query["is_active"] = True

        total = await self.db.users.count_documents(query)
        cursor = self.db.users.find(
            query,
            {"hashed_password": 0, "password_reset_otp": 0, "password_reset_otp_expires_at": 0}
        ).skip(skip).limit(limit).sort("created_at", -1)
        users = await cursor.to_list(length=limit)
        for u in users:
            self._serialize(u)
            if creator_role == "superadmin":
                await self._attach_org_name(u)

        return {
            "users": users,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    # ------------------------------------------------------------------
    # Read — single
    # ------------------------------------------------------------------

    async def get_user_by_id(self, user_id: str, current_user: dict) -> dict:
        try:
            user = await self.db.users.find_one(
                {"_id": ObjectId(user_id)},
                {"hashed_password": 0, "password_reset_otp": 0, "password_reset_otp_expires_at": 0}
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        self._enforce_access(current_user, user)
        self._serialize(user)
        if current_user.get("role") == "superadmin":
            await self._attach_org_name(user)
        return user

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_user(self, user_id: str, data: UserUpdateRequest, current_user: dict) -> dict:
        try:
            user = await self.db.users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        self._enforce_access(current_user, user)

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided to update"
            )

        # Check email uniqueness if being changed
        if "email" in update_data and update_data["email"] != user["email"]:
            existing = await self.db.users.find_one({"email": update_data["email"]})
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A user with this email already exists"
                )

        update_data["updated_at"] = datetime.utcnow()

        await self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )

        logger.info(f"Updated user {user_id} by {current_user.get('email')}")

        updated = await self.db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"hashed_password": 0, "password_reset_otp": 0, "password_reset_otp_expires_at": 0}
        )
        return self._serialize(updated)

    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    async def delete_user(self, user_id: str, current_user: dict) -> dict:
        try:
            user = await self.db.users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Prevent self-deletion
        if str(user["_id"]) == str(current_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot delete your own account"
            )

        self._enforce_access(current_user, user)

        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already inactive"
            )

        await self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )

        logger.info(f"Soft deleted user {user_id} by {current_user.get('email')}")
        return {"message": "User deactivated successfully", "user_id": user_id}

    # ------------------------------------------------------------------
    # Access control enforcement (shared by get, update, delete)
    # ------------------------------------------------------------------

    def _enforce_access(self, current_user: dict, target_user: dict) -> None:
        """
        superadmin  → can operate on org_admin and hr_admin
        org_admin   → can only operate on hr_admin within their own organization
        """
        creator_role = current_user.get("role")
        target_role = target_user.get("role")

        if creator_role == "superadmin":
            if target_role not in ["org_admin", "hr_admin"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="superadmin can only manage org_admin and hr_admin users"
                )

        elif creator_role == "org_admin":
            if target_role != "hr_admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="org_admin can only manage hr_admin users"
                )
            # Must be same organization
            if target_user.get("organization_id") != current_user.get("organization_id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only manage users within your own organization"
                )

        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
