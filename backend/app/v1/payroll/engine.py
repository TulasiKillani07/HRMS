"""
Payroll Calculation Engine
Each calculation is a separate function.
No hardcoded values — everything from company settings.
"""
import calendar as cal_mod


def calculate_working_days(month: int, year: int) -> int:
    """Calculate working days (exclude weekends)"""
    cal_days = cal_mod.monthrange(year, month)[1]
    weekends = sum(1 for d in range(1, cal_days + 1) if cal_mod.weekday(year, month, d) in (5, 6))
    return cal_days - weekends


def calculate_earnings(monthly_ctc: float, salary_structure) -> dict:
    """Calculate earning components from CTC — handles both old and new config format"""
    if isinstance(salary_structure, dict):
        basic_pct = salary_structure.get("basic_percentage", 40)
        hra_pct = salary_structure.get("hra_percentage", 20)
        special_pct = salary_structure.get("special_allowance_percentage", 15)
        other_pct = salary_structure.get("other_percentage", 0)
    else:
        basic_pct, hra_pct, special_pct, other_pct = 40, 20, 15, 0

    basic = round(monthly_ctc * basic_pct / 100, 2)
    hra = round(monthly_ctc * hra_pct / 100, 2)
    special = round(monthly_ctc * special_pct / 100, 2)
    other = round(monthly_ctc * other_pct / 100, 2)

    return {
        "basic": basic, "hra": hra, "special_allowance": special,
        "other_allowance": other, "gross_salary": round(basic + hra + special + other, 2)
    }


def calculate_lop(gross_salary: float, basic: float, monthly_ctc: float,
                  lop_days: int, working_days: int, lop_settings) -> dict:
    """Calculate LOP deduction — handles both old and new config format"""
    if lop_days == 0 or working_days == 0:
        return {"lop_deduction": 0, "gross_after_lop": gross_salary, "daily_salary": 0}

    if isinstance(lop_settings, dict):
        basis = lop_settings.get("deduction_basis", "gross")
    else:
        basis = "gross"

    if basis == "basic":
        daily_salary = basic / working_days
    elif basis == "ctc":
        daily_salary = monthly_ctc / working_days
    else:
        daily_salary = gross_salary / working_days

    lop_deduction = round(daily_salary * lop_days, 2)
    gross_after_lop = round(gross_salary - lop_deduction, 2)

    return {
        "lop_deduction": lop_deduction,
        "gross_after_lop": gross_after_lop,
        "daily_salary": round(daily_salary, 2)
    }


def calculate_pf(basic: float, pf_settings) -> dict:
    """Calculate PF (employee + employer) — supports pf_applicable_on: full_basic | pf_wage_ceiling"""
    if isinstance(pf_settings, dict) and "enabled" in pf_settings:
        if not pf_settings.get("enabled", False):
            return {"employee_pf": 0, "employer_pf": 0}
        pf_applicable_on = pf_settings.get("pf_applicable_on", "full_basic")
        ceiling = pf_settings.get("pf_wage_ceiling", 15000)
        if pf_applicable_on == "pf_wage_ceiling" and ceiling > 0:
            pf_basic = min(basic, ceiling)
        else:
            pf_basic = basic  # full_basic
        employee_pf = round(pf_basic * pf_settings.get("employee_percentage", 12) / 100, 2)
        employer_pf = round(pf_basic * pf_settings.get("employer_percentage", 12) / 100, 2)
        return {"employee_pf": employee_pf, "employer_pf": employer_pf}
    pf_pct = pf_settings if isinstance(pf_settings, (int, float)) else 12
    employee_pf = round(basic * pf_pct / 100, 2)
    return {"employee_pf": employee_pf, "employer_pf": employee_pf}


def calculate_esi(gross_after_lop: float, esi_settings) -> dict:
    """Calculate ESI (employee + employer) — handles both old flat config and new dict format"""
    if isinstance(esi_settings, dict) and "enabled" in esi_settings:
        if not esi_settings.get("enabled", False):
            return {"employee_esi": 0, "employer_esi": 0}
        limit = esi_settings.get("salary_limit", 21000)
        if gross_after_lop > limit:
            return {"employee_esi": 0, "employer_esi": 0}
        employee_esi = round(gross_after_lop * esi_settings.get("employee_percentage", 0.75) / 100, 2)
        employer_esi = round(gross_after_lop * esi_settings.get("employer_percentage", 3.25) / 100, 2)
        return {"employee_esi": employee_esi, "employer_esi": employer_esi}
    # Legacy: no ESI config
    return {"employee_esi": 0, "employer_esi": 0}


def calculate_pt(pt_settings) -> float:
    """Calculate Professional Tax — handles both int (legacy) and dict format"""
    if isinstance(pt_settings, (int, float)):
        return float(pt_settings)
    if not pt_settings:
        return 0
    if not pt_settings.get("enabled", False):
        return 0
    return pt_settings.get("amount", 200)


def calculate_net(gross_after_lop: float, total_deductions: float,
                  bonus: float = 0, reimbursements: float = 0) -> float:
    """Calculate net salary"""
    return round(gross_after_lop + bonus + reimbursements - total_deductions, 2)
