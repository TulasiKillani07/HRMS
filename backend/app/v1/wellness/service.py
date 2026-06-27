from datetime import datetime, timedelta
from fastapi import HTTPException
from bson import ObjectId
from app.database import get_database
from app.models.wellness import MoodEntryModel, WellnessProgramModel
from app.utils.logger import logger


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


class WellnessService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    def _org_id(self, user: dict, explicit: str = None) -> str:
        if user.get("role") == "superadmin":
            if not explicit:
                raise HTTPException(status_code=400, detail="superadmin must supply organization_id")
            return explicit
        return user.get("organization_id") or ""

    async def _get_emp(self, user: dict):
        emp = await self.db.employees.find_one({"user_id": str(user["_id"]), "is_deleted": False})
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        return emp

    # ==================================================================
    # MOOD CHECK-IN
    # ==================================================================

    async def submit_mood(self, score: int, note: str, current_user: dict) -> dict:
        emp = await self._get_emp(current_user)
        emp_id = str(emp["_id"])
        org_id = emp.get("organization_id", "")
        today = datetime.utcnow().strftime("%Y-%m-%d")

        if score < 1 or score > 5:
            raise HTTPException(status_code=400, detail="Score must be 1-5")

        # One entry per day — block if already submitted
        existing = await self.db.wellness_mood_entries.find_one(
            {"employee_id": emp_id, "date": today}
        )

        if existing:
            raise HTTPException(status_code=400, detail="Mood already submitted for today")

        entry = MoodEntryModel(
            organization_id=org_id, employee_id=emp_id,
            employee_name=f"{emp['first_name']} {emp['last_name']}",
            department=emp.get("department", ""),
            date=today, score=score, note=note or None,
            created_at=datetime.utcnow()
        )

        result = await self.db.wellness_mood_entries.insert_one(entry.model_dump())
        entry_id = str(result.inserted_id)

        # Calculate streak
        streak = await self._calc_streak(emp_id)

        return {"id": entry_id, "score": score, "date": today, "note": note, "streak": streak}

    async def _calc_streak(self, emp_id: str) -> int:
        """Count consecutive days with mood entries"""
        streak = 0
        check_date = datetime.utcnow().date()
        while True:
            date_str = check_date.strftime("%Y-%m-%d")
            exists = await self.db.wellness_mood_entries.find_one(
                {"employee_id": emp_id, "date": date_str}
            )
            if exists:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
            if streak > 365:
                break
        return streak

    # ==================================================================
    # MOOD HISTORY (Employee)
    # ==================================================================

    async def get_mood_history(self, current_user: dict, days: int = 30) -> dict:
        emp = await self._get_emp(current_user)
        emp_id = str(emp["_id"])

        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        entries = await self.db.wellness_mood_entries.find(
            {"employee_id": emp_id, "date": {"$gte": start_date}}
        ).sort("date", -1).to_list(days)

        for e in entries:
            _serialize(e)

        scores = [e["score"] for e in entries]
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        streak = await self._calc_streak(emp_id)

        return {
            "entries": entries,
            "average": avg,
            "streak": streak,
            "total_entries": len(entries)
        }

    # ==================================================================
    # WELLNESS DASHBOARD (HR)
    # ==================================================================

    async def get_dashboard(self, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        today = datetime.utcnow()
        week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")

        # Today's submissions
        today_entries = await self.db.wellness_mood_entries.find(
            {"organization_id": org_id, "date": today_str}
        ).to_list(500)

        # Mood distribution (today)
        dist = {"great": 0, "good": 0, "okay": 0, "low": 0, "terrible": 0}
        for e in today_entries:
            s = e["score"]
            if s == 5: dist["great"] += 1
            elif s == 4: dist["good"] += 1
            elif s == 3: dist["okay"] += 1
            elif s == 2: dist["low"] += 1
            else: dist["terrible"] += 1

        # Weekly trend
        weekly_trend = []
        for i in range(6, -1, -1):
            d = (today - timedelta(days=i))
            d_str = d.strftime("%Y-%m-%d")
            day_name = d.strftime("%a")
            pipeline = [
                {"$match": {"organization_id": org_id, "date": d_str}},
                {"$group": {"_id": None, "avg": {"$avg": "$score"}}}
            ]
            r = await self.db.wellness_mood_entries.aggregate(pipeline).to_list(1)
            avg = round(r[0]["avg"], 1) if r else 0
            weekly_trend.append({"day": day_name, "date": d_str, "avg_score": avg})

        # Department scores (last 7 days)
        dept_pipeline = [
            {"$match": {"organization_id": org_id, "date": {"$gte": week_ago}}},
            {"$group": {"_id": "$department", "avg": {"$avg": "$score"}}}
        ]
        dept_results = await self.db.wellness_mood_entries.aggregate(dept_pipeline).to_list(20)
        dept_scores = {r["_id"]: round(r["avg"], 1) for r in dept_results if r["_id"]}

        # At-risk employees (avg < 2.5 over 7 days)
        at_risk_pipeline = [
            {"$match": {"organization_id": org_id, "date": {"$gte": week_ago}}},
            {"$group": {
                "_id": {"employee_id": "$employee_id", "employee_name": "$employee_name", "department": "$department"},
                "avg_score": {"$avg": "$score"},
                "entries": {"$sum": 1}
            }},
            {"$match": {"avg_score": {"$lt": 2.5}}},
            {"$sort": {"avg_score": 1}}
        ]
        at_risk_results = await self.db.wellness_mood_entries.aggregate(at_risk_pipeline).to_list(20)
        at_risk = []
        for r in at_risk_results:
            at_risk.append({
                "employee_id": r["_id"]["employee_id"],
                "employee_name": r["_id"]["employee_name"],
                "department": r["_id"]["department"],
                "avg_score_7d": round(r["avg_score"], 1),
                "entries_7d": r["entries"]
            })

        # Org wellness score
        all_week = await self.db.wellness_mood_entries.find(
            {"organization_id": org_id, "date": {"$gte": week_ago}}
        ).to_list(5000)
        all_scores = [e["score"] for e in all_week]
        org_avg = sum(all_scores) / len(all_scores) if all_scores else 0
        wellness_score = round((org_avg / 5) * 100)

        # Participation rate
        total_active = await self.db.employees.count_documents(
            {"organization_id": org_id, "is_deleted": False, "status": "active"}
        )
        participation = round((len(today_entries) / total_active) * 100) if total_active > 0 else 0

        return {
            "wellness_score": wellness_score,
            "mood_distribution": dist,
            "weekly_trend": weekly_trend,
            "department_scores": dept_scores,
            "at_risk_employees": at_risk,
            "participation_rate": participation,
            "total_submissions_today": len(today_entries)
        }

    # ==================================================================
    # ANALYTICS (HR)
    # ==================================================================

    async def get_analytics(self, current_user: dict, period: int = 30, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        start = (datetime.utcnow() - timedelta(days=period)).strftime("%Y-%m-%d")
        prev_start = (datetime.utcnow() - timedelta(days=period * 2)).strftime("%Y-%m-%d")

        # Current period avg
        pipeline = [
            {"$match": {"organization_id": org_id, "date": {"$gte": start}}},
            {"$group": {"_id": None, "avg": {"$avg": "$score"}, "count": {"$sum": 1}}}
        ]
        curr = await self.db.wellness_mood_entries.aggregate(pipeline).to_list(1)
        avg_score = round(curr[0]["avg"], 2) if curr else 0

        # Previous period avg
        prev_pipeline = [
            {"$match": {"organization_id": org_id, "date": {"$gte": prev_start, "$lt": start}}},
            {"$group": {"_id": None, "avg": {"$avg": "$score"}}}
        ]
        prev = await self.db.wellness_mood_entries.aggregate(prev_pipeline).to_list(1)
        prev_avg = prev[0]["avg"] if prev else avg_score
        change = round(avg_score - prev_avg, 2)
        trend = "improving" if change > 0.1 else "declining" if change < -0.1 else "stable"

        # Day of week averages
        dow_pipeline = [
            {"$match": {"organization_id": org_id, "date": {"$gte": start}}},
            {"$addFields": {"date_obj": {"$dateFromString": {"dateString": "$date"}}}},
            {"$group": {"_id": {"$dayOfWeek": "$date_obj"}, "avg": {"$avg": "$score"}}}
        ]
        dow_results = await self.db.wellness_mood_entries.aggregate(dow_pipeline).to_list(7)
        day_names = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
        dow_map = {day_names.get(r["_id"], "?"): round(r["avg"], 1) for r in dow_results}

        happiest = max(dow_map, key=dow_map.get) if dow_map else "N/A"
        lowest = min(dow_map, key=dow_map.get) if dow_map else "N/A"

        return {
            "avg_score": avg_score,
            "trend": trend,
            "change_vs_last_period": change,
            "happiest_day": happiest,
            "lowest_day": lowest,
            "day_of_week_scores": dow_map,
            "period_days": period
        }

    # ==================================================================
    # WELLNESS PROGRAMS
    # ==================================================================

    async def create_program(self, data: dict, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        prog = WellnessProgramModel(
            organization_id=org_id, name=data["name"],
            description=data.get("description"), type=data.get("type", "ongoing"),
            start_date=data.get("start_date"), end_date=data.get("end_date"),
            max_participants=data.get("max_participants"),
            participants=[], created_by=str(current_user["_id"]),
            is_active=True, created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        result = await self.db.wellness_programs.insert_one(prog.model_dump())
        d = prog.model_dump(); d["_id"] = result.inserted_id
        d["total_participants"] = 0
        d["participation"] = 0
        logger.info(f"Wellness program '{data['name']}' created")
        return _serialize(d)

    async def list_programs(self, current_user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(current_user, org_id_param)
        user_id = str(current_user["_id"])

        # Get employee_id for enrollment check
        emp = await self.db.employees.find_one({"user_id": user_id, "is_deleted": False})
        emp_id = str(emp["_id"]) if emp else ""

        progs = await self.db.wellness_programs.find(
            {"organization_id": org_id, "is_active": True}
        ).sort("created_at", -1).to_list(50)

        total_active = await self.db.employees.count_documents(
            {"organization_id": org_id, "is_deleted": False, "status": "active"}
        )

        results = []
        for p in progs:
            _serialize(p)
            participants = p.get("participants", [])
            p["total_participants"] = len(participants)
            p["participation"] = round((len(participants) / total_active) * 100) if total_active else 0
            p["is_enrolled"] = emp_id in participants
            p.pop("participants", None)
            results.append(p)

        return {"programs": results}

    async def enroll_program(self, program_id: str, current_user: dict) -> dict:
        emp = await self._get_emp(current_user)
        emp_id = str(emp["_id"])

        try:
            obj_id = ObjectId(program_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid program ID")

        prog = await self.db.wellness_programs.find_one({"_id": obj_id, "is_active": True})
        if not prog:
            raise HTTPException(status_code=404, detail="Program not found")

        if emp_id in prog.get("participants", []):
            raise HTTPException(status_code=400, detail="Already enrolled")

        if prog.get("max_participants") and len(prog.get("participants", [])) >= prog["max_participants"]:
            raise HTTPException(status_code=400, detail="Program is full")

        await self.db.wellness_programs.update_one(
            {"_id": obj_id}, {"$addToSet": {"participants": emp_id}}
        )
        return {"message": f"Enrolled in '{prog['name']}'"}

    async def unenroll_program(self, program_id: str, current_user: dict) -> dict:
        emp = await self._get_emp(current_user)
        emp_id = str(emp["_id"])

        try:
            obj_id = ObjectId(program_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid program ID")

        await self.db.wellness_programs.update_one(
            {"_id": obj_id}, {"$pull": {"participants": emp_id}}
        )
        return {"message": "Unenrolled successfully"}
