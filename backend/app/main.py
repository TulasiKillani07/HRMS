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

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
# HRMS API with FastAPI and MongoDB

Complete HR Management System with role-based access control, organization management, and employee operations.

## 🎭 User Roles (4 Total)

The system supports 4 distinct roles with hierarchical permissions:

### 1. **superadmin** - System Administrator
- **Access Level:** Full system access
- **Responsibilities:**
  - Create and manage all organizations
  - View system-wide analytics
  - Manage system configuration
- **Scope:** Entire HRMS system
- **Not counted in any limit**

### 2. **org_admin** - Organization Administrator  
- **Access Level:** Organization-wide access
- **Responsibilities:**
  - Manage organization settings
  - Create departments and employees
  - Create HR admins
  - View organization reports
  - Manage payroll, attendance, leaves
- **Scope:** Single organization
- **Auto-created:** When organization is created
- **Counted in:** `admin_user_access_limit`

### 3. **hr_admin** - HR Administrator
- **Access Level:** HR department access
- **Responsibilities:**
  - Manage employees
  - Process payroll
  - Approve/reject leave requests
  - Manage attendance records
  - Generate HR reports
- **Scope:** Organization (HR operations)
- **Created by:** org_admin
- **Counted in:** `admin_user_access_limit`

### 4. **employee** - Regular Employee
- **Access Level:** Self-service only
- **Responsibilities:**
  - View own profile
  - Mark attendance
  - Apply for leave
  - View payslips
  - Update personal information
- **Scope:** Self only
- **Default role:** When registering
- **Counted in:** `emp_count_for_access`

## 📊 Access Limits

Each organization has two separate access limits:

### Admin User Limit (`admin_user_access_limit`)
- **Controls:** org_admin + hr_admin users
- **Default:** 2 admin users
- **Customizable:** Yes (per organization)
- **Use Case:** Control administrative access per organization

### Employee Limit (`emp_count_for_access`)
- **Controls:** employee users
- **Default:** Defined at organization creation
- **Customizable:** Yes (per organization)
- **Use Case:** Tier-based pricing (e.g., Basic: 50, Pro: 100)

## 🔐 Authentication

All protected endpoints require authentication via:
1. **HTTP-only cookies** (Recommended for web apps)
2. **Authorization header** with Bearer token (For API clients)

Use `/auth/login` to obtain tokens.

## 🏢 Organization Hierarchy

```
superadmin (System Level)
    │
    ├── Organization A
    │   ├── org_admin (1)
    │   ├── hr_admin (1 or more)
    │   └── employees (many)
    │
    └── Organization B
        ├── org_admin (1)
        ├── hr_admin (1 or more)
        └── employees (many)
```

## 📝 Quick Start

1. **Register Superadmin:** `POST /auth/register` with role `superadmin`
2. **Login:** `POST /auth/login` to get tokens
3. **Create Organization:** `POST /organizations/` (auto-creates org_admin)
4. **Org Admin Login:** Use credentials from invitation email
5. **Add Employees:** Use employee endpoints

## 🌐 Base URL

Development: `http://localhost:8002/hrms`

## 📖 Documentation

- **Swagger UI:** `/docs`
- **ReDoc:** `/redoc`
"""
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
app.include_router(employees_router, prefix=f"{settings.API_V1_PREFIX}/employees", tags=["Employees"])
app.include_router(departments_router, prefix=f"{settings.API_V1_PREFIX}/departments", tags=["Departments"])
app.include_router(attendance_router, prefix=f"{settings.API_V1_PREFIX}/attendance", tags=["Attendance"])
app.include_router(leaves_router, prefix=f"{settings.API_V1_PREFIX}/leaves", tags=["Leaves"])
app.include_router(payroll_router, prefix=f"{settings.API_V1_PREFIX}/payroll", tags=["Payroll"])
