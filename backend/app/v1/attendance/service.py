from datetime import datetime
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.attendance import (
    OfficeLocationModel, AttendanceConfigModel,
    AttendanceModel, RegularizationModel, haversine_distance
)
from app.utils.helpers import paginate_query
from app.utils.logger import logger


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


DEFAULT_CONFIG = {
    "shift_start": "09:00", "shift_end": "18:00",
    "grace_period_minutes": 15,
    "min_hours_full_day": 8.0, "min_hours_half_day": 4.0,
    "location_required_for_checkout": False,
    "photo_required": True, "weekend_days": [0, 6],
    "auto_mark_absent_after": "11:00"
}


class AttendanceService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    def _org_id(self, current_user: dict, explicit: str = None) -> str:
        role = current_user.get("role")
        if role == "superadmin":
            if not explicit:
                raise HTTPException(status_code=400, detail="superadmin must supply organization_id")
            return explicit
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(status_code=400, detail="No organization linked")
        return org_id

    async def _get_employee(self, current_user: dict):
        user_id = str(current_user["_id"])
        emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee record not found")
        return emp

    async def _get_config(self, org_id: str) -> dict:
        config = await self.db.attendance_config.find_one({"organization_id": org_id})
        if not config:
            return DEFAULT_CONFIG
        return config

    # ==================================================================
    # OFFICE LOCATIONS CRUD
    # ==================================================================

    async def create_location(self, data, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        loc = OfficeLocationModel(
            organization_id=org_id, name=data.name, address=data.address,
            latitude=data.latitude, longitude=data.longitude,
            radius_meters=data.radius_meters, is_active=data.is_active,
            created_by=str(current_user["_id"]),
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        result = await self.db.office_locations.insert_one(loc.model_dump())
        d = loc.model_dump()
        d["_id"] = result.inserted_id
        logger.info(f"Office location '{data.name}' created for org {org_id}")
        return _serialize(d)

    async def get_locations(self, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        locs = await self.db.office_locations.find({"organization_id": org_id}).to_list(50)
        for l in locs:
            _serialize(l)
        return {"locations": locs, "total": len(locs)}

    async def update_location(self, location_id: str, data, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(location_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid location ID")
        loc = await self.db.office_locations.find_one({"_id": obj_id, "organization_id": org_id})
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        update = data.model_dump(exclude_unset=True)
        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")
        update["updated_at"] = datetime.utcnow()
        await self.db.office_locations.update_one({"_id": obj_id}, {"$set": update})
        updated = await self.db.office_locations.find_one({"_id": obj_id})
        return _serialize(updated)

    async def delete_location(self, location_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(location_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid location ID")
        loc = await self.db.office_locations.find_one({"_id": obj_id, "organization_id": org_id})
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        await self.db.office_locations.delete_one({"_id": obj_id})
        return {"message": f"Location '{loc['name']}' deleted"}

    # ==================================================================
    # CHECK-IN
    # ==================================================================

    async def check_in(self, data, current_user: dict) -> dict:
        emp = await self._get_employee(current_user)
        emp_id = str(emp["_id"])
        org_id = emp.get("organization_id", "")
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # Prevent duplicate
        existing = await self.db.attendance.find_one({"employee_id": emp_id, "date": today})
        if existing and existing.get("check_in"):
            raise HTTPException(status_code=400, detail="Already checked in today")

        # Validate location against office locations
        locations = await self.db.office_locations.find(
            {"organization_id": org_id, "is_active": True}
        ).to_list(50)

        matched_office = None
        min_distance = None
        nearest_office = None

        for loc in locations:
            dist = haversine_distance(data.latitude, data.longitude, loc["latitude"], loc["longitude"])
            if min_distance is None or dist < min_distance:
                min_distance = dist
                nearest_office = loc["name"]
            if dist <= loc["radius_meters"]:
                matched_office = loc["name"]
                min_distance = dist
                break

        if locations and not matched_office:
            dist_km = round(min_distance / 1000, 2) if min_distance else "unknown"
            raise HTTPException(
                status_code=403,
                detail=f"You are not within any registered office location. Nearest: {nearest_office} (distance: {dist_km} km, allowed: {locations[0]['radius_meters']}m)"
            )

        # Check if late
        config = await self._get_config(org_id)
        now = datetime.utcnow()
        shift_start = datetime.strptime(f"{today} {config.get('shift_start', '09:00')}", "%Y-%m-%d %H:%M")
        grace = config.get("grace_period_minutes", 15)
        allowed_time = shift_start.replace(minute=shift_start.minute + grace) if grace else shift_start

        is_late = now > allowed_time
        late_by = int((now - shift_start).total_seconds() / 60) if is_late else 0

        check_in_location = {
            "latitude": data.latitude,
            "longitude": data.longitude,
            "matched_office": matched_office or "No office validation",
            "distance_meters": round(min_distance) if min_distance else None
        }

        attendance = AttendanceModel(
            organization_id=org_id, employee_id=emp_id,
            employee_name=f"{emp['first_name']} {emp['last_name']}",
            department=emp.get("department", ""), date=today,
            check_in=now, check_in_location=check_in_location,
            check_in_photo=data.photo_url,
            status="present", is_late=is_late, late_by_minutes=late_by,
            source="self", created_at=now, updated_at=now
        )

        result = await self.db.attendance.insert_one(attendance.model_dump())
        d = attendance.model_dump()
        d["_id"] = result.inserted_id
        logger.info(f"Check-in: {emp['first_name']} at {matched_office or 'unvalidated'}, late={is_late}")
        return _serialize(d)

    # ==================================================================
    # CHECK-OUT
    # ==================================================================

    async def check_out(self, data, current_user: dict) -> dict:
        emp = await self._get_employee(current_user)
        emp_id = str(emp["_id"])
        org_id = emp.get("organization_id", "")
        today = datetime.utcnow().strftime("%Y-%m-%d")

        existing = await self.db.attendance.find_one({"employee_id": emp_id, "date": today})
        if not existing or not existing.get("check_in"):
            raise HTTPException(status_code=400, detail="Not checked in today. Check in first.")
        if existing.get("check_out"):
            raise HTTPException(status_code=400, detail="Already checked out today")

        now = datetime.utcnow()
        config = await self._get_config(org_id)

        # Optional location validation for checkout
        check_out_location = None
        if data.latitude and data.longitude:
            check_out_location = {"latitude": data.latitude, "longitude": data.longitude}

        # Calculate hours
        total_hours = round((now - existing["check_in"]).total_seconds() / 3600, 2)

        # Determine status
        min_full = config.get("min_hours_full_day", 8)
        min_half = config.get("min_hours_half_day", 4)
        att_status = "present"
        if total_hours < min_half:
            att_status = "half_day"
        elif total_hours < min_full:
            att_status = "half_day"

        # Keep late status if was late
        if existing.get("is_late"):
            att_status = "late" if total_hours >= min_full else att_status

        await self.db.attendance.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "check_out": now, "check_out_location": check_out_location,
                "check_out_photo": data.photo_url,
                "total_hours": total_hours, "status": att_status, "updated_at": now
            }}
        )

        logger.info(f"Check-out: {emp['first_name']} | {total_hours}h | status={att_status}")
        updated = await self.db.attendance.find_one({"_id": existing["_id"]})
        return _serialize(updated)

    # ==================================================================
    # TODAY / HISTORY / LIST
    # ==================================================================

    async def get_today(self, current_user: dict, employee_id: str = None) -> dict:
        if current_user.get("role") == "employee":
            emp = await self._get_employee(current_user)
            emp_id = str(emp["_id"])
        else:
            if not employee_id:
                raise HTTPException(status_code=400, detail="employee_id required for HR")
            emp_id = employee_id

        today = datetime.utcnow().strftime("%Y-%m-%d")
        record = await self.db.attendance.find_one({"employee_id": emp_id, "date": today})
        if not record:
            return {"date": today, "status": "not_checked_in", "check_in": None, "check_out": None, "total_hours": None}
        return _serialize(record)

    async def get_my_history(self, current_user: dict, page: int = 1, limit: int = 31,
                             month: int = None, year: int = None, employee_id: str = None) -> dict:
        role = current_user.get("role")
        if role == "employee":
            emp = await self._get_employee(current_user)
            emp_id = str(emp["_id"])
        else:
            if not employee_id:
                raise HTTPException(status_code=400, detail="employee_id required for HR")
            emp_id = employee_id

        skip, limit = paginate_query(page, limit)
        query = {"employee_id": emp_id}
        if year and month:
            query["date"] = {"$regex": f"^{year}-{month:02d}"}
        elif year:
            query["date"] = {"$regex": f"^{year}"}
        total = await self.db.attendance.count_documents(query)
        records = await self.db.attendance.find(query).skip(skip).limit(limit).sort("date", -1).to_list(limit)
        for r in records:
            _serialize(r)
        return {"records": records, "total": total, "page": page, "limit": limit, "pages": (total + limit - 1) // limit}

    async def get_attendance_list(self, current_user: dict, page: int = 1, limit: int = 50,
                                  date_filter: str = None, from_date: str = None, to_date: str = None,
                                  employee_id: str = None, department: str = None,
                                  status_filter: str = None, org_id_param: str = None) -> dict:
        role = current_user.get("role")
        org_id = self._org_id(current_user, org_id_param)
        skip, limit = paginate_query(page, limit)
        query = {"organization_id": org_id}

        if role == "employee":
            emp = await self._get_employee(current_user)
            query["employee_id"] = str(emp["_id"])
        elif employee_id:
            query["employee_id"] = employee_id

        if date_filter:
            query["date"] = date_filter
        elif from_date and to_date:
            query["date"] = {"$gte": from_date, "$lte": to_date}
        elif from_date:
            query["date"] = {"$gte": from_date}
        elif to_date:
            query["date"] = {"$lte": to_date}

        if department:
            query["department"] = {"$regex": department, "$options": "i"}
        if status_filter:
            query["status"] = status_filter

        total = await self.db.attendance.count_documents(query)
        records = await self.db.attendance.find(query).skip(skip).limit(limit).sort("date", -1).to_list(limit)
        for r in records:
            _serialize(r)
        return {"records": records, "total": total, "page": page, "limit": limit, "pages": (total + limit - 1) // limit}

    # ==================================================================
    # HR: MARK, EDIT, SUMMARY
    # ==================================================================

    async def mark_attendance(self, data, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            emp = await self.db.employees.find_one({"_id": ObjectId(data.employee_id), "organization_id": org_id, "is_deleted": False})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid employee_id")
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        emp_id = str(emp["_id"])
        existing = await self.db.attendance.find_one({"employee_id": emp_id, "date": data.date})
        now = datetime.utcnow()

        check_in = datetime.strptime(f"{data.date} {data.check_in}", "%Y-%m-%d %H:%M") if data.check_in else None
        check_out = datetime.strptime(f"{data.date} {data.check_out}", "%Y-%m-%d %H:%M") if data.check_out else None
        total_hours = round((check_out - check_in).total_seconds() / 3600, 2) if check_in and check_out else None

        if existing:
            await self.db.attendance.update_one({"_id": existing["_id"]}, {"$set": {
                "check_in": check_in, "check_out": check_out, "total_hours": total_hours,
                "status": data.status, "source": "hr_manual",
                "marked_by": str(current_user["_id"]),
                "marked_by_name": current_user.get("full_name", current_user.get("email", "")),
                "notes": data.reason, "updated_at": now
            }})
            updated = await self.db.attendance.find_one({"_id": existing["_id"]})
            return _serialize(updated)

        att = AttendanceModel(
            organization_id=org_id, employee_id=emp_id,
            employee_name=f"{emp['first_name']} {emp['last_name']}",
            department=emp.get("department", ""), date=data.date,
            check_in=check_in, check_out=check_out, total_hours=total_hours,
            status=data.status, source="hr_manual",
            marked_by=str(current_user["_id"]),
            marked_by_name=current_user.get("full_name", current_user.get("email", "")),
            notes=data.reason, created_at=now, updated_at=now
        )
        result = await self.db.attendance.insert_one(att.model_dump())
        d = att.model_dump(); d["_id"] = result.inserted_id
        logger.info(f"HR marked attendance for {emp['first_name']} on {data.date}")
        return _serialize(d)

    async def update_attendance(self, attendance_id: str, data, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(attendance_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid attendance ID")
        record = await self.db.attendance.find_one({"_id": obj_id, "organization_id": org_id})
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        update = data.model_dump(exclude_unset=True)
        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")

        if "check_in" in update and update["check_in"]:
            update["check_in"] = datetime.strptime(f"{record['date']} {update['check_in']}", "%Y-%m-%d %H:%M")
        if "check_out" in update and update["check_out"]:
            update["check_out"] = datetime.strptime(f"{record['date']} {update['check_out']}", "%Y-%m-%d %H:%M")

        cin = update.get("check_in", record.get("check_in"))
        cout = update.get("check_out", record.get("check_out"))
        if cin and cout:
            update["total_hours"] = round((cout - cin).total_seconds() / 3600, 2)

        update["updated_at"] = datetime.utcnow()
        await self.db.attendance.update_one({"_id": obj_id}, {"$set": update})
        updated = await self.db.attendance.find_one({"_id": obj_id})
        return _serialize(updated)

    async def get_summary(self, current_user: dict, month: int = None, year: int = None,
                          department: str = None, employee_id: str = None, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        if not year: year = datetime.utcnow().year
        if not month: month = datetime.utcnow().month
        month_str = f"{year}-{month:02d}"

        match = {"organization_id": org_id, "date": {"$regex": f"^{month_str}"}}
        if department: match["department"] = {"$regex": department, "$options": "i"}
        if employee_id: match["employee_id"] = employee_id

        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": {"employee_id": "$employee_id", "employee_name": "$employee_name", "department": "$department"},
                "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}},
                "absent": {"$sum": {"$cond": [{"$eq": ["$status", "absent"]}, 1, 0]}},
                "half_day": {"$sum": {"$cond": [{"$eq": ["$status", "half_day"]}, 1, 0]}},
                "late": {"$sum": {"$cond": [{"$eq": ["$status", "late"]}, 1, 0]}},
                "on_leave": {"$sum": {"$cond": [{"$eq": ["$status", "on_leave"]}, 1, 0]}},
                "late_arrivals": {"$sum": {"$cond": ["$is_late", 1, 0]}},
                "total_hours": {"$sum": {"$ifNull": ["$total_hours", 0]}},
                "total_days": {"$sum": 1}
            }},
            {"$sort": {"_id.employee_name": 1}}
        ]
        results = await self.db.attendance.aggregate(pipeline).to_list(500)
        summary = []
        for r in results:
            total_days = r["present"] + r["late"] + r["half_day"]
            summary.append({
                "employee_id": r["_id"]["employee_id"], "employee_name": r["_id"]["employee_name"],
                "department": r["_id"]["department"],
                "total_working_days": r["total_days"], "present": r["present"],
                "absent": r["absent"], "half_days": r["half_day"],
                "late_arrivals": r["late_arrivals"], "leaves": r["on_leave"],
                "avg_hours": round(r["total_hours"] / total_days, 1) if total_days > 0 else 0,
                "total_hours": round(r["total_hours"], 2)
            })
        return {"month": month, "year": year, "summary": summary}

    # ==================================================================
    # REGULARIZATION
    # ==================================================================

    async def request_regularization(self, data, current_user: dict) -> dict:
        emp = await self._get_employee(current_user)
        emp_id = str(emp["_id"])
        org_id = emp.get("organization_id", "")

        existing = await self.db.attendance_regularizations.find_one(
            {"employee_id": emp_id, "date": data.date, "status": "pending"}
        )
        if existing:
            raise HTTPException(status_code=400, detail="Pending regularization already exists for this date")

        att = await self.db.attendance.find_one({"employee_id": emp_id, "date": data.date})
        reg = RegularizationModel(
            organization_id=org_id, employee_id=emp_id,
            employee_name=f"{emp['first_name']} {emp['last_name']}",
            department=emp.get("department", ""),
            attendance_id=str(att["_id"]) if att else None,
            date=data.date, type=data.type, proposed_time=data.proposed_time,
            reason=data.reason, status="pending",
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        result = await self.db.attendance_regularizations.insert_one(reg.model_dump())
        d = reg.model_dump(); d["_id"] = result.inserted_id
        logger.info(f"Regularization: {emp['first_name']} for {data.date} ({data.type})")

        # Notify HR
        from app.v1.notifications.service import NotificationService
        notif = NotificationService(self.db)
        emp_name = f"{emp['first_name']} {emp['last_name']}"
        await notif.notify_org_hrs(
            organization_id=org_id,
            title="Regularization Request",
            message=f"{emp_name} requested attendance regularization for {data.date}. Type: {data.type}",
            type="action", category="attendance",
            reference_id=str(result.inserted_id), reference_type="regularization"
        )

        return _serialize(d)

    async def get_regularizations(self, current_user: dict, status_filter: str = None,
                                  employee_id: str = None, page: int = 1, limit: int = 50,
                                  org_id_param: str = None) -> dict:
        role = current_user.get("role")
        org_id = self._org_id(current_user, org_id_param)
        skip, limit = paginate_query(page, limit)
        query = {"organization_id": org_id}

        if role == "employee":
            emp = await self._get_employee(current_user)
            query["employee_id"] = str(emp["_id"])
        elif employee_id:
            query["employee_id"] = employee_id

        if status_filter:
            query["status"] = status_filter

        total = await self.db.attendance_regularizations.count_documents(query)
        regs = await self.db.attendance_regularizations.find(query).skip(skip).limit(limit).sort("created_at", -1).to_list(limit)
        for r in regs:
            _serialize(r)
        return {"regularizations": regs, "total": total, "page": page, "limit": limit, "pages": (total + limit - 1) // limit}

    async def approve_regularization(self, reg_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(reg_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid ID")
        reg = await self.db.attendance_regularizations.find_one({"_id": obj_id, "organization_id": org_id})
        if not reg:
            raise HTTPException(status_code=404, detail="Not found")
        if reg["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Cannot approve: status is '{reg['status']}'")

        now = datetime.utcnow()
        await self.db.attendance_regularizations.update_one({"_id": obj_id}, {"$set": {
            "status": "approved", "approved_by": str(current_user["_id"]),
            "approved_by_name": current_user.get("full_name", current_user.get("email", "")),
            "approved_at": now, "updated_at": now
        }})

        # Create/update attendance
        emp_id = reg["employee_id"]
        att = await self.db.attendance.find_one({"employee_id": emp_id, "date": reg["date"]})
        check_in = datetime.strptime(f"{reg['date']} {reg['proposed_time']}", "%Y-%m-%d %H:%M") if reg.get("proposed_time") else None

        if att:
            update_fields = {"status": "present", "is_regularized": True, "updated_at": now}
            if reg["type"] == "missed_check_in" and check_in:
                update_fields["check_in"] = check_in
            elif reg["type"] == "missed_check_out" and check_in:
                update_fields["check_out"] = check_in
            await self.db.attendance.update_one({"_id": att["_id"]}, {"$set": update_fields})
        else:
            new_att = AttendanceModel(
                organization_id=org_id, employee_id=emp_id,
                employee_name=reg["employee_name"], department=reg.get("department", ""),
                date=reg["date"], check_in=check_in, status="present",
                is_regularized=True, source="regularization",
                created_at=now, updated_at=now
            )
            await self.db.attendance.insert_one(new_att.model_dump())

        logger.info(f"Regularization approved: {reg['employee_name']} on {reg['date']}")

        # Notify employee
        from app.v1.notifications.service import NotificationService
        notif = NotificationService(self.db)
        emp = await self.db.employees.find_one({"_id": ObjectId(reg["employee_id"])})
        if emp and emp.get("user_id"):
            await notif.create_notification(
                organization_id=org_id, user_id=emp["user_id"],
                title="Regularization Approved",
                message=f"Your attendance regularization for {reg['date']} has been approved.",
                type="info", category="attendance",
                reference_id=str(obj_id), reference_type="regularization"
            )

        updated = await self.db.attendance_regularizations.find_one({"_id": obj_id})
        return _serialize(updated)

    async def reject_regularization(self, reg_id: str, reason: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(reg_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid ID")
        reg = await self.db.attendance_regularizations.find_one({"_id": obj_id, "organization_id": org_id})
        if not reg:
            raise HTTPException(status_code=404, detail="Not found")
        if reg["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Cannot reject: status is '{reg['status']}'")
        await self.db.attendance_regularizations.update_one({"_id": obj_id}, {"$set": {
            "status": "rejected", "rejection_reason": reason, "updated_at": datetime.utcnow()
        }})

        # Notify employee
        from app.v1.notifications.service import NotificationService
        notif = NotificationService(self.db)
        emp = await self.db.employees.find_one({"_id": ObjectId(reg["employee_id"])})
        if emp and emp.get("user_id"):
            await notif.create_notification(
                organization_id=org_id, user_id=emp["user_id"],
                title="Regularization Rejected",
                message=f"Your regularization for {reg['date']} was rejected. Reason: {reason}",
                type="alert", category="attendance",
                reference_id=str(obj_id), reference_type="regularization"
            )

        updated = await self.db.attendance_regularizations.find_one({"_id": obj_id})
        return _serialize(updated)

    # ==================================================================
    # ATTENDANCE CONFIG
    # ==================================================================

    async def get_config_endpoint(self, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        config = await self.db.attendance_config.find_one({"organization_id": org_id})
        if not config:
            return {"organization_id": org_id, **DEFAULT_CONFIG}
        return _serialize(config)

    async def update_config(self, data, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        update = data.model_dump(exclude_unset=True)
        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")

        update["updated_at"] = datetime.utcnow()
        existing = await self.db.attendance_config.find_one({"organization_id": org_id})
        if existing:
            await self.db.attendance_config.update_one({"_id": existing["_id"]}, {"$set": update})
            updated = await self.db.attendance_config.find_one({"_id": existing["_id"]})
            return _serialize(updated)
        else:
            config = {**DEFAULT_CONFIG, **update, "organization_id": org_id, "created_at": datetime.utcnow()}
            result = await self.db.attendance_config.insert_one(config)
            config["_id"] = result.inserted_id
            return _serialize(config)

    # ==================================================================
    # REPORTS
    # ==================================================================

    async def report_daily(self, current_user: dict, date_str: str = None, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        if not date_str:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        all_emps = await self.db.employees.find(
            {"organization_id": org_id, "is_deleted": False, "status": "active"},
            {"first_name": 1, "last_name": 1, "department": 1, "employee_id": 1}
        ).to_list(500)

        attendance = await self.db.attendance.find({"organization_id": org_id, "date": date_str}).to_list(500)
        att_map = {a["employee_id"]: a for a in attendance}

        present, absent = [], []
        for emp in all_emps:
            emp_id = str(emp["_id"])
            info = {"employee_id": emp.get("employee_id"), "name": f"{emp['first_name']} {emp['last_name']}",
                    "department": emp.get("department", "")}
            if emp_id in att_map:
                a = att_map[emp_id]
                info.update({"status": a.get("status"), "check_in": a.get("check_in"),
                             "check_out": a.get("check_out"), "total_hours": a.get("total_hours"),
                             "is_late": a.get("is_late", False), "check_in_location": a.get("check_in_location"),
                             "check_in_photo": a.get("check_in_photo"),
                             "check_out_photo": a.get("check_out_photo")})
                present.append(info)
            else:
                info["status"] = "absent"
                absent.append(info)

        return {"date": date_str, "total_employees": len(all_emps),
                "present_count": len(present), "absent_count": len(absent),
                "present": present, "absent": absent}

    async def report_monthly(self, current_user: dict, month: int = None, year: int = None,
                             department: str = None, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        if not year: year = datetime.utcnow().year
        if not month: month = datetime.utcnow().month
        month_str = f"{year}-{month:02d}"

        match = {"organization_id": org_id, "date": {"$regex": f"^{month_str}"}}
        if department: match["department"] = {"$regex": department, "$options": "i"}

        pipeline = [
            {"$match": match},
            {"$group": {
                "_id": "$department",
                "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}},
                "absent": {"$sum": {"$cond": [{"$eq": ["$status", "absent"]}, 1, 0]}},
                "late": {"$sum": {"$cond": [{"$eq": ["$status", "late"]}, 1, 0]}},
                "half_day": {"$sum": {"$cond": [{"$eq": ["$status", "half_day"]}, 1, 0]}},
                "total_hours": {"$sum": {"$ifNull": ["$total_hours", 0]}},
                "employees": {"$addToSet": "$employee_id"}
            }},
            {"$sort": {"_id": 1}}
        ]
        results = await self.db.attendance.aggregate(pipeline).to_list(50)
        departments = []
        for r in results:
            departments.append({
                "department": r["_id"], "present_days": r["present"], "absent_days": r["absent"],
                "late_days": r["late"], "half_days": r["half_day"],
                "total_hours": round(r["total_hours"], 2), "unique_employees": len(r["employees"])
            })
        return {"year": year, "month": month, "departments": departments}
