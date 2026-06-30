import calendar
from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId
from app.database import get_database
from app.models.payroll import (
    CompanyPayrollSettingsModel, PayrollRunModel, PayslipModel, PayrollAdjustmentModel
)
from app.v1.payroll.engine import (
    calculate_working_days, calculate_earnings, calculate_lop,
    calculate_pf, calculate_esi, calculate_pt, calculate_net
)
from app.utils.helpers import paginate_query
from app.utils.logger import logger


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


DEFAULT_SETTINGS = CompanyPayrollSettingsModel(organization_id="").model_dump()
del DEFAULT_SETTINGS["organization_id"]
del DEFAULT_SETTINGS["created_at"]
del DEFAULT_SETTINGS["updated_at"]


class PayrollService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()

    def _org_id(self, user: dict, explicit: str = None) -> str:
        if user.get("role") == "superadmin":
            if not explicit: raise HTTPException(status_code=400, detail="superadmin must supply organization_id")
            return explicit
        return user.get("organization_id") or ""

    async def _get_settings(self, org_id: str) -> dict:
        s = await self.db.company_payroll_settings.find_one({"organization_id": org_id})
        if not s:
            return {**DEFAULT_SETTINGS, "organization_id": org_id}
        return s

    # ==================================================================
    # SETTINGS CRUD
    # ==================================================================

    async def get_settings(self, user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        s = await self.db.company_payroll_settings.find_one({"organization_id": org_id})
        if not s:
            return {"organization_id": org_id, **DEFAULT_SETTINGS}
        return _serialize(s)

    async def update_settings(self, data: dict, user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        update = {k: v for k, v in data.items() if v is not None}
        if not update:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Validate salary structure total = 100%
        if "salary_structure" in update:
            ss = update["salary_structure"]
            total = (ss.get("basic_percentage", 0) + ss.get("hra_percentage", 0) +
                     ss.get("special_allowance_percentage", 0) + ss.get("other_percentage", 0))
            if round(total, 2) != 100:
                raise HTTPException(
                    status_code=400,
                    detail=f"Salary structure percentages must total 100%. Current total: {total}%"
                )

        update["updated_at"] = datetime.utcnow()

        existing = await self.db.company_payroll_settings.find_one({"organization_id": org_id})
        if existing:
            await self.db.company_payroll_settings.update_one({"_id": existing["_id"]}, {"$set": update})
            updated = await self.db.company_payroll_settings.find_one({"_id": existing["_id"]})
            return _serialize(updated)
        else:
            doc = {**DEFAULT_SETTINGS, **update, "organization_id": org_id, "created_at": datetime.utcnow()}
            result = await self.db.company_payroll_settings.insert_one(doc)
            doc["_id"] = result.inserted_id
            return _serialize(doc)

    # ==================================================================
    # PAYROLL RUN
    # ==================================================================

    async def run_payroll(self, month: int, year: int, user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)

        existing_run = await self.db.payroll_runs.find_one({"organization_id": org_id, "month": month, "year": year})
        if existing_run:
            settings = await self._get_settings(org_id)
            schedule = settings.get("payroll_schedule", {})
            lock = schedule.get("lock_after_processing", True)
            allow_reprocess = schedule.get("allow_reprocessing", False)
            if lock and not allow_reprocess:
                raise HTTPException(status_code=400, detail=f"Payroll for {month}/{year} is locked. Reprocessing is disabled. Change 'allow_reprocessing' in payroll schedule to override.")
            # Delete old run and payslips to reprocess
            await self.db.payroll_runs.delete_one({"_id": existing_run["_id"]})
            await self.db.payslips.delete_many({"payroll_run_id": str(existing_run["_id"])})

        settings = await self._get_settings(org_id)
        employees = await self.db.employees.find(
            {"organization_id": org_id, "is_deleted": False, "status": "active"}
        ).to_list(500)

        if not employees:
            raise HTTPException(status_code=400, detail="No active employees found")

        month_str = f"{year}-{month:02d}"
        working_days = calculate_working_days(month, year, settings.get("lop", {}))

        # Create run
        run = PayrollRunModel(
            organization_id=org_id, month=month, year=year, status="processed",
            processed_by=str(user["_id"]), processed_at=datetime.utcnow(),
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )
        run_result = await self.db.payroll_runs.insert_one(run.model_dump())
        run_id = str(run_result.inserted_id)

        total_gross = 0; total_deductions = 0; total_net = 0

        for emp in employees:
            payslip = await self._build_payslip(emp, month, year, month_str, working_days, settings, run_id, org_id, user)
            await self.db.payslips.insert_one(payslip)
            total_gross += payslip["gross_salary"]
            total_deductions += payslip["total_deductions"]
            total_net += payslip["net_pay"]

        await self.db.payroll_runs.update_one(
            {"_id": run_result.inserted_id},
            {"$set": {"total_gross": round(total_gross, 2), "total_deductions": round(total_deductions, 2),
                      "total_net": round(total_net, 2), "employee_count": len(employees)}}
        )

        # Mark adjustments applied
        await self.db.payroll_adjustments.update_many(
            {"organization_id": org_id, "month": month, "year": year, "applied": False},
            {"$set": {"applied": True}}
        )

        logger.info(f"Payroll run: {month}/{year}, {len(employees)} employees, net={round(total_net, 2)}")
        return {"id": run_id, "month": month, "year": year, "status": "processed",
                "employee_count": len(employees), "total_gross": round(total_gross, 2),
                "total_net": round(total_net, 2), "payslips_generated": len(employees)}

    async def _build_payslip(self, emp, month, year, month_str, working_days, settings, run_id, org_id, user=None) -> dict:
        """Build payslip using engine functions — each step is separate"""
        emp_id = str(emp["_id"])
        ctc_annual = emp.get("salary_structure", {}).get("ctc", 0)
        monthly_ctc = round(ctc_annual / 12, 2)

        # Step 1: Earnings
        earnings = calculate_earnings(monthly_ctc, settings.get("salary_structure", {}))
        gross_salary = earnings["gross_salary"]
        basic = earnings["basic"]

        # Step 2: LOP days (attendance absent + approved LOP leaves)
        att_pipeline = [{"$match": {"employee_id": emp_id, "date": {"$regex": f"^{month_str}"}, "status": "absent"}}, {"$count": "c"}]
        att_r = await self.db.attendance.aggregate(att_pipeline).to_list(1)
        lop_att = att_r[0]["c"] if att_r else 0

        lop_leave_pipeline = [{"$match": {"employee_id": emp_id, "leave_type_code": "LOP", "status": "approved", "start_date": {"$regex": f"^{month_str}"}}}, {"$group": {"_id": None, "t": {"$sum": "$days"}}}]
        lop_l = await self.db.leave_requests.aggregate(lop_leave_pipeline).to_list(1)
        lop_leaves = int(lop_l[0]["t"]) if lop_l else 0

        lop_days = lop_att + lop_leaves
        days_worked = working_days - lop_days

        # Step 3: LOP deduction
        lop_result = calculate_lop(gross_salary, basic, monthly_ctc, lop_days, working_days, settings.get("lop", {}))
        lop_deduction = lop_result["lop_deduction"]
        gross_after_lop = lop_result["gross_after_lop"]

        # Step 4: PF (only if pf_applicable for this employee — None treated as True for existing employees)
        pf_settings = settings.get("pf", {})
        pf_applicable = emp.get("pf_applicable")
        if pf_applicable is False:  # explicitly set to False
            pf_result = {"employee_pf": 0, "employer_pf": 0}
        else:
            pf_result = calculate_pf(basic, pf_settings)

        # Step 5: ESI (only if esi_applicable for this employee — None treated as True)
        esi_settings = settings.get("esi", {})
        esi_applicable = emp.get("esi_applicable")
        if esi_applicable is False:  # explicitly set to False
            esi_result = {"employee_esi": 0, "employer_esi": 0}
        else:
            esi_result = calculate_esi(gross_after_lop, esi_settings)

        # Step 6: Professional Tax
        pt = calculate_pt(settings.get("professional_tax", {}))

        # Step 7: Manual adjustments
        adjustments = await self.db.payroll_adjustments.find(
            {"employee_id": emp_id, "month": month, "year": year, "applied": False}
        ).to_list(20)
        bonus = sum(a["amount"] for a in adjustments if a["type"] == "bonus")
        reimbursements = sum(a["amount"] for a in adjustments if a["type"] == "reimbursement")
        manual_deductions = sum(a["amount"] for a in adjustments if a["type"] == "deduction")

        # Total deductions
        total_deductions = round(pf_result["employee_pf"] + esi_result["employee_esi"] + pt + manual_deductions, 2)

        # Step 8: Net
        net_pay = calculate_net(gross_after_lop, total_deductions, bonus, reimbursements)

        # Employer cost
        total_employer_cost = round(pf_result["employer_pf"] + esi_result["employer_esi"], 2)

        # Bank details from onboarding
        bank = emp.get("bank_details") or {}

        # Build payslip
        return PayslipModel(
            organization_id=org_id, payroll_run_id=run_id,
            employee_id=emp_id, employee_name=f"{emp['first_name']} {emp['last_name']}",
            employee_code=emp.get("employee_id", ""), department=emp.get("department", ""),
            month=month, year=year, monthly_ctc=monthly_ctc,
            working_days=working_days, days_worked=days_worked, lop_days=lop_days,
            earnings={
                "basic": basic, "hra": earnings["hra"],
                "special_allowance": earnings["special_allowance"],
                "other_allowance": earnings["other_allowance"],
                "bonus": bonus, "reimbursements": reimbursements
            },
            gross_salary=gross_salary, lop_deduction=lop_deduction, gross_after_lop=gross_after_lop,
            deductions={
                "pf_employee": pf_result["employee_pf"],
                "esi_employee": esi_result["employee_esi"],
                "professional_tax": pt,
                "manual_deductions": manual_deductions,
                "total_deductions": total_deductions
            },
            total_deductions=total_deductions,
            employer_contributions={
                "pf_employer": pf_result["employer_pf"],
                "esi_employer": esi_result["employer_esi"],
                "total_employer_cost": total_employer_cost
            },
            total_employer_cost=total_employer_cost,
            # Phase 5 history fields
            pf_employee=pf_result["employee_pf"],
            esi_employee=esi_result["employee_esi"],
            professional_tax=pt,
            pf_employer=pf_result["employer_pf"],
            esi_employer=esi_result["employer_esi"],
            net_pay=net_pay,
            status="processed",
            generated_by=str(user["_id"]) if user else None,
            generated_by_name=user.get("full_name", user.get("email", "")) if user else None,
            generated_at=datetime.utcnow(),
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        ).model_dump()

    # ==================================================================
    # RUNS CRUD
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
        if not run: raise HTTPException(status_code=404, detail="Not found")
        _serialize(run)
        payslips = await self.db.payslips.find({"payroll_run_id": run_id}).to_list(500)
        for p in payslips: _serialize(p)
        run["payslips"] = payslips
        return run

    async def approve_run(self, run_id: str, user: dict) -> dict:
        org_id = self._org_id(user)
        try: obj_id = ObjectId(run_id)
        except: raise HTTPException(status_code=400, detail="Invalid ID")
        run = await self.db.payroll_runs.find_one({"_id": obj_id, "organization_id": org_id})
        if not run: raise HTTPException(status_code=404, detail="Not found")
        if run["status"] != "processed": raise HTTPException(status_code=400, detail=f"Cannot approve: {run['status']}")
        now = datetime.utcnow()
        await self.db.payroll_runs.update_one({"_id": obj_id}, {"$set": {"status": "approved", "approved_by": str(user["_id"]), "approved_by_name": user.get("full_name", ""), "approved_at": now}})
        await self.db.payslips.update_many({"payroll_run_id": run_id}, {"$set": {"status": "approved"}})
        updated = await self.db.payroll_runs.find_one({"_id": obj_id})
        return _serialize(updated)

    async def mark_paid(self, run_id: str, user: dict) -> dict:
        org_id = self._org_id(user)
        try: obj_id = ObjectId(run_id)
        except: raise HTTPException(status_code=400, detail="Invalid ID")
        run = await self.db.payroll_runs.find_one({"_id": obj_id, "organization_id": org_id})
        if not run: raise HTTPException(status_code=404, detail="Not found")
        if run["status"] != "approved": raise HTTPException(status_code=400, detail=f"Cannot pay: {run['status']}")
        now = datetime.utcnow()
        await self.db.payroll_runs.update_one({"_id": obj_id}, {"$set": {"status": "paid", "paid_at": now}})
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
        except: raise HTTPException(status_code=400, detail="Invalid ID")
        role = user.get("role")
        if role == "employee":
            emp = await self.db.employees.find_one({"user_id": str(user["_id"]), "is_deleted": False})
            if not emp: raise HTTPException(status_code=404, detail="Not found")
            payslip = await self.db.payslips.find_one({"_id": obj_id, "employee_id": str(emp["_id"])})
        else:
            payslip = await self.db.payslips.find_one({"_id": obj_id, "organization_id": self._org_id(user)})
        if not payslip: raise HTTPException(status_code=404, detail="Payslip not found")
        return _serialize(payslip)

    # ==================================================================
    # ADJUSTMENTS
    # ==================================================================

    async def add_adjustment(self, data: dict, user: dict, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        try: emp = await self.db.employees.find_one({"_id": ObjectId(data["employee_id"]), "organization_id": org_id, "is_deleted": False})
        except: raise HTTPException(status_code=400, detail="Invalid employee_id")
        if not emp: raise HTTPException(status_code=404, detail="Employee not found")
        adj = PayrollAdjustmentModel(
            organization_id=org_id, employee_id=data["employee_id"],
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
        if not payslips: return {"month": month, "year": year, "message": "No payroll data"}

        total_gross = sum(p.get("gross_salary", p.get("gross_pay", 0)) for p in payslips)
        total_net = sum(p["net_pay"] for p in payslips)
        total_deductions = sum(p["total_deductions"] for p in payslips)
        total_employer = sum(p.get("total_employer_cost", 0) for p in payslips)

        dept_map = {}
        for p in payslips:
            d = p.get("department", "Other")
            if d not in dept_map: dept_map[d] = {"gross": 0, "net": 0, "count": 0}
            dept_map[d]["gross"] += p.get("gross_salary", p.get("gross_pay", 0))
            dept_map[d]["net"] += p["net_pay"]
            dept_map[d]["count"] += 1

        return {"month": month, "year": year, "employee_count": len(payslips),
                "total_gross": round(total_gross, 2), "total_deductions": round(total_deductions, 2),
                "total_net": round(total_net, 2), "total_employer_cost": round(total_employer, 2),
                "avg_salary": round(total_net / len(payslips), 2),
                "department_breakdown": dept_map}

    async def report_annual(self, user: dict, employee_id: str, year: int = None, org_id_param: str = None) -> dict:
        org_id = self._org_id(user, org_id_param)
        if not year: year = datetime.utcnow().year
        try: emp = await self.db.employees.find_one({"_id": ObjectId(employee_id), "organization_id": org_id})
        except: raise HTTPException(status_code=400, detail="Invalid employee_id")
        if not emp: raise HTTPException(status_code=404, detail="Not found")
        payslips = await self.db.payslips.find({"employee_id": employee_id, "year": year}).sort("month", 1).to_list(12)
        month_wise = [{"month": p["month"], "gross": p.get("gross_salary", p.get("gross_pay", 0)), "deductions": p["total_deductions"], "net": p["net_pay"]} for p in payslips]
        total_gross = sum(p.get("gross_salary", p.get("gross_pay", 0)) for p in payslips)
        total_net = sum(p["net_pay"] for p in payslips)
        return {"employee_name": f"{emp['first_name']} {emp['last_name']}", "employee_code": emp.get("employee_id", ""),
                "year": year, "total_gross_annual": round(total_gross, 2), "total_net_annual": round(total_net, 2), "month_wise": month_wise}

    async def report_bank_transfer(self, user: dict, month: int = None, year: int = None, org_id_param: str = None) -> dict:
        """Bank transfer report — net pay + bank details for bulk payment"""
        org_id = self._org_id(user, org_id_param)
        if not year: year = datetime.utcnow().year
        if not month: month = datetime.utcnow().month

        payslips = await self.db.payslips.find(
            {"organization_id": org_id, "month": month, "year": year, "status": {"$in": ["approved", "paid"]}}
        ).to_list(500)

        transfers = []
        total_amount = 0
        for p in payslips:
            # Get bank details from employee
            emp = await self.db.employees.find_one({"_id": ObjectId(p["employee_id"])})
            bank = emp.get("bank_details", {}) if emp else {}

            transfers.append({
                "employee_id": p.get("employee_code", ""),
                "employee_name": p["employee_name"],
                "department": p["department"],
                "net_pay": p["net_pay"],
                "account_number": bank.get("account_number", ""),
                "ifsc": bank.get("ifsc", ""),
                "bank_name": bank.get("bank_name", ""),
                "status": p["status"]
            })
            total_amount += p["net_pay"]

        return {
            "month": month, "year": year,
            "total_employees": len(transfers),
            "total_amount": round(total_amount, 2),
            "transfers": transfers
        }

    async def report_salary_register(self, user: dict, month: int = None, year: int = None, department: str = None, org_id_param: str = None) -> dict:
        """Salary Register — all components for every employee in one table"""
        org_id = self._org_id(user, org_id_param)
        if not year: year = datetime.utcnow().year
        if not month: month = datetime.utcnow().month

        query = {"organization_id": org_id, "month": month, "year": year}
        if department: query["department"] = {"$regex": department, "$options": "i"}

        payslips = await self.db.payslips.find(query).sort("employee_name", 1).to_list(500)

        register = []
        for p in payslips:
            earnings = p.get("earnings", {})
            register.append({
                "employee_code": p.get("employee_code", ""),
                "employee_name": p["employee_name"],
                "department": p.get("department", ""),
                "monthly_ctc": p.get("monthly_ctc", 0),
                "basic": earnings.get("basic", 0),
                "hra": earnings.get("hra", 0),
                "special_allowance": earnings.get("special_allowance", 0),
                "other_allowance": earnings.get("other_allowance", 0),
                "bonus": earnings.get("bonus", 0),
                "reimbursements": earnings.get("reimbursements", 0),
                "gross_salary": p.get("gross_salary", p.get("gross_pay", 0)),
                "working_days": p.get("working_days", 0),
                "lop_days": p.get("lop_days", 0),
                "lop_deduction": p.get("lop_deduction", 0),
                "gross_after_lop": p.get("gross_after_lop", 0),
                "pf_employee": p.get("pf_employee", 0),
                "esi_employee": p.get("esi_employee", 0),
                "professional_tax": p.get("professional_tax", 0),
                "total_deductions": p.get("total_deductions", 0),
                "net_pay": p.get("net_pay", 0),
                "pf_employer": p.get("pf_employer", 0),
                "esi_employer": p.get("esi_employer", 0),
                "total_employer_cost": p.get("total_employer_cost", 0),
                "status": p.get("status", "")
            })

        return {"month": month, "year": year, "total_employees": len(register), "register": register}

    async def report_department_summary(self, user: dict, month: int = None, year: int = None, org_id_param: str = None) -> dict:
        """Department-wise payroll summary"""
        org_id = self._org_id(user, org_id_param)
        if not year: year = datetime.utcnow().year
        if not month: month = datetime.utcnow().month

        pipeline = [
            {"$match": {"organization_id": org_id, "month": month, "year": year}},
            {"$group": {
                "_id": "$department",
                "employee_count": {"$sum": 1},
                "total_gross": {"$sum": "$gross_salary"},
                "total_deductions": {"$sum": "$total_deductions"},
                "total_net": {"$sum": "$net_pay"},
                "total_pf": {"$sum": "$pf_employee"},
                "total_esi": {"$sum": "$esi_employee"},
                "total_pt": {"$sum": "$professional_tax"},
                "total_lop": {"$sum": "$lop_deduction"},
                "total_employer_cost": {"$sum": "$total_employer_cost"}
            }},
            {"$sort": {"_id": 1}}
        ]
        results = await self.db.payslips.aggregate(pipeline).to_list(50)

        departments = []
        for r in results:
            departments.append({
                "department": r["_id"],
                "employee_count": r["employee_count"],
                "total_gross": round(r["total_gross"], 2),
                "total_deductions": round(r["total_deductions"], 2),
                "total_net": round(r["total_net"], 2),
                "total_pf": round(r["total_pf"], 2),
                "total_esi": round(r["total_esi"], 2),
                "total_pt": round(r["total_pt"], 2),
                "total_lop": round(r["total_lop"], 2),
                "total_employer_cost": round(r["total_employer_cost"], 2)
            })

        return {"month": month, "year": year, "departments": departments}
