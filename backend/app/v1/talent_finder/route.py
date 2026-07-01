from fastapi import APIRouter, Depends, Query, Path, UploadFile, File, Form, status, HTTPException
from typing import Optional, List
from app.database import get_database
from app.core.dependencies import get_current_user
from app.v1.talent_finder.hrms_service import HRMSTalentFinderService

router = APIRouter()


def _hr(u: dict = Depends(get_current_user)):
    if u.get("role") not in ("superadmin", "org_admin", "hr_admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return u


@router.post(
    "/search",
    status_code=status.HTTP_201_CREATED,
    summary="Run Talent Search (AI Resume Matching)",
    description="""
**Purpose:** HR uploads a Job Description and selects employees. The AI compares each employee's
resume (stored in their onboarding `personal_details.resume_url`) against the JD and ranks them.

**Access:** `org_admin`, `hr_admin`

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Required | Description |
|-------|----------|-------------|
| jd_file | ✅ | Job Description file (PDF, DOCX, TXT) |
| title | ❌ | Search title/label (e.g., "Senior Dev Opening") |
| department | ❌ | Filter by department name (all active employees in dept) |
| employee_ids | ❌ | Comma-separated employee MongoDB ObjectIds (specific employees) |
| top_n | ❌ | Return only top N results (0 = all) |

**Note:** Provide either `department` OR `employee_ids`, not both.
Each employee must have uploaded their resume during onboarding (`personal_details.resume_url`).

**Response 201:**
```json
{
  "title": "Senior Software Engineer",
  "department": "Engineering",
  "total_candidates": 8,
  "showing": 8,
  "required_skills": ["React", "Node.js", "AWS"],
  "employees_without_resume": ["Raj Kumar"],
  "results": [
    {
      "rank": 1,
      "employee_id": "65emp...",
      "employee_code": "EMP001",
      "match_score": 87.5,
      "candidate_name": "Rahul Verma",
      "department": "Engineering",
      "designation": "Software Developer",
      "matched_skills": ["React", "Node.js", "AWS"],
      "missing_skills": ["Kubernetes"],
      "experience_years": 5,
      "seniority_level": "senior",
      "strengths": ["Strong full-stack background", "AWS certified"],
      "weaknesses": ["Missing Kubernetes"],
      "summary": "5yr full-stack dev, strong AWS skills",
      "recruiter_verdict": "shortlist",
      "why_top_ranked": "Best overall match for senior dev role",
      "improvement_suggestion": "Add Kubernetes certification",
      "skills_score": 0.85,
      "semantic_score": 0.78,
      "experience_score": 0.90,
      "percentile": 95,
      "fraud_score": 0,
      "is_suspicious": false
    }
  ]
}
```

**Recruiter Verdict Values:**
- `shortlist` — Strong match, recommend for interview
- `maybe` — Partial match, needs discussion
- `pass` — Not suitable for this role

**Errors:**
- `400` — No employees found / No resumes available / JD parse failed
- `404` — No active employees in given department
""",
)
async def run_talent_search(
    jd_file: UploadFile = File(..., description="Job Description (PDF, DOCX, TXT)"),
    title: str = Form("", description="Search title label"),
    department: str = Form("", description="Filter by department name"),
    employee_ids: str = Form("", description="Comma-separated employee ObjectIds"),
    top_n: int = Form(0, description="Return top N results (0 = all)"),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_hr)
):
    if not jd_file.filename.endswith(('.pdf', '.docx', '.txt')):
        raise HTTPException(status_code=400, detail="JD must be PDF, DOCX, or TXT")

    emp_ids = [e.strip() for e in employee_ids.split(",") if e.strip()] if employee_ids else []

    if not department and not emp_ids:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'department' (search all in dept) or 'employee_ids' (specific employees)"
        )

    return await HRMSTalentFinderService(db).run_talent_search(
        jd_file=jd_file,
        department=department,
        employee_ids=emp_ids,
        top_n=top_n,
        title=title,
        current_user=current_user,
        org_id_param=organization_id
    )


@router.get(
    "/history",
    summary="Get Talent Search History",
    description="""
**Purpose:** List all past talent searches for the organization.

**Access:** `org_admin`, `hr_admin`

**Response 200:**
```json
{
  "searches": [
    {
      "id": "65search...",
      "title": "Senior Software Engineer",
      "department": "Engineering",
      "total_candidates": 8,
      "created_by_name": "Pranavi",
      "created_at": "2025-07-15T09:00:00"
    }
  ],
  "total": 5,
  "page": 1,
  "pages": 1
}
```
""",
)
async def get_search_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    organization_id: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: dict = Depends(_hr)
):
    return await HRMSTalentFinderService(db).get_search_history(current_user, page, limit, organization_id)


@router.get(
    "/history/{search_id}",
    summary="Get Talent Search Detail",
    description="""
**Purpose:** Get full results of a specific past talent search.

**Access:** `org_admin`, `hr_admin`

**Path Parameter:** `search_id` — MongoDB ObjectId of the saved search
""",
)
async def get_search_detail(
    search_id: str = Path(...),
    db=Depends(get_database),
    current_user: dict = Depends(_hr)
):
    return await HRMSTalentFinderService(db).get_search_detail(search_id, current_user)
