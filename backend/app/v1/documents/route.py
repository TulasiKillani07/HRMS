from fastapi import APIRouter, Depends, Query, Path, Form, UploadFile, File, status, HTTPException
from typing import Optional
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.documents.service import DocumentService

router = APIRouter()

def _hr(u: dict = Depends(get_current_user)):
    if u.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return u

def _emp(u: dict = Depends(get_current_user)):
    if u.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Only employees")
    return u

def _any(u: dict = Depends(get_current_user)):
    return u


# ===========================================================================
# COMPANY DOCUMENTS
# ===========================================================================

@router.post("/company", status_code=201, summary="Upload Company Document", description="""
**Purpose:** HR uploads a document (policy, handbook, template) visible to all or specific departments.

**Access:** `org_admin`, `hr_admin`

**Content-Type:** `multipart/form-data`

| Field | Required | Notes |
|---|---|---|
| file | ✅ | PDF, DOCX, etc. |
| title | ✅ | Display name |
| category | ❌ | policy / handbook / template / form / other |
| description | ❌ | Brief description |
| target_departments | ❌ | JSON array string, e.g. '["Engineering"]'. Empty = all |
| is_mandatory | ❌ | true if employees must acknowledge |
""")
async def upload_company_doc(
    file: UploadFile = File(...), title: str = Form(...),
    category: str = Form("other"), description: str = Form(""),
    target_departments: str = Form(""), is_mandatory: bool = Form(False),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)
):
    return await DocumentService(db).upload_company_doc(
        file, title, category, description, target_departments, is_mandatory, current_user, organization_id)


@router.get("/company", summary="List Company Documents", description="""
**Purpose:** Get company documents. Employees see only those shared with their department.

**Access:** All authenticated users

**Query:** page, limit, category, search
""")
async def list_company_docs(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=50),
    category: Optional[str] = Query(None), search: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_any)):
    return await DocumentService(db).list_company_docs(current_user, page, limit, category, search, organization_id)


@router.patch("/company/{document_id}/acknowledge", summary="Acknowledge Document", description="""
**Purpose:** Employee acknowledges they've read a mandatory company document.

**Access:** `employee`
""")
async def acknowledge_doc(document_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_any)):
    return await DocumentService(db).acknowledge_doc(document_id, current_user)


@router.put("/company/{document_id}", summary="Update Company Document", description="""
**Purpose:** Update document metadata.

**Access:** `org_admin`, `hr_admin`

**Request Body (JSON, all optional):** title, description, category, target_departments, is_mandatory
""")
async def update_company_doc(document_id: str = Path(...),
    title: Optional[str] = None, description: Optional[str] = None,
    category: Optional[str] = None, target_departments: Optional[str] = None,
    is_mandatory: Optional[bool] = None,
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    import json as j
    data = {}
    if title: data["title"] = title
    if description is not None: data["description"] = description
    if category: data["category"] = category
    if target_departments:
        try: data["target_departments"] = j.loads(target_departments)
        except: pass
    if is_mandatory is not None: data["is_mandatory"] = is_mandatory
    return await DocumentService(db).update_company_doc(document_id, data, current_user)


@router.delete("/company/{document_id}", summary="Delete Company Document", description="""
**Purpose:** Soft-delete a company document.

**Access:** `org_admin`, `hr_admin`
""")
async def delete_company_doc(document_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await DocumentService(db).delete_company_doc(document_id, current_user)


# ===========================================================================
# EMPLOYEE DOCUMENTS
# ===========================================================================

@router.post("/employee", status_code=201, summary="Upload Employee Document", description="""
**Purpose:** Upload a personal document for/by an employee (offer letter, certificates, etc.)

**Access:**
- `employee` — uploads own docs
- `org_admin`, `hr_admin` — uploads for any employee (pass employee_id)

**Content-Type:** `multipart/form-data`

| Field | Required | Notes |
|---|---|---|
| file | ✅ | Document file |
| title | ✅ | e.g. "Offer Letter", "B.Tech Certificate" |
| category | ❌ | offer_letter / experience_letter / certificate / id_proof / other |
| employee_id | ❌ | Required when HR uploads for an employee |
""")
async def upload_employee_doc(
    file: UploadFile = File(...), title: str = Form(...),
    category: str = Form("other"), employee_id: str = Form(""),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_any)
):
    return await DocumentService(db).upload_employee_doc(
        file, title, category, employee_id or None, current_user, organization_id)


@router.get("/employee", summary="List Employee Documents", description="""
**Purpose:** Get documents for an employee.

**Access:**
- `employee` — sees own
- `org_admin`, `hr_admin` — pass `?employee_id=`

**Query:** employee_id (HR), category, page, limit
""")
async def list_employee_docs(employee_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None), page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=50),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_any)):
    return await DocumentService(db).list_employee_docs(current_user, employee_id, category, page, limit, organization_id)


