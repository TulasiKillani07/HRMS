from datetime import datetime
from fastapi import HTTPException, status
from bson import ObjectId
from typing import Optional
import uuid

from app.database import get_database
from app.utils.helpers import paginate_query
from app.utils.logger import logger
from app.models.performance import (
    PerformanceCycleModel,
    PerformanceOKRModel,
    PerformanceReviewModel,
    KeyResultEntry,
    ObjectiveEntry
)
from app.v1.performance.schema import (
    CycleCreateRequest,
    CycleUpdateRequest,
    OKRCreateRequest,
    OKRUpdateRequest,
    ReviewSubmitRequest
)


class PerformanceService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()
    
    # -----------------------------------------------------------------------
    # Helper methods
    # -----------------------------------------------------------------------
    
    def _serialize(self, doc: dict) -> dict:
        """Convert MongoDB _id to id"""
        if doc and "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
        return doc
    
    def _get_org_id(self, current_user: dict, explicit_org_id: str = None) -> str:
        """Get organization ID from user or explicit parameter"""
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
                detail="User not linked to any organization"
            )
        return org_id

    
    def _calculate_kr_progress(self, current: float, target: float) -> float:
        """Calculate key result progress percentage"""
        if target == 0:
            return 0.0
        progress = (current / target) * 100
        return min(progress, 100.0)  # Cap at 100%
    
    def _calculate_objective_progress(self, key_results: list) -> float:
        """Calculate objective progress as average of key results"""
        if not key_results:
            return 0.0
        total = sum(kr.get("progress", 0) for kr in key_results)
        return total / len(key_results)
    
    def _calculate_overall_progress(self, objectives: list) -> float:
        """Calculate overall OKR progress as weighted average of objectives"""
        if not objectives:
            return 0.0
        
        total_weight = sum(obj.get("weight", 0) for obj in objectives)
        if total_weight == 0:
            return 0.0
        
        weighted_sum = sum(
            obj.get("progress", 0) * obj.get("weight", 0)
            for obj in objectives
        )
        return weighted_sum / total_weight
    
    def _calculate_final_rating(
        self,
        self_rating: Optional[float],
        manager_rating: Optional[float],
        self_weight: float = 0.3,
        manager_weight: float = 0.7
    ) -> Optional[float]:
        """Calculate final rating as weighted average"""
        if self_rating is None or manager_rating is None:
            return None
        return (self_rating * self_weight) + (manager_rating * manager_weight)
    
    # -----------------------------------------------------------------------
    # Performance Cycles
    # -----------------------------------------------------------------------
    
    async def create_cycle(
        self,
        data: CycleCreateRequest,
        current_user: dict
    ) -> dict:
        """Create a new performance cycle"""
        org_id = self._get_org_id(current_user)
        
        cycle_model = PerformanceCycleModel(
            organization_id=org_id,
            name=data.name,
            start_date=data.start_date,
            end_date=data.end_date,
            status="active",
            created_by=str(current_user["_id"]),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await self.db.performance_cycles.insert_one(cycle_model.model_dump())
        
        cycle_dict = cycle_model.model_dump()
        cycle_dict["id"] = str(result.inserted_id)
        
        logger.info(f"Performance cycle '{data.name}' created for org {org_id}")
        return self._serialize(cycle_dict)
    
    async def get_cycles(
        self,
        current_user: dict,
        status_filter: Optional[str] = None
    ) -> dict:
        """Get all cycles for organization"""
        org_id = self._get_org_id(current_user)
        
        query = {"organization_id": org_id}
        if status_filter:
            query["status"] = status_filter
        
        cursor = self.db.performance_cycles.find(query).sort("created_at", -1)
        cycles = await cursor.to_list(length=None)
        
        for cycle in cycles:
            self._serialize(cycle)
        
        return {"cycles": cycles, "total": len(cycles)}
    
    async def update_cycle(
        self,
        cycle_id: str,
        data: CycleUpdateRequest,
        current_user: dict
    ) -> dict:
        """Update a performance cycle"""
        org_id = self._get_org_id(current_user)
        
        try:
            cycle = await self.db.performance_cycles.find_one({
                "_id": ObjectId(cycle_id),
                "organization_id": org_id
            })
        except:
            raise HTTPException(status_code=400, detail="Invalid cycle ID")
        
        if not cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")
        
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_data["updated_at"] = datetime.utcnow()
        
        await self.db.performance_cycles.update_one(
            {"_id": ObjectId(cycle_id)},
            {"$set": update_data}
        )
        
        updated = await self.db.performance_cycles.find_one({"_id": ObjectId(cycle_id)})
        logger.info(f"Cycle {cycle_id} updated to status: {update_data.get('status', 'N/A')}")
        return self._serialize(updated)

    
    # -----------------------------------------------------------------------
    # OKRs
    # -----------------------------------------------------------------------
    
    async def create_okr(
        self,
        data: OKRCreateRequest,
        current_user: dict
    ) -> dict:
        """Create OKR for employee"""
        org_id = self._get_org_id(current_user)
        
        # Determine employee_id
        role = current_user.get("role")
        if role == "employee":
            employee_id = str(current_user["_id"])
        else:
            if not data.employee_id:
                raise HTTPException(status_code=400, detail="HR/admin must supply employee_id")
            employee_id = data.employee_id
        
        # Get employee details
        try:
            employee = await self.db.employees.find_one({
                "_id": ObjectId(employee_id),
                "organization_id": org_id,
                "is_deleted": False
            })
        except:
            raise HTTPException(status_code=400, detail="Invalid employee ID")
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Verify cycle exists
        try:
            cycle = await self.db.performance_cycles.find_one({
                "_id": ObjectId(data.cycle_id),
                "organization_id": org_id
            })
        except:
            raise HTTPException(status_code=400, detail="Invalid cycle ID")
        
        if not cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")
        
        # Build objectives with UUIDs and progress calculations
        objectives = []
        for obj_req in data.objectives:
            key_results = []
            for kr_req in obj_req.key_results:
                progress = self._calculate_kr_progress(kr_req.current, kr_req.target)
                kr = KeyResultEntry(
                    id=str(uuid.uuid4()),
                    title=kr_req.title,
                    target=kr_req.target,
                    current=kr_req.current,
                    unit=kr_req.unit,
                    progress=progress
                )
                key_results.append(kr)
            
            obj_progress = self._calculate_objective_progress([kr.model_dump() for kr in key_results])
            obj = ObjectiveEntry(
                id=str(uuid.uuid4()),
                title=obj_req.title,
                description=obj_req.description,
                weight=obj_req.weight,
                key_results=key_results,
                progress=obj_progress
            )
            objectives.append(obj)
        
        overall_progress = self._calculate_overall_progress([obj.model_dump() for obj in objectives])
        
        okr_model = PerformanceOKRModel(
            organization_id=org_id,
            cycle_id=data.cycle_id,
            employee_id=employee_id,
            employee_name=f"{employee['first_name']} {employee['last_name']}",
            department=employee.get("department", "N/A"),
            objectives=objectives,
            overall_progress=overall_progress,
            status="draft",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await self.db.performance_okrs.insert_one(okr_model.model_dump())
        okr_dict = okr_model.model_dump()
        okr_dict["id"] = str(result.inserted_id)
        
        logger.info(f"OKR created for employee {employee_id} in cycle {data.cycle_id}")
        return self._serialize(okr_dict)
    
    async def get_okrs(
        self,
        current_user: dict,
        page: int,
        limit: int,
        cycle_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        department: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> dict:
        """List OKRs with filters"""
        org_id = self._get_org_id(current_user)
        role = current_user.get("role")
        
        query = {"organization_id": org_id}
        
        # Employee can only see their own
        if role == "employee":
            query["employee_id"] = str(current_user["_id"])
        elif employee_id:
            query["employee_id"] = employee_id
        
        if cycle_id:
            query["cycle_id"] = cycle_id
        if department:
            query["department"] = {"$regex": department, "$options": "i"}
        if status_filter:
            query["status"] = status_filter
        
        skip, limit = paginate_query(page, limit)
        total = await self.db.performance_okrs.count_documents(query)
        
        cursor = self.db.performance_okrs.find(query).skip(skip).limit(limit).sort("created_at", -1)
        okrs = await cursor.to_list(length=limit)
        
        for okr in okrs:
            self._serialize(okr)
            okr["objectives_count"] = len(okr.get("objectives", []))
            # Get cycle name
            if okr.get("cycle_id"):
                cycle = await self.db.performance_cycles.find_one({"_id": ObjectId(okr["cycle_id"])})
                okr["cycle_name"] = cycle["name"] if cycle else "N/A"
        
        return {
            "okrs": okrs,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    
    async def get_okr_by_id(
        self,
        okr_id: str,
        current_user: dict
    ) -> dict:
        """Get full OKR details"""
        org_id = self._get_org_id(current_user)
        role = current_user.get("role")
        
        try:
            query = {"_id": ObjectId(okr_id), "organization_id": org_id}
            
            # Employee can only see their own
            if role == "employee":
                query["employee_id"] = str(current_user["_id"])
            
            okr = await self.db.performance_okrs.find_one(query)
        except:
            raise HTTPException(status_code=400, detail="Invalid OKR ID")
        
        if not okr:
            raise HTTPException(status_code=404, detail="OKR not found")
        
        return self._serialize(okr)
    
    async def update_okr(
        self,
        okr_id: str,
        data: OKRUpdateRequest,
        current_user: dict
    ) -> dict:
        """Update OKR progress or objectives"""
        org_id = self._get_org_id(current_user)
        role = current_user.get("role")
        
        try:
            query = {"_id": ObjectId(okr_id), "organization_id": org_id}
            
            # Employee can only update their own
            if role == "employee":
                query["employee_id"] = str(current_user["_id"])
            
            okr = await self.db.performance_okrs.find_one(query)
        except:
            raise HTTPException(status_code=400, detail="Invalid OKR ID")
        
        if not okr:
            raise HTTPException(status_code=404, detail="OKR not found")
        
        update_data = {}
        
        # Update objectives if provided
        if data.objectives:
            objectives = okr.get("objectives", [])
            
            for obj_update in data.objectives:
                if obj_update.id:
                    # Update existing objective
                    for obj in objectives:
                        if obj["id"] == obj_update.id:
                            if obj_update.title:
                                obj["title"] = obj_update.title
                            if obj_update.description is not None:
                                obj["description"] = obj_update.description
                            if obj_update.weight:
                                obj["weight"] = obj_update.weight
                            
                            # Update key results
                            if obj_update.key_results:
                                for kr_update in obj_update.key_results:
                                    for kr in obj["key_results"]:
                                        if kr["id"] == kr_update.id:
                                            if kr_update.current is not None:
                                                kr["current"] = kr_update.current
                                            if kr_update.title:
                                                kr["title"] = kr_update.title
                                            if kr_update.target:
                                                kr["target"] = kr_update.target
                                            if kr_update.unit:
                                                kr["unit"] = kr_update.unit
                                            # Recalculate progress
                                            kr["progress"] = self._calculate_kr_progress(kr["current"], kr["target"])
                            
                            # Recalculate objective progress
                            obj["progress"] = self._calculate_objective_progress(obj["key_results"])
                            break
                else:
                    # Add new objective
                    new_obj = {
                        "id": str(uuid.uuid4()),
                        "title": obj_update.title,
                        "description": obj_update.description,
                        "weight": obj_update.weight,
                        "key_results": [],
                        "progress": 0.0
                    }
                    objectives.append(new_obj)
            
            # Recalculate overall progress
            overall_progress = self._calculate_overall_progress(objectives)
            update_data["objectives"] = objectives
            update_data["overall_progress"] = overall_progress
        
        if data.status:
            update_data["status"] = data.status
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_data["updated_at"] = datetime.utcnow()
        
        await self.db.performance_okrs.update_one(
            {"_id": ObjectId(okr_id)},
            {"$set": update_data}
        )
        
        updated = await self.db.performance_okrs.find_one({"_id": ObjectId(okr_id)})
        logger.info(f"OKR {okr_id} updated, progress: {update_data.get('overall_progress', 'N/A')}")
        return self._serialize(updated)
    
    async def delete_okr(
        self,
        okr_id: str,
        current_user: dict
    ) -> dict:
        """Delete OKR (draft only)"""
        org_id = self._get_org_id(current_user)
        
        try:
            okr = await self.db.performance_okrs.find_one({
                "_id": ObjectId(okr_id),
                "organization_id": org_id
            })
        except:
            raise HTTPException(status_code=400, detail="Invalid OKR ID")
        
        if not okr:
            raise HTTPException(status_code=404, detail="OKR not found")
        
        if okr.get("status") != "draft":
            raise HTTPException(
                status_code=400,
                detail="Only draft OKRs can be deleted"
            )
        
        await self.db.performance_okrs.delete_one({"_id": ObjectId(okr_id)})
        logger.info(f"OKR {okr_id} deleted")
        return {"message": "OKR deleted successfully"}

    
    # -----------------------------------------------------------------------
    # Performance Reviews
    # -----------------------------------------------------------------------
    
    async def submit_review(
        self,
        data: ReviewSubmitRequest,
        current_user: dict
    ) -> dict:
        """Submit self-review or manager review"""
        org_id = self._get_org_id(current_user)
        role = current_user.get("role")
        
        # Determine employee_id and review type
        if role == "employee":
            # Self-review
            employee_id = str(current_user["_id"])
            if not data.self_rating:
                raise HTTPException(status_code=400, detail="Employee must provide self_rating")
        else:
            # Manager review
            if not data.employee_id:
                raise HTTPException(status_code=400, detail="HR/admin must supply employee_id")
            if not data.manager_rating:
                raise HTTPException(status_code=400, detail="Manager must provide manager_rating")
            employee_id = data.employee_id
        
        # Get employee details
        try:
            employee = await self.db.employees.find_one({
                "_id": ObjectId(employee_id),
                "organization_id": org_id,
                "is_deleted": False
            })
        except:
            raise HTTPException(status_code=400, detail="Invalid employee ID")
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Verify cycle exists
        try:
            cycle = await self.db.performance_cycles.find_one({
                "_id": ObjectId(data.cycle_id),
                "organization_id": org_id
            })
        except:
            raise HTTPException(status_code=400, detail="Invalid cycle ID")
        
        if not cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")
        
        # Check if review already exists
        existing = await self.db.performance_reviews.find_one({
            "organization_id": org_id,
            "cycle_id": data.cycle_id,
            "employee_id": employee_id
        })
        
        if existing:
            # Update existing review
            update_data = {}
            
            if role == "employee":
                update_data["self_rating"] = data.self_rating
                update_data["self_comments"] = data.self_comments
                update_data["status"] = "self_reviewed"
            else:
                update_data["manager_id"] = str(current_user["_id"])
                update_data["manager_rating"] = data.manager_rating
                update_data["manager_comments"] = data.manager_comments
                update_data["status"] = "manager_reviewed"
            
            if data.competencies:
                update_data["competencies"] = data.competencies.model_dump()
            
            # Recalculate final rating if both ratings exist
            self_rating = update_data.get("self_rating", existing.get("self_rating"))
            manager_rating = update_data.get("manager_rating", existing.get("manager_rating"))
            
            if self_rating and manager_rating:
                update_data["final_rating"] = self._calculate_final_rating(self_rating, manager_rating)
            
            update_data["updated_at"] = datetime.utcnow()
            
            await self.db.performance_reviews.update_one(
                {"_id": existing["_id"]},
                {"$set": update_data}
            )
            
            review = await self.db.performance_reviews.find_one({"_id": existing["_id"]})
            logger.info(f"Review updated for employee {employee_id}, status: {update_data.get('status')}")
            return self._serialize(review)
        
        else:
            # Create new review
            review_model = PerformanceReviewModel(
                organization_id=org_id,
                cycle_id=data.cycle_id,
                employee_id=employee_id,
                employee_name=f"{employee['first_name']} {employee['last_name']}",
                self_rating=data.self_rating,
                self_comments=data.self_comments,
                manager_id=str(current_user["_id"]) if role != "employee" else None,
                manager_rating=data.manager_rating,
                manager_comments=data.manager_comments,
                competencies=data.competencies.model_dump() if data.competencies else None,
                status="self_reviewed" if role == "employee" else "manager_reviewed",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Calculate final rating if both exist
            if data.self_rating and data.manager_rating:
                review_model.final_rating = self._calculate_final_rating(
                    data.self_rating,
                    data.manager_rating
                )
            
            result = await self.db.performance_reviews.insert_one(review_model.model_dump())
            review_dict = review_model.model_dump()
            review_dict["id"] = str(result.inserted_id)
            
            logger.info(f"Review created for employee {employee_id}")
            return self._serialize(review_dict)

    
    async def get_reviews(
        self,
        current_user: dict,
        cycle_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> dict:
        """List reviews with filters"""
        org_id = self._get_org_id(current_user)
        role = current_user.get("role")
        
        query = {"organization_id": org_id}
        
        # Employee can only see their own
        if role == "employee":
            query["employee_id"] = str(current_user["_id"])
        elif employee_id:
            query["employee_id"] = employee_id
        
        if cycle_id:
            query["cycle_id"] = cycle_id
        if status_filter:
            query["status"] = status_filter
        
        cursor = self.db.performance_reviews.find(query).sort("created_at", -1)
        reviews = await cursor.to_list(length=None)
        
        # Get employee departments
        for review in reviews:
            self._serialize(review)
            emp = await self.db.employees.find_one({"_id": ObjectId(review["employee_id"])})
            review["department"] = emp.get("department", "N/A") if emp else "N/A"
        
        return {"reviews": reviews, "total": len(reviews)}
    
    async def get_review_by_id(
        self,
        review_id: str,
        current_user: dict
    ) -> dict:
        """Get full review details"""
        org_id = self._get_org_id(current_user)
        role = current_user.get("role")
        
        try:
            query = {"_id": ObjectId(review_id), "organization_id": org_id}
            
            # Employee can only see their own
            if role == "employee":
                query["employee_id"] = str(current_user["_id"])
            
            review = await self.db.performance_reviews.find_one(query)
        except:
            raise HTTPException(status_code=400, detail="Invalid review ID")
        
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")
        
        return self._serialize(review)

    
    # -----------------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------------
    
    async def get_leaderboard(
        self,
        current_user: dict,
        cycle_id: Optional[str],
        department: Optional[str],
        limit: int = 10
    ) -> dict:
        """Get top performers leaderboard"""
        org_id = self._get_org_id(current_user)
        
        query = {"organization_id": org_id}
        if cycle_id:
            query["cycle_id"] = cycle_id
        
        # Get all reviews with final ratings
        reviews = await self.db.performance_reviews.find(query).to_list(length=None)
        
        # Get OKRs for progress data
        okr_map = {}
        okrs = await self.db.performance_okrs.find(query).to_list(length=None)
        for okr in okrs:
            okr_map[okr["employee_id"]] = okr.get("overall_progress", 0)
        
        # Build leaderboard
        leaderboard = []
        for review in reviews:
            if review.get("final_rating") is None:
                continue
            
            emp_id = review["employee_id"]
            emp = await self.db.employees.find_one({"_id": ObjectId(emp_id)})
            if not emp:
                continue
            
            dept = emp.get("department", "N/A")
            
            # Filter by department if specified
            if department and department.lower() not in dept.lower():
                continue
            
            leaderboard.append({
                "employee_id": emp_id,
                "employee_name": review["employee_name"],
                "department": dept,
                "final_rating": review["final_rating"],
                "okr_progress": okr_map.get(emp_id, 0)
            })
        
        # Sort by final_rating descending
        leaderboard.sort(key=lambda x: x["final_rating"], reverse=True)
        
        # Add rank and limit
        for idx, entry in enumerate(leaderboard[:limit], 1):
            entry["rank"] = idx
        
        return {"leaderboard": leaderboard[:limit]}

    
    async def get_analytics(
        self,
        current_user: dict,
        cycle_id: Optional[str]
    ) -> dict:
        """Get performance analytics"""
        org_id = self._get_org_id(current_user)
        
        query = {"organization_id": org_id}
        if cycle_id:
            query["cycle_id"] = cycle_id
        
        reviews = await self.db.performance_reviews.find(query).to_list(length=None)
        
        # Distribution
        exceeds = 0  # >= 4.5
        meets = 0     # 3.0 - 4.49
        below = 0     # < 3.0
        
        total_rating = 0.0
        reviewed_count = 0
        
        dept_totals = {}
        dept_counts = {}
        
        for review in reviews:
            rating = review.get("final_rating")
            if rating is None:
                continue
            
            reviewed_count += 1
            total_rating += rating
            
            if rating >= 4.5:
                exceeds += 1
            elif rating >= 3.0:
                meets += 1
            else:
                below += 1
            
            # Department averages
            emp = await self.db.employees.find_one({"_id": ObjectId(review["employee_id"])})
            if emp:
                dept = emp.get("department", "N/A")
                dept_totals[dept] = dept_totals.get(dept, 0) + rating
                dept_counts[dept] = dept_counts.get(dept, 0) + 1
        
        # Calculate department averages
        department_avg = {}
        for dept, total in dept_totals.items():
            department_avg[dept] = round(total / dept_counts[dept], 2)
        
        avg_rating = round(total_rating / reviewed_count, 2) if reviewed_count > 0 else 0
        
        return {
            "distribution": {
                "exceeds": exceeds,
                "meets": meets,
                "below": below
            },
            "department_avg": department_avg,
            "avg_rating": avg_rating,
            "total_reviewed": reviewed_count
        }
