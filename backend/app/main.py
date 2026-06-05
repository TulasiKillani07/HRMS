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

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="HRMS API with FastAPI and MongoDB"
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
app.include_router(employees_router, prefix=f"{settings.API_V1_PREFIX}/employees", tags=["Employees"])
app.include_router(departments_router, prefix=f"{settings.API_V1_PREFIX}/departments", tags=["Departments"])
app.include_router(attendance_router, prefix=f"{settings.API_V1_PREFIX}/attendance", tags=["Attendance"])
app.include_router(leaves_router, prefix=f"{settings.API_V1_PREFIX}/leaves", tags=["Leaves"])
app.include_router(payroll_router, prefix=f"{settings.API_V1_PREFIX}/payroll", tags=["Payroll"])
