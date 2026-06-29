import calendar
from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId
from app.database import get_database
from app.models.payroll import PayrollConfigModel, PayrollRunModel, PayslipModel, PayrollAdjustmentModel
from app.utils.helpers import paginate_query
from app.utils.logger import logger


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


DEFAULT_CONFIG = {
    "basic_percentage": 40.0, "hra_percentage": 20.0, "special_allowance_percentage": 15.0,
    "pf_percentage": 12.0, "esi_employee_percentage": 0.75,
    "esi_employer_percentage": 3.25, "esi_limit": 21000,
    "professional_tax": 200, "pay_day": 28,
    "pay_cycle": "monthly", "lop_calculation": "calendar_days"
}


class PayrollService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    def _org_id(self, user: dict, explicit: str = None) -> str:
        if user.get("role") == "superadmin":
            if not explicit: raise HTTPException(status_code=400, detail="superadmin must supply organization_id")
            return explicit
        return user.get("organization_id") or ""

    async def _get_config(self, org_id: str) -> dict:
        config = await self.db.payroll_configs.find_one({"organization_id": org_id})
        return config if config else {**DEFAULT_CONFIG, "organization_id": org_id}

    # ==================================================================
    # CONFIG
    # ==================================================================

    async def get_config(self, user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        config = await self.db.payroll_configs.find_one({"organization_id": org_id})
        if not config:
            return {"organization_id": org_id, **DEFAULT_CONFIG}
        return _serialize(config)

    async def update_config(self, data: dict, user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        update = {k: v for k, v in data.items() if v is not None}
        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")
        update["updated_at"] = datetime.utcnow()

        existing = await self.db.payroll_configs.find_one({"organization_id": org_id})
        if existing:
            await self.db.payroll_configs.update_one({"_id": existing["_id"]}, {"$set": update})
            updated = await self.db.payroll_configs.find_one({"_id": existing["_id"]})
            return _serialize(updated)
        else:
            config = {**DEFAULT_CONFIG, **update, "organization_id": org_id, "created_at": datetime.utcnow()}
            result = await self.db.payroll_configs.insert_one(config)
            config["_id"] = result.inserted_id
            return _serialize(config)

    # ==================================================================
    # RUN PAYROLL
    # ==================================================================

    async def run_payroll(self, month: int, year: int, user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)

        # Check if already run
        existing_run = await self.db.payroll_runs.find_one({"organization_id": org_id, "month": month, "year": year})
        if existing_run:
            raise HTTPException(status_code=400, detail=f"Payroll already processed for {month}/{year}")

        config = await self._get_config(org_id)
        employees = await self.db.employees.find(
            {"organization_id": org_id, "is_deleted": False, "status": "active"}
        ).to_list(500)

        if not employees:
            raise HTTPException(status_code=400, detail="No active employees found")

        # Calculate days
        cal_days = calendar.monthrange(year, month)[1]
        month_str = f"{year}-{month:02d}"

        # Create payroll run
        run = PayrollRunModel(
            organization_id=org_id, month=month, year=year, status="processed",
            processed_by=str(user["_id"]), processed_at=datetime.utcnow(),
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        run_result = await self.db.payroll_runs.insert_one(run.model_dump())
        run_id = str(run_result.inserted_id)

        total_gross = 0
        total_deductions = 0
        total_net = 0

        for emp in employees:
            payslip = await self._calculate_payslip(emp, month, year, cal_days, month_str, config, run_id, org_id)
            await self.db.payslips.insert_one(payslip)
            total_gross += payslip["gross_pay"]
            total_deductions += payslip["total_deductions"]
            total_net += payslip["net_pay"]

        # Update run totals
        await self.db.payroll_runs.update_one(
            {"_id": run_result.inserted_id},
            {"$set": {
                "total_gross": round(total_gross, 2), "total_deductions": round(total_deductions, 2),
                "total_net": round(total_net, 2), "employee_count": len(employees)
            }}
        )

        # Mark adjustments as applied
        await self.db.payroll_adjustments.update_many(
            {"organization_id": org_id, "month": month, "year": year, "applied": False},
            {"$set": {"applied": True}}
        )

        logger.info(f"Payroll run: {month}/{year} for org {org_id}, {len(employees)} employees")
        return {
            "id": run_id, "month": month, "year": year, "status": "processed",
            "employee_count": len(employees),
            "total_gross": round(total_gross, 2), "total_net": round(total_net, 2),
            "payslips_generated": len(employees)
        }

    async def _calculate_payslip(self, emp, month, year, cal_days, month_str, config, run_id, org_id) -> dict:
        """Calculate individual employee payslip from CTC + config percentages"""
        sal = emp.get("salary_structure", {})
        ctc_annual = sal.get("ctc", 0)
        ctc_monthly = ctc_annual / 12

        # Calculate salary components from config percentages
        basic_pct = config.get("basic_percentage", 40)
        hra_pct = config.get("hra_percentage", 20)
        special_pct = config.get("special_allowance_percentage", 15)

        basic = round(ctc_monthly * basic_pct / 100, 2)
        hra = round(ctc_monthly * hra_pct / 100, 2)
        special = round(ctc_monthly * special_pct / 100, 2)
        monthly_gross = basic + hra + special
        emp_id = str(emp["_id"])

        # Working days (simple: calendar days - weekends)
        import calendar as cal_mod
        weekends = 0
        for d in range(1, cal_days + 1):
            if cal_mod.weekday(year, month, d) in (5, 6):
                weekends += 1
        working_days = cal_days - weekends

        # LOP days from attendance
        att_pipeline = [
            {"$match": {"employee_id": emp_id, "date": {"$regex": f"^{month_str}"}, "status": "absent"}},
            {"$count": "lop"}
        ]
        lop_result = await self.db.attendance.aggregate(att_pipeline).to_list(1)
        lop_days = lop_result[0]["lop"] if lop_result else 0
        days_worked = working_days - lop_days

        # LOP deduction (pro-rated)
        per_day = monthly_gross / working_days if working_days > 0 else 0
        lop_deduction = round(per_day * lop_days, 2)

        # Adjustments (bonus, reimbursement, deduction)
        adjustments = await self.db.payroll_adjustments.find(
            {"employee_id": emp_id, "month": month, "year": year, "applied": False}
        ).to_list(20)
        bonus = sum(a["amount"] for a in adjustments if a["type"] == "bonus")
        reimbursements = sum(a["amount"] for a in adjustments if a["type"] == "reimbursement")
        other_deductions = sum(a["amount"] for a in adjustments if a["type"] == "deduction")

        # Gross
        gross_pay = round(monthly_gross - lop_deduction + bonus + reimbursements, 2)

        # Deductions
        pf_pct = config.get("pf_percentage", 12)
        esi_pct = config.get("esi_employee_percentage", 0.75)
        esi_limit = config.get("esi_limit", 21000)
        pt = config.get("professional_tax", 200)

        pf_employee = round(basic * pf_pct / 100, 2)
        esi_employee = round(gross_pay * esi_pct / 100, 2) if gross_pay <= esi_limit else 0
        tds = round(gross_pay * 0.1, 2)  # Simplified: 10% TDS

        total_deductions = round(pf_employee + esi_employee + pt + tds + other_deductions, 2)
        net_pay = round(gross_pay - total_deductions, 2)

        # Employer contributions
        pf_employer = round(basic * pf_pct / 100, 2)
        esi_employer = round(gross_pay * config.get("esi_employer_percentage", 3.25) / 100, 2) if gross_pay <= esi_limit else 0

        return PayslipModel(
            organization_id=org_id, payroll_run_id=run_id,
            employee_id=emp_id, employee_name=f"{emp['first_name']} {emp['last_name']}",
            employee_code=emp.get("employee_id", ""), department=emp.get("department", ""),
            month=month, year=year, working_days=working_days,
            days_worked=days_worked, lop_days=lop_days,
            earnings={"basic": basic, "hra": hra, "special_allowance": special, "bonus": bonus, "reimbursements": reimbursements},
            gross_pay=gross_pay,
            deductions={"pf_employee": pf_employee, "esi_employee": esi_employee, "professional_tax": pt, "tds": tds, "lop_deduction": lop_deduction, "other_deductions": other_deductions},
            total_deductions=total_deductions, net_pay=net_pay,
            employer_contributions={"pf_employer": pf_employer, "esi_employer": esi_employer},
            status="processed", created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        ).model_dump()

    # ==================================================================
    # RUNS
    # ==================================================================

    async def get_runs(self, user: dict, year: int = None, status_filter: str = None, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        query = {"organization_id": org_id}
        if year: query["year"] = year
        if status_filter: query["status"] = status_filter
        runs = await self.db.payroll_runs.find(query).sort("created_at", -1).to_list(50)
        for r in runs: _serialize(r)
        return {"runs": runs, "total": len(runs)}

    async def get_run_detail(self, run_id: str, user: dict) -> dict:
        org_id = self._org_id(user)
        try: obj_id = ObjectId(run_id)
        except: raise HTTPException(status_code=400, detail="Invalid run ID")
        run = await self.db.payroll_runs.find_one({"_id": obj_id, "organization_id": org_id})
        if not run: raise HTTPException(status_code=404, detail="Payroll run not found")
        _serialize(run)
        payslips = await self.db.payslips.find({"payroll_run_id": run_id}).to_list(500)
        for p in payslips: _serialize(p)
        run["payslips"] = payslips
        return run

    async def approve_run(self, run_id: str, user: dict) -> dict:
        org_id = self._org_id(user)
        try: obj_id = ObjectId(run_id)
        except: raise HTTPException(status_code=400, detail="Invalid run ID")
        run = await self.db.payroll_runs.find_one({"_id": obj_id, "organization_id": org_id})
        if not run: raise HTTPException(status_code=404, detail="Not found")
        if run["status"] != "processed": raise HTTPException(status_code=400, detail=f"Cannot approve: status is '{run['status']}'")
        now = datetime.utcnow()
        await self.db.payroll_runs.update_one({"_id": obj_id}, {"$set": {"status": "approved", "approved_by": str(user["_id"]), "approved_by_name": user.get("full_name", ""), "approved_at": now, "updated_at": now}})
        await self.db.payslips.update_many({"payroll_run_id": run_id}, {"$set": {"status": "approved"}})
        updated = await self.db.payroll_runs.find_one({"_id": obj_id})
        return _serialize(updated)

    async def mark_paid(self, run_id: str, user: dict) -> dict:
        org_id = self._org_id(user)
        try: obj_id = ObjectId(run_id)
        except: raise HTTPException(status_code=400, detail="Invalid run ID")
        run = await self.db.payroll_runs.find_one({"_id": obj_id, "organization_id": org_id})
        if not run: raise HTTPException(status_code=404, detail="Not found")
        if run["status"] != "approved": raise HTTPException(status_code=400, detail=f"Cannot mark paid: status is '{run['status']}'")
        now = datetime.utcnow()
        await self.db.payroll_runs.update_one({"_id": obj_id}, {"$set": {"status": "paid", "paid_at": now, "updated_at": now}})
        await self.db.payslips.update_many({"payroll_run_id": run_id}, {"$set": {"status": "paid", "paid_at": now}})
        updated = await self.db.payroll_runs.find_one({"_id": obj_id})
        return _serialize(updated)

    # ==================================================================
    # PAYSLIPS
    # ==================================================================

    async def get_payslips(self, user: dict, month: int = None, year: int = None, employee_id: str = None, department: str = None, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        query = {"organization_id": org_id}
        if month: query["month"] = month
        if year: query["year"] = year
        if employee_id: query["employee_id"] = employee_id
        if department: query["department"] = {"$regex": department, "$options": "i"}
        payslips = await self.db.payslips.find(query).sort("created_at", -1).to_list(500)
        for p in payslips: _serialize(p)
        return {"payslips": payslips, "total": len(payslips)}

    async def get_my_payslips(self, user: dict, year: int = None) -> dict:
        emp = await self.db.employees.find_one({"user_id": str(user["_id"]), "is_deleted": False})
        if not emp: raise HTTPException(status_code=404, detail="Employee not found")
        query = {"employee_id": str(emp["_id"])}
        if year: query["year"] = year
        payslips = await self.db.payslips.find(query).sort([("year", -1), ("month", -1)]).to_list(50)
        for p in payslips: _serialize(p)
        return {"payslips": payslips, "total": len(payslips)}

    async def get_payslip_detail(self, payslip_id: str, user: dict) -> dict:
        try: obj_id = ObjectId(payslip_id)
        except: raise HTTPException(status_code=400, detail="Invalid payslip ID")
        role = user.get("role")
        if role == "employee":
            emp = await self.db.employees.find_one({"user_id": str(user["_id"]), "is_deleted": False})
            if not emp: raise HTTPException(status_code=404, detail="Employee not found")
            payslip = await self.db.payslips.find_one({"_id": obj_id, "employee_id": str(emp["_id"])})
        else:
            org_id = self._org_id(user)
            payslip = await self.db.payslips.find_one({"_id": obj_id, "organization_id": org_id})
        if not payslip: raise HTTPException(status_code=404, detail="Payslip not found")
        return _serialize(payslip)

    async def edit_payslip(self, payslip_id: str, data: dict, user: dict) -> dict:
        org_id = self._org_id(user)
        try: obj_id = ObjectId(payslip_id)
        except: raise HTTPException(status_code=400, detail="Invalid ID")
        payslip = await self.db.payslips.find_one({"_id": obj_id, "organization_id": org_id})
        if not payslip: raise HTTPException(status_code=404, detail="Not found")
        if payslip["status"] != "processed": raise HTTPException(status_code=400, detail="Can only edit before approval")
        # Recalculate with new values
        earnings = payslip["earnings"]
        deductions = payslip["deductions"]
        if "bonus" in data: earnings["bonus"] = data["bonus"]
        if "reimbursements" in data: earnings["reimbursements"] = data["reimbursements"]
        if "tds" in data: deductions["tds"] = data["tds"]
        if "other_deductions" in data: deductions["other_deductions"] = data["other_deductions"]
        gross = sum(earnings.values())
        total_ded = sum(deductions.values())
        net = round(gross - total_ded, 2)
        await self.db.payslips.update_one({"_id": obj_id}, {"$set": {"earnings": earnings, "deductions": deductions, "gross_pay": gross, "total_deductions": total_ded, "net_pay": net, "updated_at": datetime.utcnow()}})
        updated = await self.db.payslips.find_one({"_id": obj_id})
        return _serialize(updated)

    # ==================================================================
    # ADJUSTMENTS
    # ==================================================================

    async def add_adjustment(self, data: dict, user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        emp_id = data.get("employee_id")
        try: emp = await self.db.employees.find_one({"_id": ObjectId(emp_id), "organization_id": org_id, "is_deleted": False})
        except: raise HTTPException(status_code=400, detail="Invalid employee_id")
        if not emp: raise HTTPException(status_code=404, detail="Employee not found")

        adj = PayrollAdjustmentModel(
            organization_id=org_id, employee_id=emp_id,
            employee_name=f"{emp['first_name']} {emp['last_name']}",
            type=data["type"], amount=data["amount"], description=data.get("description", ""),
            month=data["month"], year=data["year"], applied=False,
            created_by=str(user["_id"]), created_at=datetime.utcnow()
        )
        result = await self.db.payroll_adjustments.insert_one(adj.model_dump())
        d = adj.model_dump(); d["_id"] = result.inserted_id
        return _serialize(d)

    async def get_adjustments(self, user: dict, employee_id: str = None, month: int = None, year: int = None, type_filter: str = None, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        query = {"organization_id": org_id}
        if employee_id: query["employee_id"] = employee_id
        if month: query["month"] = month
        if year: query["year"] = year
        if type_filter: query["type"] = type_filter
        adjs = await self.db.payroll_adjustments.find(query).sort("created_at", -1).to_list(200)
        for a in adjs: _serialize(a)
        return {"adjustments": adjs, "total": len(adjs)}

    # ==================================================================
    # REPORTS
    # ==================================================================

    async def report_summary(self, user: dict, month: int = None, year: int = None, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        if not year: year = datetime.utcnow().year
        if not month: month = datetime.utcnow().month

        query = {"organization_id": org_id, "month": month, "year": year}
        payslips = await self.db.payslips.find(query).to_list(500)

        if not payslips:
            return {"month": month, "year": year, "message": "No payroll data for this period"}

        total_gross = sum(p["gross_pay"] for p in payslips)
        total_deductions = sum(p["total_deductions"] for p in payslips)
        total_net = sum(p["net_pay"] for p in payslips)
        total_pf = sum(p["deductions"].get("pf_employee", 0) for p in payslips)
        total_esi = sum(p["deductions"].get("esi_employee", 0) for p in payslips)
        total_tds = sum(p["deductions"].get("tds", 0) for p in payslips)

        # Department breakdown
        dept_map = {}
        for p in payslips:
            dept = p.get("department", "Other")
            if dept not in dept_map:
                dept_map[dept] = {"gross": 0, "net": 0, "count": 0}
            dept_map[dept]["gross"] += p["gross_pay"]
            dept_map[dept]["net"] += p["net_pay"]
            dept_map[dept]["count"] += 1

        return {
            "month": month, "year": year, "employee_count": len(payslips),
            "total_gross": round(total_gross, 2), "total_deductions": round(total_deductions, 2),
            "total_net": round(total_net, 2), "total_pf": round(total_pf, 2),
            "total_esi": round(total_esi, 2), "total_tds": round(total_tds, 2),
            "avg_salary": round(total_net / len(payslips), 2),
            "department_breakdown": dept_map
        }

    async def report_annual(self, user: dict, employee_id: str, year: int = None, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        if not year: year = datetime.utcnow().year

        try: emp = await self.db.employees.find_one({"_id": ObjectId(employee_id), "organization_id": org_id})
        except: raise HTTPException(status_code=400, detail="Invalid employee_id")
        if not emp: raise HTTPException(status_code=404, detail="Employee not found")

        payslips = await self.db.payslips.find({"employee_id": employee_id, "year": year}).sort("month", 1).to_list(12)
        month_wise = []
        total_gross = 0
        total_tds = 0
        for p in payslips:
            month_wise.append({"month": p["month"], "gross": p["gross_pay"], "tds": p["deductions"].get("tds", 0), "net": p["net_pay"]})
            total_gross += p["gross_pay"]
            total_tds += p["deductions"].get("tds", 0)

        return {
            "employee_name": f"{emp['first_name']} {emp['last_name']}",
            "employee_code": emp.get("employee_id", ""),
            "year": year,
            "total_gross_annual": round(total_gross, 2),
            "total_tds_annual": round(total_tds, 2),
            "total_net_annual": round(total_gross - total_tds, 2),
            "month_wise": month_wise
        }