@router.delete("/employee/{document_id}", summary="Delete Employee Document", description="""
**Purpose:** Delete an employee's document.

**Access:** `org_admin`, `hr_admin`
""")
async def delete_employee_doc(document_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await DocumentService(db).delete_employee_doc(document_id, current_user)


# ===========================================================================
# DOCUMENT TEMPLATES
# ===========================================================================

@router.post("/templates", status_code=201, summary="Upload Document Template", description="""
**Purpose:** Upload a downloadable template (leave form, expense form, etc.)

**Access:** `org_admin`, `hr_admin`

**Content-Type:** `multipart/form-data`

| Field | Required | Notes |
|---|---|---|
| file | ✅ | Template file |
| title | ✅ | Template name |
| description | ❌ | Brief description |
""")
async def upload_template(
    file: UploadFile = File(...), title: str = Form(...), description: str = Form(""),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await DocumentService(db).upload_template(file, title, description, current_user, organization_id)


@router.get("/templates", summary="List Document Templates", description="""
**Purpose:** Get downloadable templates.

**Access:** All authenticated users
""")
async def list_templates(organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_any)):
    return await DocumentService(db).list_templates(current_user, organization_id)


@router.delete("/templates/{template_id}", summary="Delete Template", description="""
**Purpose:** Remove a template.

**Access:** `org_admin`, `hr_admin`
""")
async def delete_template(template_id: str = Path(...), db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await DocumentService(db).delete_template(template_id, current_user)


# ===========================================================================
# DOCUMENT REQUESTS (HR requests → Employee uploads)
# ===========================================================================

@router.post("/requests", status_code=201, summary="Request Document from Employee", description="""
**Purpose:** HR requests an employee to upload a specific document (e.g., PAN card, experience letter).
Employee receives a notification and can upload via the upload endpoint.

**Access:** `org_admin`, `hr_admin`

**Request Body (JSON):**
```json
{
  "employee_id": "65emp...",
  "title": "PAN Card Copy",
  "description": "Please upload a clear scan of your PAN card",
  "category": "id_proof",
  "due_date": "2025-07-20"
}
```

| Field | Required | Notes |
|---|---|---|
| employee_id | ✅ | Employee MongoDB ObjectId |
| title | ✅ | What document is needed |
| description | ❌ | Additional instructions |
| category | ❌ | offer_letter / experience_letter / certificate / id_proof / other |
| due_date | ❌ | YYYY-MM-DD deadline |

**Flow:** HR requests → Employee gets notification → Employee uploads → HR gets notification → HR approves/rejects
""")
async def create_doc_request(
    employee_id: str, title: str, description: str = "", category: str = "other", due_date: str = "",
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await DocumentService(db).create_doc_request(
        employee_id, title, description, category, due_date, current_user, organization_id)


@router.get("/requests", summary="List Document Requests", description="""
**Purpose:** List document requests.

**Access:**
- `employee` — sees own pending requests
- `org_admin`, `hr_admin` — sees all (filterable)

**Query:** employee_id, status (pending/uploaded/approved/rejected), page, limit
""")
async def list_doc_requests(
    employee_id: Optional[str] = Query(None), status: Optional[str] = Query(None),
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=50),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database), current_user: dict = Depends(_any)):
    return await DocumentService(db).list_doc_requests(current_user, employee_id, status, page, limit, organization_id)


@router.put("/requests/{request_id}/upload", summary="Upload Requested Document", description="""
**Purpose:** Employee uploads the document that HR requested. Sends notification to HR.

**Access:** `employee` only

**Content-Type:** `multipart/form-data`

| Field | Required |
|---|---|
| file | ✅ |

**After upload:** Status changes to "uploaded" and HR is notified.
""")
async def upload_requested_doc(
    request_id: str = Path(...), file: UploadFile = File(...),
    db=Depends(get_database), current_user: dict = Depends(_emp)):
    return await DocumentService(db).upload_requested_doc(request_id, file, current_user)


@router.patch("/requests/{request_id}/review", summary="Approve/Reject Uploaded Document", description="""
**Purpose:** HR reviews the uploaded document and approves or rejects it.

**Access:** `org_admin`, `hr_admin`

**Query Parameters:**
| Param | Required | Notes |
|---|---|---|
| action | ✅ | "approve" or "reject" |
| reason | ❌ | Required for reject |

**On reject:** Status resets to "pending" so employee can re-upload. Employee gets notification.
""")
async def review_doc_request(
    request_id: str = Path(...),
    action: str = Query(..., description="approve | reject"),
    reason: str = Query("", description="Required for reject"),
    db=Depends(get_database), current_user: dict = Depends(_hr)):
    return await DocumentService(db).review_doc_request(request_id, action, reason, current_user)


# ===========================================================================
# DEFAULT DOCUMENT TITLES (for dropdown)
# ===========================================================================

@router.get("/default-titles", summary="Get Default Document Titles", description="""
**Purpose:** Returns a list of predefined document titles for dropdown selection.
Frontend uses this to show standard options when HR requests a document or employee uploads.

**Access:** All authenticated users

**Response 200:**
```json
{
  "titles": [
    { "title": "Aadhaar Card", "category": "id_proof" },
    { "title": "PAN Card", "category": "id_proof" },
    { "title": "Offer Letter", "category": "offer_letter" },
    { "title": "Experience Letter", "category": "experience_letter" },
    ...
  ]
}
```
""")
async def get_default_titles(current_user: dict = Depends(_any)):
    from app.models.document import DEFAULT_DOCUMENT_TITLES
    return {"titles": DEFAULT_DOCUMENT_TITLES}
