import io
import csv
from datetime import datetime
from fastapi import HTTPException, status, UploadFile
from bson import ObjectId
from app.database import get_database
from app.models.holiday import HolidayModel
from app.v1.holidays.schema import (
    HolidayCreateRequest, HolidayUpdateRequest
)
from app.utils.helpers import paginate_query
from app.utils.logger import logger


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


class HolidayService:
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
    # CREATE
    # ------------------------------------------------------------------

    async def create_holiday(
        self, data: HolidayCreateRequest, current_user: dict,
        organization_id: str = None
    ) -> dict:
        org_id = self._org_id_from_user(current_user, organization_id)

        # Validate date format
        try:
            parsed_date = datetime.strptime(data.date, "%Y-%m-%d")
            year = parsed_date.year
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Validate type
        if data.type not in ("mandatory", "optional"):
            raise HTTPException(
                status_code=400,
                detail="type must be 'mandatory' or 'optional'"
            )

        # Check duplicate (same name + date in same org)
        dup = await self.db.holidays.find_one({
            "organization_id": org_id,
            "date": data.date,
            "name": data.name,
            "is_deleted": False
        })
        if dup:
            raise HTTPException(
                status_code=400,
                detail=f"Holiday '{data.name}' on {data.date} already exists"
            )

        holiday_model = HolidayModel(
            organization_id=org_id,
            name=data.name,
            date=data.date,
            state=data.state,
            type=data.type,
            description=data.description,
            year=year,
            is_deleted=False,
            created_by=str(current_user["_id"]),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        result = await self.db.holidays.insert_one(holiday_model.model_dump())
        holiday_dict = holiday_model.model_dump()
        holiday_dict["_id"] = result.inserted_id

        logger.info(f"Holiday '{data.name}' on {data.date} created for org {org_id}")
        return _serialize(holiday_dict)

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------

    async def get_holidays(
        self, current_user: dict, page: int = 1, limit: int = 50,
        year: int = None, type_filter: str = None, state: str = None,
        organization_id: str = None
    ) -> dict:
        org_id = self._org_id_from_user(current_user, organization_id)
        skip, limit = paginate_query(page, limit)

        query = {"organization_id": org_id, "is_deleted": False}
        if year:
            query["year"] = year
        if type_filter:
            query["type"] = type_filter
        if state:
            query["state"] = {"$regex": state, "$options": "i"}

        total = await self.db.holidays.count_documents(query)
        cursor = (
            self.db.holidays.find(query)
            .skip(skip).limit(limit).sort("date", 1)
        )
        holidays = await cursor.to_list(length=limit)
        for h in holidays:
            _serialize(h)

        return {
            "holidays": holidays,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    # ------------------------------------------------------------------
    # GET SINGLE
    # ------------------------------------------------------------------

    async def get_holiday_by_id(
        self, holiday_id: str, current_user: dict
    ) -> dict:
        try:
            obj_id = ObjectId(holiday_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid holiday ID")

        org_id = self._org_id_from_user(current_user)
        holiday = await self.db.holidays.find_one({
            "_id": obj_id, "organization_id": org_id, "is_deleted": False
        })

        if not holiday:
            raise HTTPException(status_code=404, detail="Holiday not found")

        return _serialize(holiday)

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    async def update_holiday(
        self, holiday_id: str, data: HolidayUpdateRequest, current_user: dict
    ) -> dict:
        try:
            obj_id = ObjectId(holiday_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid holiday ID")

        org_id = self._org_id_from_user(current_user)
        holiday = await self.db.holidays.find_one({
            "_id": obj_id, "organization_id": org_id, "is_deleted": False
        })

        if not holiday:
            raise HTTPException(status_code=404, detail="Holiday not found")

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        # Validate type if being changed
        if "type" in update_data and update_data["type"] not in ("mandatory", "optional"):
            raise HTTPException(status_code=400, detail="type must be 'mandatory' or 'optional'")

        # Validate and update year if date is changed
        if "date" in update_data:
            try:
                parsed_date = datetime.strptime(update_data["date"], "%Y-%m-%d")
                update_data["year"] = parsed_date.year
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        update_data["updated_at"] = datetime.utcnow()
        await self.db.holidays.update_one({"_id": obj_id}, {"$set": update_data})

        logger.info(f"Holiday {holiday_id} updated by {current_user.get('email')}")
        updated = await self.db.holidays.find_one({"_id": obj_id})
        return _serialize(updated)

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    async def delete_holiday(
        self, holiday_id: str, current_user: dict
    ) -> dict:
        try:
            obj_id = ObjectId(holiday_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid holiday ID")

        org_id = self._org_id_from_user(current_user)
        holiday = await self.db.holidays.find_one({
            "_id": obj_id, "organization_id": org_id, "is_deleted": False
        })

        if not holiday:
            raise HTTPException(status_code=404, detail="Holiday not found")

        await self.db.holidays.update_one(
            {"_id": obj_id},
            {"$set": {"is_deleted": True, "updated_at": datetime.utcnow()}}
        )

        logger.info(f"Holiday '{holiday['name']}' deleted by {current_user.get('email')}")
        return {"message": f"Holiday '{holiday['name']}' on {holiday['date']} deleted successfully"}

    # ------------------------------------------------------------------
    # CSV IMPORT
    # ------------------------------------------------------------------

    async def import_holidays_csv(
        self, file: UploadFile, current_user: dict, organization_id: str = None
    ) -> dict:
        org_id = self._org_id_from_user(current_user, organization_id)

        content = await file.read()
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))

        REQUIRED_COLS = {"name", "date"}

        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV file is empty or has no headers")

        normalized_fields = {c.strip().lower() for c in reader.fieldnames}
        missing_cols = REQUIRED_COLS - normalized_fields
        if missing_cols:
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing required columns: {missing_cols}. Required: name, date. Optional: state, type, description"
            )

        imported = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

            name = row.get("name", "").strip()
            date_str = row.get("date", "").strip()
            state = row.get("state", "").strip() or None
            holiday_type = row.get("type", "mandatory").strip().lower()
            description = row.get("description", "").strip() or None

            # Validate required fields
            if not name:
                errors.append({"row": row_num, "name": None, "error": "Missing holiday name"})
                continue

            if not date_str:
                errors.append({"row": row_num, "name": name, "error": "Missing date"})
                continue

            # Validate date
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                year = parsed_date.year
            except ValueError:
                errors.append({
                    "row": row_num, "name": name,
                    "error": f"Invalid date format '{date_str}'. Use YYYY-MM-DD"
                })
                continue

            # Validate type
            if holiday_type not in ("mandatory", "optional"):
                holiday_type = "mandatory"

            # Check duplicate
            dup = await self.db.holidays.find_one({
                "organization_id": org_id,
                "date": date_str,
                "name": name,
                "is_deleted": False
            })
            if dup:
                errors.append({
                    "row": row_num, "name": name,
                    "error": f"Duplicate: '{name}' on {date_str} already exists"
                })
                continue

            # Insert
            holiday_model = HolidayModel(
                organization_id=org_id,
                name=name,
                date=date_str,
                state=state,
                type=holiday_type,
                description=description,
                year=year,
                is_deleted=False,
                created_by=str(current_user["_id"]),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            await self.db.holidays.insert_one(holiday_model.model_dump())
            imported += 1

        logger.info(f"Holiday CSV import: {imported} imported, {len(errors)} failed for org {org_id}")
        return {
            "imported": imported,
            "failed": len(errors),
            "errors": errors
        }
