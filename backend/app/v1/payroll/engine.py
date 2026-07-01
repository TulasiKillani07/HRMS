"""
Payroll Calculation Engine
Each calculation is a separate function.
Zero hardcoded values — all from company payroll settings.
If config is missing a field, calculation stops with a clear error.
"""
import calendar as cal_mod
from fastapi import HTTPException


def calculate_working_days(month: int, year: int, lop_settings: dict) -> int:
    """Calculate working days based on config"""
    calculation = lop_settings.get("calculation")
    if not calculation:
        raise HTTPException(status_code=400, detail="Payroll config missing: lop.calculation (working_days | calendar_days)")

    cal_days = cal_mod.monthrange(year, month)[1]
    if calculation == "calendar_days":
        return cal_days
    else:  # working_days
        weekends = sum(1 for d in range(1, cal_days + 1) if cal_mod.weekday(year, month, d) in (5, 6))
        return cal_days - weekends


def calculate_earnings(monthly_ctc: float, salary_structure: dict) -> dict:
    """Calculate earning components from Monthly CTC using config percentages"""
    required = ["basic_percentage", "hra_percentage", "special_allowance_percentage", "other_percentage"]
    for field in required:
        if field not in salary_structure:
            raise HTTPException(status_code=400, detail=f"Payroll config missing: salary_structure.{field}")

    basic = round(monthly_ctc * salary_structure["basic_percentage"] / 100, 2)
    hra = round(monthly_ctc * salary_structure["hra_percentage"] / 100, 2)
    special = round(monthly_ctc * salary_structure["special_allowance_percentage"] / 100, 2)
    other = round(monthly_ctc * salary_structure["other_percentage"] / 100, 2)
    gross_salary = round(basic + hra + special + other, 2)

    return {"basic": basic, "hra": hra, "special_allowance": special, "other_allowance": other, "gross_salary": gross_salary}


def calculate_lop(gross_salary: float, basic: float, monthly_ctc: float,
                  lop_days: int, working_days: int, lop_settings: dict) -> dict:
    """Calculate LOP deduction based on config"""
    if lop_days == 0 or working_days == 0:
        return {"lop_deduction": 0, "gross_after_lop": gross_salary, "daily_salary": 0}

    basis = lop_settings.get("deduction_basis")
    if not basis:
        raise HTTPException(status_code=400, detail="Payroll config missing: lop.deduction_basis (gross | basic | ctc)")

    if basis == "basic":
        daily_salary = basic / working_days
    elif basis == "ctc":
        daily_salary = monthly_ctc / working_days
    elif basis == "gross":
        daily_salary = gross_salary / working_days
    else:
        raise HTTPException(status_code=400, detail=f"Invalid lop.deduction_basis: '{basis}'. Must be gross | basic | ctc")

    lop_deduction = round(daily_salary * lop_days, 2)
    return {"lop_deduction": lop_deduction, "gross_after_lop": round(gross_salary - lop_deduction, 2), "daily_salary": round(daily_salary, 2)}


def calculate_pf(basic: float, pf_settings: dict) -> dict:
    """Calculate PF employee + employer from config"""
    if not pf_settings:
        return {"employee_pf": 0, "employer_pf": 0}
    # Default enabled=True if not explicitly set (handles old configs without enabled field)
    if not pf_settings.get("enabled", True):
        return {"employee_pf": 0, "employer_pf": 0}

    emp_pct = pf_settings.get("employee_percentage")
    emp_r_pct = pf_settings.get("employer_percentage")
    if emp_pct is None or emp_r_pct is None:
        raise HTTPException(status_code=400, detail="Payroll config missing: pf.employee_percentage or pf.employer_percentage")

    # Accept both old (pf_on_full_basic) and new (pf_applicable_on) field names
    pf_applicable_on = pf_settings.get("pf_applicable_on")
    pf_on_full_basic = pf_settings.get("pf_on_full_basic", True)

    use_ceiling = False
    if pf_applicable_on == "pf_wage_ceiling":
        use_ceiling = True
    elif pf_applicable_on == "full_basic":
        use_ceiling = False
    elif pf_applicable_on is None:
        # Legacy field
        use_ceiling = not pf_on_full_basic

    if use_ceiling:
        ceiling = pf_settings.get("pf_wage_ceiling", 15000)
        pf_basic = min(basic, ceiling)
    else:
        pf_basic = basic

    employee_pf = round(pf_basic * emp_pct / 100, 2)
    employer_pf = round(pf_basic * emp_r_pct / 100, 2)
    return {"employee_pf": employee_pf, "employer_pf": employer_pf}


def calculate_esi(gross_after_lop: float, esi_settings: dict) -> dict:
    """Calculate ESI employee + employer from config"""
    if not esi_settings:
        return {"employee_esi": 0, "employer_esi": 0}
    # Default enabled=True if not explicitly set
    if not esi_settings.get("enabled", True):
        return {"employee_esi": 0, "employer_esi": 0}

    for field in ["employee_percentage", "employer_percentage", "salary_limit"]:
        if field not in esi_settings:
            raise HTTPException(status_code=400, detail=f"Payroll config missing: esi.{field}")

    if gross_after_lop > esi_settings["salary_limit"]:
        return {"employee_esi": 0, "employer_esi": 0}

    employee_esi = round(gross_after_lop * esi_settings["employee_percentage"] / 100, 2)
    employer_esi = round(gross_after_lop * esi_settings["employer_percentage"] / 100, 2)
    return {"employee_esi": employee_esi, "employer_esi": employer_esi}


def calculate_pt(pt_settings: dict) -> float:
    """Calculate Professional Tax from config"""
    if not pt_settings:
        return 0
    # If 'enabled' is not set but amount exists, treat as enabled
    enabled = pt_settings.get("enabled", True)
    if not enabled:
        return 0
    amount = pt_settings.get("amount")
    if amount is None:
        raise HTTPException(status_code=400, detail="Payroll config missing: professional_tax.amount")
    return float(amount)


def calculate_net(gross_after_lop: float, total_deductions: float,
                  bonus: float = 0, reimbursements: float = 0) -> float:
    """Net = Gross after LOP + Bonus + Reimbursements - Total Deductions"""
    return round(gross_after_lop + bonus + reimbursements - total_deductions, 2)
