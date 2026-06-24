from fastapi import APIRouter, Depends, Query, Path, UploadFile, File, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.employees.schema import (
    EmployeeCreateRequest, EmployeeUpdateRequest,
    EmployeeCreateResponse, EmployeeListResponse,
    CSVImportResponse, OnboardingProgressResponse,
    SectionSubmitResponse, VerifyEmployeeRequest,
    OnboardingSectionRequest,
)
from app.v1.employees.service import EmployeeService

router = APIRouter()


def _require_hr_access(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


def _require_employee_or_hr(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") not in ("employee", "superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


def _require_any(current_user: dict = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# 1. Create employee
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=EmployeeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Employee (Manual Entry)",
    description="""
**Purpose:** HR manually adds a new employee. Creates the employee record,
generates a `employee` user account with password `Welcome1`, and sends
a welcome email with login credentials and onboarding instructions.

**Access:** `superadmin`, `org_admin`, `hr_admin`

- `org_admin` / `hr_admin` — organization is auto-inferred from token
- `superadmin` — must supply `organization_id` in the request body

**Checks before creating:**
- `employee_id` must be unique within the organization
- `official_email` must be unique across all employees
- `emp_count_for_access` limit must not be exceeded

**Request Body (experienced employee):**
```json
{
  "employee_id": "EMP001",
  "first_name": "Rahul",
  "last_name": "Verma",
  "official_email": "rahul@techsolutions.com",
  "phone": "+919876543210",
  "department": "Engineering",
  "designation": "Senior Developer",
  "reporting_manager": "Vikram Singh",
  "joining_date": "2025-07-01",
  "employment_type": "full-time",
  "shift": "General",
  "work_location": "Hyderabad Office",
  "is_fresher": false,
  "salary_structure": {
    "basic": 50000,
    "hra": 20000,
    "special_allowance": 15000,
    "ctc": 1200000
  }
}
```

**Request Body (fresher — no UAN needed):**
```json
{
  "employee_id": "EMP002",
  "first_name": "Ananya",
  "last_name": "Singh",
  "official_email": "ananya@techsolutions.com",
  "phone": "+919876543221",
  "department": "Engineering",
  "designation": "Junior Developer",
  "joining_date": "2025-08-01",
  "is_fresher": true,
  "salary_structure": {
    "basic": 25000,
    "hra": 10000,
    "special_allowance": 5000,
    "ctc": 480000
  }
}
```

| Field | Required | Notes |
|---|---|---|
| employee_id | ✅ | Company-specific ID like EMP001 |
| first_name, last_name | ✅ | |
| official_email | ✅ | Used as login email |
| phone | ✅ | |
| department | ✅ | Department name (text, not ID) |
| designation | ✅ | Job title |
| joining_date | ✅ | Format: YYYY-MM-DD |
| salary_structure.basic, .ctc | ✅ | |
| is_fresher | ✅ | `true` = fresher, `false` = has prior work experience. **UAN will be collected in government_ids onboarding section** |
| reporting_manager | ❌ | Manager name |
| shift, work_location | ❌ | |
| employment_type | ❌ | `full-time` (default) / `part-time` / `contract` |
| organization_id | ❌ | Required only for superadmin |

**Response 201:**
```json
{
  "id": "65abc...",
  "employee_id": "EMP001",
  "status": "pending_onboarding",
  "onboarding_progress": 0,
  "invite_sent": true,
  "created_at": "2025-07-01T09:00:00"
}
```

**Employee status after creation:** `pending_onboarding`

**Errors:**
- `400` — Duplicate employee_id or email, missing organization_id for superadmin
- `403` — Access denied or employee limit reached
- `404` — Organization not found
""",
)
async def create_employee(
    data: EmployeeCreateRequest,
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await EmployeeService(db).create_employee(data, current_user)


# ---------------------------------------------------------------------------
# 2. CSV import
# ---------------------------------------------------------------------------
@router.post(
    "/import",
    response_model=CSVImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import Employees via CSV",
    description="""
**Purpose:** Bulk-create employees by uploading a CSV file.
Valid rows are imported; invalid/duplicate rows are reported with reasons.

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Content-Type:** `multipart/form-data` — upload file in field named `file`.

**Required CSV Columns:**
`employee_id`, `first_name`, `last_name`, `official_email`, `phone`, `department`, `designation`, `joining_date`, `ctc`

**Optional CSV Columns:**
`reporting_manager`, `employment_type`

**CSV Template:**
```
employee_id,first_name,last_name,official_email,phone,department,designation,joining_date,ctc
EMP010,Arjun,Nair,arjun@company.com,+919876500001,Engineering,Developer,2025-08-01,800000
EMP011,Sneha,Rao,sneha@company.com,+919876500002,HR,HR Executive,2025-08-01,500000
```

**Per-row logic:**
- Each valid row → employee record created + user account created + welcome email sent
- Duplicate `employee_id` or `email` → row skipped, reported as error
- Missing required fields → row skipped, reported as error

**Response 201:**
```json
{
  "imported": 8,
  "failed": 2,
  "errors": [
    { "row": 3, "employee_id": "EMP003", "email": "x@y.com", "error": "Duplicate: email already exists" },
    { "row": 7, "employee_id": "EMP007", "email": "", "error": "Missing required fields: ['phone']" }
  ]
}
```

**Errors:**
- `400` — File is not a CSV or has no headers / missing required columns
- `403` — Access denied or employee limit reached
""",
)
async def import_employees_csv(
    file: UploadFile = File(..., description="CSV file with employee data"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    return await EmployeeService(db).import_employees_csv(file, current_user)


# ---------------------------------------------------------------------------
# 3. List employees
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=EmployeeListResponse,
    summary="List Employees",
    description="""
**Purpose:** Get a paginated list of employees in the organization with optional filters.

**Access:** `superadmin`, `org_admin`, `hr_admin`

- `org_admin` / `hr_admin` — sees only their own organization's employees
- `superadmin` — must pass `?organization_id=<id>` to specify which org

**Query Parameters:**
| Param | Type | Default | Description |
|---|---|---|---|
| organization_id | string | null | Required for superadmin |
| page | int | 1 | Page number |
| limit | int | 10 | Items per page (max 100) |
| status | string | null | Filter: `pending_onboarding` / `onboarding_in_progress` / `active` / `inactive` |
| department | string | null | Filter by department name (partial match) |
| search | string | null | Search by name, email, employee_id, or designation |
| include_deleted | bool | false | Show soft-deleted employees too |

**Response 200:**
```json
{
  "employees": [
    {
      "id": "65abc...",
      "employee_id": "EMP001",
      "first_name": "Rahul",
      "last_name": "Verma",
      "official_email": "rahul@techsolutions.com",
      "phone": "+919876543210",
      "department": "Engineering",
      "designation": "Senior Developer",
      "status": "onboarding_in_progress",
      "onboarding_progress": 72,
      "joining_date": "2025-07-01",
      "created_at": "2025-06-20T09:00:00"
    }
  ],
  "total": 50,
  "page": 1,
  "limit": 10,
  "pages": 5
}
```
""",
)
async def get_employees(
    organization_id: Optional[str] = Query(None, description="Required for superadmin"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="pending_onboarding | onboarding_in_progress | active | inactive"),
    department: Optional[str] = Query(None, description="Filter by department name"),
    search: Optional[str] = Query(None, description="Search name / email / employee_id / designation"),
    include_deleted: bool = Query(False, description="Include soft-deleted employees"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await EmployeeService(db).get_employees(
        current_user, page, limit, status, department, search, include_deleted, organization_id
    )


# ---------------------------------------------------------------------------
# 4. Get single employee
# ---------------------------------------------------------------------------
@router.get(
    "/{employee_id}",
    summary="Get Employee Full Profile",
    description="""
**Purpose:** Get the complete profile of an employee including all onboarding details.

**Access:**
- `superadmin` — any employee across all orgs
- `org_admin`, `hr_admin` — only employees in their own organization
- `employee` — only their own record

**Path Parameter:** `employee_id` — MongoDB ObjectId of the employee.

**Response 200:**
```json
{
  "id": "65abc...",
  "employee_id": "EMP001",
  "first_name": "Rahul",
  "last_name": "Verma",
  "official_email": "rahul@techsolutions.com",
  "department": "Engineering",
  "designation": "Senior Developer",
  "status": "onboarding_in_progress",
  "onboarding_progress": 72,
  "salary_structure": { "basic": 50000, "hra": 20000, "special_allowance": 15000, "ctc": 1200000 },
  "onboarding_sections": {
    "personal_details": { "status": "completed", "verified": true },
    "address": { "status": "completed", "verified": false },
    "bank_details": { "status": "completed", "verified": false },
    "government_ids": { "status": "pending", "verified": false },
    ...
  },
  "personal_details": { "date_of_birth": "1995-03-15", "gender": "male", ... },
  "address": { "current": { "line1": "...", "city": "Hyderabad", ... } },
  "bank_details": { "account_number": "...", "ifsc": "..." },
  ...
}
```

**Errors:**
- `400` — Invalid ID format
- `403` — Access denied
- `404` — Employee not found
""",
)
async def get_employee(
    employee_id: str = Path(..., description="Employee MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_any)
):
    return await EmployeeService(db).get_employee_by_id(employee_id, current_user)


# ---------------------------------------------------------------------------
# 5. Update employee (HR fields)
# ---------------------------------------------------------------------------
@router.put(
    "/{employee_id}",
    summary="Update Employee (HR Fields Only)",
    description="""
**Purpose:** HR updates administrative fields of an employee. Only HR-controlled fields
can be changed here. Employee personal/onboarding data is submitted by the employee themselves.

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Path Parameter:** `employee_id` — MongoDB ObjectId of the employee.

**Request Body (all fields optional):**
```json
{
  "department": "Product",
  "designation": "Product Manager",
  "reporting_manager": "Priya Sharma",
  "shift": "General",
  "work_location": "Bangalore Office",
  "employment_type": "full-time",
  "salary_structure": {
    "basic": 60000,
    "hra": 24000,
    "special_allowance": 18000,
    "ctc": 1440000
  },
  "status": "active"
}
```

| Field | Notes |
|---|---|
| department | Department name |
| designation | Job title |
| reporting_manager | Manager name |
| shift | Work shift (General / Morning / Night) |
| work_location | Office location |
| employment_type | `full-time` / `part-time` / `contract` |
| salary_structure | Full object required if updating salary |
| status | `pending_onboarding` / `onboarding_in_progress` / `active` / `inactive` |

**Response 200:** Full updated employee object.

**Errors:**
- `400` — No fields provided or invalid ID
- `403` — Access denied
- `404` — Employee not found
""",
)
async def update_employee(
    data: EmployeeUpdateRequest,
    employee_id: str = Path(..., description="Employee MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await EmployeeService(db).update_employee(employee_id, data, current_user)


# ---------------------------------------------------------------------------
# 6. Submit onboarding section
# ---------------------------------------------------------------------------
@router.put(
    "/me/onboarding/{section}",
    response_model=SectionSubmitResponse,
    summary="Submit Onboarding Section",
    description="""
**Purpose:** Submit one section of the employee onboarding profile.
Progress is recalculated after each submission.
When all 9 sections are completed, status auto-changes to `onboarding_in_progress` (awaiting HR approval).

**Access:**
- `employee` — submits their own sections (no query param needed, identity from token)
- `org_admin`, `hr_admin`, `superadmin` — fills on behalf of employee (must pass `?employee_id=<id>`)

**Path Parameter `section`** — one of:

| Section | What employee fills |
|---|---|
| `personal_details` | Date of birth, gender, blood group, marital status |
| `address` | Current address + permanent address |
| `emergency_contact` | Emergency contact name, relation, phone |
| `bank_details` | ⚠️ Critical — Account number, IFSC, bank name |
| `government_ids` | ⚠️ Critical — PAN, Aadhaar, Passport, UAN (all optional) |
| `education` | List of degrees with institution, year, grade |
| `experience` | List of past jobs with company, dates |
| `documents` | List of uploaded documents (Cloudinary URLs) |
| `policy_acceptance` | Accept company policies (must be `true`) |

⚠️ `bank_details` and `government_ids` are **critical sections** — HR must verify these
before the employee can be approved/activated.

**Request Body** — always wrapped in a `data` key:

**personal_details:**
```json
{ "data": { "date_of_birth": "1995-03-15", "gender": "male", "blood_group": "O+", "marital_status": "single" } }
```

**address:**
```json
{
  "data": {
    "current": { "line1": "Flat 4B Sunrise Apts", "city": "Hyderabad", "state": "Telangana", "pincode": "500032" },
    "permanent": { "line1": "12 Gandhi Nagar", "city": "Vizag", "state": "AP", "pincode": "530002" }
  }
}
```

**emergency_contact:**
```json
{ "data": { "name": "Priya Verma", "relation": "Spouse", "phone": "+919876543211" } }
```

**bank_details:**
```json
{ "data": { "account_number": "123456789012", "ifsc": "HDFC0001234", "bank_name": "HDFC Bank", "branch": "Madhapur", "account_type": "savings" } }
```

**government_ids:** ⚠️ Critical — HR must verify
```json
{
  "data": {
    "pan":      { "number": "ABCDE1234F",      "document_url": "https://res.cloudinary.com/dxbjp7jno/..." },
    "aadhaar":  { "number": "1234 5678 9012",  "document_url": "https://res.cloudinary.com/dxbjp7jno/..." },
    "passport": { "number": "N1234567",         "document_url": "https://res.cloudinary.com/dxbjp7jno/..." },
    "uan":      { "number": "100123456789",     "document_url": null }
  }
}
```
> ℹ️ All government IDs including `uan` are **optional**. The `is_fresher` field helps frontend show/hide UAN field as needed.

**education:**
```json
{
  "data": {
    "entries": [
      { "degree": "B.Tech", "institution": "JNTU Hyderabad", "field_of_study": "CSE", "start_year": 2013, "end_year": 2017, "grade": "8.5 CGPA" }
    ]
  }
}
```

**experience:**
```json
{
  "data": {
    "entries": [
      { "company": "TechCorp Pvt Ltd", "designation": "Developer", "start_date": "2017-07-01", "end_date": "2022-06-30", "is_current": false, "document_url": "https://res.cloudinary.com/..." }
    ]
  }
}
```
> ℹ️ `is_fresher` flag (set during creation by HR):
> - **Experienced** (`is_fresher: false`) → at least 1 experience entry required. UAN is optional.
> - **Fresher** (`is_fresher: true`) → send `"entries": []` (empty array). UAN is optional.

**documents:**
```json
{
  "data": {
    "entries": [
      { "name": "Offer Letter", "document_url": "https://res.cloudinary.com/dxbjp7jno/..." },
      { "name": "10th Marksheet", "document_url": "https://res.cloudinary.com/dxbjp7jno/..." }
    ]
  }
}
```

**policy_acceptance:**
```json
{ "data": { "accepted": true } }
```

**Response 200:**
```json
{
  "section": "bank_details",
  "status": "completed",
  "overall_progress": 78,
  "filled_by": "employee"
}
```

**Query Parameter for HR use:**
`?employee_id=<MongoDB ObjectId>` — required when HR fills on behalf of employee.

**Errors:**
- `400` — Invalid section name, policy not accepted, HR missing employee_id
- `403` — Employee is inactive
- `404` — Employee record not found
""",
)
async def submit_onboarding_section(
    body: OnboardingSectionRequest,
    section: str = Path(..., description="Section name — see description for all valid values"),
    employee_id: Optional[str] = Query(None, description="HR only: MongoDB ObjectId of the target employee"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    from app.models.employee import ONBOARDING_SECTIONS
    if section not in ONBOARDING_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section '{section}'. Valid: {ONBOARDING_SECTIONS}"
        )
    if current_user.get("role") != "employee" and not employee_id:
        raise HTTPException(
            status_code=400,
            detail="HR must supply ?employee_id=<id> to fill on behalf of an employee"
        )
    return await EmployeeService(db).submit_onboarding_section(
        section, body.data, current_user, target_employee_id=employee_id
    )


# ---------------------------------------------------------------------------
# 7. Get onboarding progress
# ---------------------------------------------------------------------------
@router.get(
    "/me/onboarding",
    response_model=OnboardingProgressResponse,
    summary="Get Onboarding Progress",
    description="""
**Purpose:** View the onboarding checklist status — which sections are done, pending, or need revision.
Frontend uses the `is_fresher` flag from this response to show or hide the experience section.

**Access:**
- `employee` — views their own progress (no query param needed)
- `org_admin`, `hr_admin`, `superadmin` — must pass `?employee_id=<id>` to view a specific employee

**Query Parameter for HR:**
`?employee_id=<MongoDB ObjectId>` — required for HR/admin roles.

**Response 200:**
```json
{
  "status": "onboarding_in_progress",
  "progress": 78,
  "is_fresher": false,
  "sections": {
    "personal_details":  { "status": "completed", "verified": true },
    "address":           { "status": "completed", "verified": false },
    "emergency_contact": { "status": "completed", "verified": false },
    "bank_details":      { "status": "completed", "verified": false },
    "government_ids":    { "status": "needs_revision", "verified": false },
    "education":         { "status": "completed", "verified": true },
    "experience":        { "status": "pending", "verified": false },
    "documents":         { "status": "pending", "verified": false },
    "policy_acceptance": { "status": "completed", "verified": true }
  },
  "hr_notes": "PAN card image is blurry, please re-upload"
}
```

**`is_fresher` flag — frontend logic:**
- `is_fresher: true` → hide experience section (fresher, no prior jobs). UAN is optional.
- `is_fresher: false` → show experience section, at least 1 entry required. UAN is optional.

**Section status values:**
- `pending` — not yet submitted
- `completed` — submitted by employee
- `needs_revision` — HR requested changes (employee must re-submit)

**Errors:**
- `400` — HR missing employee_id
- `404` — Employee record not found
""",
)
async def get_my_onboarding(
    employee_id: Optional[str] = Query(None, description="HR only: MongoDB ObjectId of the target employee"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_employee_or_hr)
):
    if current_user.get("role") != "employee" and not employee_id:
        raise HTTPException(status_code=400, detail="HR must supply ?employee_id=<id>")
    return await EmployeeService(db).get_my_onboarding(current_user, target_employee_id=employee_id)


# ---------------------------------------------------------------------------
# 8. Verify / Approve employee
# ---------------------------------------------------------------------------
@router.patch(
    "/{employee_id}/verify",
    summary="Verify / Approve Employee (HR Action)",
    description="""
**Purpose:** HR performs one of three actions on an employee's onboarding.

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Path Parameter:** `employee_id` — MongoDB ObjectId of the employee.

---

### Action 1: `approve` — Activate the employee

All 9 sections must be `completed` AND `bank_details` + `government_ids` must be `verified`.
Sets employee status to `active`. Employee can now access full HRMS features.

**Request Body:**
```json
{ "action": "approve" }
```

**Response 200:**
```json
{ "status": "active", "message": "Employee approved and activated" }
```

---

### Action 2: `verify_section` — Mark one section as HR-verified

Use this after reviewing a section like bank details or government IDs.

**Request Body:**
```json
{ "action": "verify_section", "section": "bank_details" }
```

Valid sections for verification: `bank_details`, `government_ids` (critical), or any other section.

**Response 200:**
```json
{ "status": "verified", "section": "bank_details", "message": "Section 'bank_details' verified successfully" }
```

---

### Action 3: `request_changes` — Ask employee to fix sections

Marks specified sections as `needs_revision` and sends notification email to the employee.

**Request Body:**
```json
{
  "action": "request_changes",
  "sections": ["government_ids", "experience"],
  "notes": "PAN card image is blurry, please re-upload. Experience certificate missing."
}
```

**Response 200:**
```json
{
  "status": "changes_requested",
  "sections": ["government_ids", "experience"],
  "message": "Employee notified to update the specified sections"
}
```

---

**Errors:**
- `400` — Missing required fields, section not completed yet, incomplete sections for approve
- `403` — Access denied or critical sections not verified for approve
- `404` — Employee not found
""",
)
async def verify_employee(
    data: VerifyEmployeeRequest,
    employee_id: str = Path(..., description="Employee MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await EmployeeService(db).verify_employee(employee_id, data, current_user)


# ---------------------------------------------------------------------------
# 9. Deactivate employee
# ---------------------------------------------------------------------------
@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_200_OK,
    summary="Deactivate Employee (Soft Delete)",
    description="""
**Purpose:** Soft delete an employee. Data is retained but the employee is deactivated.

**Access:** `superadmin`, `org_admin`, `hr_admin`

**Path Parameter:** `employee_id` — MongoDB ObjectId of the employee.

**Request Body:** None.

**What happens:**
- Employee record: `is_deleted = true`, `status = inactive`, `deleted_at` recorded
- Linked user account: `is_active = false` (employee cannot login)
- Employee disappears from default list (use `include_deleted=true` to see them)

**Response 200:**
```json
{ "message": "Employee deactivated successfully", "employee_id": "65abc..." }
```

**Errors:**
- `400` — Invalid ID format
- `403` — Access denied
- `404` — Employee not found or already deleted
""",
)
async def delete_employee(
    employee_id: str = Path(..., description="Employee MongoDB ObjectId"),
    db=Depends(get_database),
    current_user: dict = Depends(_require_hr_access)
):
    return await EmployeeService(db).delete_employee(employee_id, current_user)
