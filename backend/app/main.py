from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.v1.employees.route import router as employees_router
from app.v1.departments.route import router as departments_router
from app.v1.attendance.route import router as attendance_router
from app.v1.leaves.route import router as leaves_router
from app.v1.payroll.route import router as payroll_router
from app.v1.auth.route import router as auth_router
from app.v1.organizations.route import router as organizations_router
from app.v1.users.route import router as users_router
from app.v1.upload.route import router as upload_router
from app.v1.performance.route import router as performance_router
from app.v1.holidays.route import router as holidays_router
from app.v1.employees.edit_request_route import router as edit_request_router
from app.v1.notifications.route import router as notifications_router
from app.v1.announcements.route import router as announcements_router
from app.v1.documents.route import router as documents_router
from app.v1.wellness.route import router as wellness_router
from app.v1.activity_logs.route import router as activity_logs_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
# HRMS API — Human Resource Management System

Built with **FastAPI** + **MongoDB**. All endpoints are prefixed with `/hrms`.

---

## Authentication

All protected endpoints require a valid `access_token`.

**Two ways to authenticate:**
1. **Cookie** (browser) — set automatically after `POST /auth/login`
2. **Header** (API clients) — `Authorization: Bearer <access_token>`

Default password for all auto-created users: **`Welcome1`**
On first login, `requires_password_change: true` is returned → frontend should force password change.

---

## User Roles & Permissions

| Role | Created by | Scope | Access |
|---|---|---|---|
| `superadmin` | Self-register | Entire system | Manage all organizations and users |
| `org_admin` | superadmin (via POST /organizations/) | Single org | Manage org, departments, employees, hr_admins |
| `hr_admin` | superadmin or org_admin (via POST /users/) | Single org | Manage employees, payroll, attendance, leaves |
| `employee` | HR (via POST /employees/) | Self only | Onboarding, view own profile, leave, attendance |

---

## Organization Access Limits

Each organization has two limits:

| Limit | Controls | Default |
|---|---|---|
| `admin_user_access_limit` | Total org_admin + hr_admin users | 2 |
| `emp_count_for_access` | Total employees | Set at org creation |

---

## Employee Onboarding Flow

```
HR creates employee (POST /employees/)
        ↓
Employee receives Welcome email with login + password "Welcome1"
        ↓
Employee logs in → forced to change password
        ↓
Employee fills 9 onboarding sections (PUT /employees/me/onboarding/{section})
        ↓
All 9 completed → status: onboarding_in_progress (HR notified)
        ↓
HR verifies critical sections (bank_details, government_ids)
        ↓
HR approves (PATCH /employees/{id}/verify) → status: active
```

**Onboarding sections:**
`personal_details` | `address` | `emergency_contact` | `bank_details` ⚠️ |
`government_ids` ⚠️ | `education` | `experience` | `policy_acceptance`

⚠️ = Critical sections — must be HR-verified before employee can be activated.

---

## Quick Start

1. `POST /hrms/auth/register` — create superadmin (role: superadmin)
2. `POST /hrms/auth/login` — login as superadmin
3. `POST /hrms/organizations/` — create organization (auto-creates org_admin)
4. Login as org_admin → `POST /hrms/users/` — create hr_admin
5. Login as hr_admin → `POST /hrms/employees/` — create employees
6. Login as employee → `PUT /hrms/employees/me/onboarding/{section}` — fill profile

---

## Base URL

`http://localhost:8000/hrms`

**Docs:** `/docs` (Swagger) · `/redoc` (ReDoc)
""",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database events
@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()

# Health check
@app.get("/", tags=["Health"])
async def root():
    return {"message": "HRMS API is running", "version": settings.VERSION}

# Include routers
app.include_router(auth_router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(organizations_router, prefix=f"{settings.API_V1_PREFIX}/organizations", tags=["Organizations"])
app.include_router(users_router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["User Management"])
app.include_router(upload_router, prefix=f"{settings.API_V1_PREFIX}/upload", tags=["File Upload"])
app.include_router(performance_router, prefix=f"{settings.API_V1_PREFIX}/performance", tags=["Performance & OKRs"])
app.include_router(employees_router, prefix=f"{settings.API_V1_PREFIX}/employees", tags=["Employees"])
app.include_router(edit_request_router, prefix=f"{settings.API_V1_PREFIX}/employees/edit-requests", tags=["Employee Edit Requests"])
app.include_router(notifications_router, prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["Notifications"])
app.include_router(announcements_router, prefix=f"{settings.API_V1_PREFIX}/announcements", tags=["Announcements"])
app.include_router(documents_router, prefix=f"{settings.API_V1_PREFIX}/documents", tags=["Documents"])
app.include_router(wellness_router, prefix=f"{settings.API_V1_PREFIX}/wellness", tags=["Wellness & Mood"])
app.include_router(activity_logs_router, prefix=f"{settings.API_V1_PREFIX}/activity-logs", tags=["Activity Logs"])
app.include_router(departments_router, prefix=f"{settings.API_V1_PREFIX}/departments", tags=["Departments"])
app.include_router(attendance_router, prefix=f"{settings.API_V1_PREFIX}/attendance", tags=["Attendance"])
app.include_router(leaves_router, prefix=f"{settings.API_V1_PREFIX}/leaves", tags=["Leaves"])
app.include_router(holidays_router, prefix=f"{settings.API_V1_PREFIX}/holidays", tags=["Holiday Calendar"])
app.include_router(payroll_router, prefix=f"{settings.API_V1_PREFIX}/payroll", tags=["Payroll"])
