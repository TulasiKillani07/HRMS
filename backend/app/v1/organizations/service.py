from datetime import datetime
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.core.security import get_password_hash
from app.utils.helpers import convert_objectid_to_str, paginate_query
from app.utils.notifications import notify_org_admin_created
from app.utils.logger import logger
from app.models.organization import OrganizationModel
from app.models.user import UserModel
from app.v1.organizations.schema import (
    OrganizationCreateRequest,
    OrganizationUpdateRequest
)
import secrets
import string

class OrganizationService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()
    
    def _generate_temp_password(self, length=12):
        """Generate a secure temporary password"""
        # Use default password "Welcome1"
        return "Welcome1"
    
    async def create_organization(self, data: OrganizationCreateRequest):
        """Create a new organization and org admin user"""
        logger.info(f"Creating organization: {data.org_name}")
        
        # Check if organization email already exists
        existing_org = await self.db.organizations.find_one({
            "email": data.email,
            "is_deleted": False
        })
        if existing_org:
            logger.warning(f"Organization email already exists: {data.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization email already exists"
            )
        
        # Check if admin email already exists in users collection
        existing_user = await self.db.users.find_one({
            "email": data.admin_email
        })
        if existing_user:
            logger.warning(f"Admin email already exists: {data.admin_email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin email already exists as a user"
            )
        
        # Generate temporary password for admin
        temp_password = self._generate_temp_password()
        logger.info(f"Generated temporary password for admin: {data.admin_email}")
        
        # Create org admin user using UserModel
        user_model = UserModel(
            email=data.admin_email,
            hashed_password=get_password_hash(temp_password),
            full_name=data.admin_name,
            role="org_admin",
            phone=data.admin_phone,
            is_active=True,
            is_verified=False,
            requires_password_change=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        user_result = await self.db.users.insert_one(user_model.model_dump())
        user_id = str(user_result.inserted_id)
        logger.info(f"Created org admin user with ID: {user_id}")
        
        # Create organization using OrganizationModel
        org_model = OrganizationModel(
            org_name=data.org_name,
            email=data.email,
            emp_count_for_access=data.emp_count_for_access,
            industry=data.industry,
            country=data.country,
            state=data.state,
            admin_name=data.admin_name,
            admin_email=data.admin_email,
            admin_phone=data.admin_phone,
            org_address=data.org_address,
            admin_user_id=user_id,
            status="active",
            is_deleted=False,
            deleted_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        org_result = await self.db.organizations.insert_one(org_model.model_dump())
        org_id = str(org_result.inserted_id)
        logger.info(f"Created organization with ID: {org_id}")
        
        # Update user with organization reference
        await self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"organization_id": org_id, "updated_at": datetime.utcnow()}}
        )
        
        # Send invitation email and notification
        await notify_org_admin_created(
            admin_email=data.admin_email,
            admin_name=data.admin_name,
            admin_phone=data.admin_phone,
            org_name=data.org_name,
            org_email=data.email,
            temp_password=temp_password
        )
        
        # Prepare response
        org_dict = org_model.model_dump()
        org_dict["id"] = org_id  # Map _id to id for response
        org_dict["temp_admin_password"] = temp_password
        org_dict["notification_sent"] = True
        
        # Remove _id from response
        if "_id" in org_dict:
            del org_dict["_id"]
        
        logger.info(f"Organization created successfully: {data.org_name} (ID: {org_id})")
        return org_dict

    async def get_organizations(self, page: int = 1, limit: int = 10, include_deleted: bool = False):
        """Get all organizations with pagination"""
        skip, limit = paginate_query(page, limit)
        
        # Filter for non-deleted organizations unless specified
        filter_query = {} if include_deleted else {"is_deleted": False}
        
        cursor = self.db.organizations.find(filter_query).skip(skip).limit(limit)
        organizations = await cursor.to_list(length=limit)
        
        # Get total count
        total = await self.db.organizations.count_documents(filter_query)
        
        # Convert ObjectId to id
        for org in organizations:
            org["id"] = str(org["_id"])
            del org["_id"]
        
        return {
            "organizations": organizations,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    
    async def get_organization_by_id(self, org_id: str):
        """Get organization by ID"""
        logger.info(f"Fetching organization by ID: {org_id}")
        try:
            org = await self.db.organizations.find_one({
                "_id": ObjectId(org_id),
                "is_deleted": False
            })
        except Exception as e:
            logger.error(f"Invalid organization ID format: {org_id} - {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization ID"
            )
        
        if not org:
            logger.warning(f"Organization not found: {org_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        logger.info(f"Organization found: {org['org_name']}")
        # Map _id to id
        org["id"] = str(org["_id"])
        del org["_id"]
        return org
    
    async def update_organization(self, org_id: str, data: OrganizationUpdateRequest):
        """Update organization details"""
        logger.info(f"Updating organization: {org_id}")
        
        # Check if organization exists
        org = await self.get_organization_by_id(org_id)
        
        # Get only provided fields
        update_data = data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Check if email is being updated and already exists
        if "email" in update_data and update_data["email"] != org["email"]:
            existing = await self.db.organizations.find_one({
                "email": update_data["email"],
                "is_deleted": False,
                "_id": {"$ne": ObjectId(org_id)}
            })
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization email already exists"
                )
        
        # If admin email is being updated, update user as well
        if "admin_email" in update_data and update_data["admin_email"] != org["admin_email"]:
            existing_user = await self.db.users.find_one({
                "email": update_data["admin_email"]
            })
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admin email already exists as a user"
                )
            
            # Update user email
            if org.get("admin_user_id"):
                await self.db.users.update_one(
                    {"_id": ObjectId(org["admin_user_id"])},
                    {"$set": {"email": update_data["admin_email"], "updated_at": datetime.utcnow()}}
                )
        
        # Update admin name in user collection if changed
        if "admin_name" in update_data and org.get("admin_user_id"):
            await self.db.users.update_one(
                {"_id": ObjectId(org["admin_user_id"])},
                {"$set": {"full_name": update_data["admin_name"], "updated_at": datetime.utcnow()}}
            )
        
        # Update admin phone in user collection if changed
        if "admin_phone" in update_data and org.get("admin_user_id"):
            await self.db.users.update_one(
                {"_id": ObjectId(org["admin_user_id"])},
                {"$set": {"phone": update_data["admin_phone"], "updated_at": datetime.utcnow()}}
            )
        
        update_data["updated_at"] = datetime.utcnow()
        
        # Update organization
        await self.db.organizations.update_one(
            {"_id": ObjectId(org_id)},
            {"$set": update_data}
        )
        
        # Fetch updated organization
        updated_org = await self.get_organization_by_id(org_id)
        
        logger.info(f"Organization updated successfully: {org_id}")
        return updated_org
    
    async def soft_delete_organization(self, org_id: str):
        """Soft delete organization (set is_deleted=True and status=inactive)"""
        logger.info(f"Soft deleting organization: {org_id}")
        
        # Check if organization exists
        org = await self.get_organization_by_id(org_id)
        
        # Soft delete
        await self.db.organizations.update_one(
            {"_id": ObjectId(org_id)},
            {
                "$set": {
                    "is_deleted": True,
                    "status": "inactive",
                    "deleted_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Deactivate admin user
        if org.get("admin_user_id"):
            await self.db.users.update_one(
                {"_id": ObjectId(org["admin_user_id"])},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            logger.info(f"Deactivated admin user: {org['admin_user_id']}")
        
        logger.info(f"Organization soft deleted successfully: {org_id}")
        return {"message": "Organization deleted successfully"}
