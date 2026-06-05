# HRMS API - FastAPI with MongoDB

Human Resource Management System API built with FastAPI and MongoDB.

## Project Structure

```
backend/
├── app/
│   ├── core/              # Core functionality (config, security, dependencies)
│   ├── models/            # MongoDB collection models
│   ├── utils/             # Utility functions (helpers, validators, responses)
│   ├── v1/                # API version 1
│   │   ├── auth/          # Authentication endpoints
│   │   ├── employees/     # Employee management
│   │   ├── departments/   # Department management
│   │   ├── attendance/    # Attendance tracking
│   │   ├── leaves/        # Leave management
│   │   └── payroll/       # Payroll processing
│   ├── main.py           # Application entry point
│   └── database.py       # Database connection
├── requirements.txt
├── .env.example
└── .gitignore
```

## Features

- 🔐 JWT Authentication
- 🏢 **Organization Management (NEW)**
  - Superadmin can create/manage organizations
  - Auto-create org admin users
  - Email & SMS invitations
  - Soft delete support
- 👥 Employee Management
- 🏢 Department Management
- ⏰ Attendance Tracking
- 📅 Leave Management
- 💰 Payroll Processing

## User Roles

- **superadmin** - Can create and manage organizations
- **org_admin** - Organization administrator (created by superadmin)
- **hr_admin** - HR administrator (to be implemented)
- **employee** - Regular employee

## Installation

1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create `.env` file from `.env.example` and update values

5. Start MongoDB locally or use MongoDB Atlas

## Configuration

1. Update MongoDB connection in `.env`:
   ```
   MONGODB_URL="mongodb+srv://TfgHrmsUser:Hrms@163@tfghrms.jtzhyy4.mongodb.net/"
   ```

2. API prefix is set to `/HRMS`

## Running the Application

```bash
uvicorn app.main:app --reload
```

API will be available at: `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

## Testing Organizations API

Run the test script after starting the server:
```bash
python test_organization_api.py
```

This will:
- Create a superadmin user
- Login as superadmin
- Create an organization
- Test all CRUD operations
- Verify soft delete

## API Endpoints

### Authentication
- POST `/HRMS/auth/register` - Register new user
- POST `/HRMS/auth/login` - Login
- POST `/HRMS/auth/refresh` - Refresh token
- GET `/HRMS/auth/me` - Get current user

### Organizations (Superadmin Only) ⭐ NEW
- POST `/HRMS/organizations/` - Create organization
- GET `/HRMS/organizations/` - Get all organizations (with pagination)
- GET `/HRMS/organizations/{id}` - Get organization by ID
- PUT `/HRMS/organizations/{id}` - Update organization
- DELETE `/HRMS/organizations/{id}` - Soft delete organization

📖 **Detailed API Documentation**: See [ORGANIZATIONS_API.md](ORGANIZATIONS_API.md)

### Employees
- POST `/HRMS/employees/` - Create employee
- GET `/HRMS/employees/` - Get all employees

### Departments
- POST `/HRMS/departments/` - Create department

### Attendance
- POST `/HRMS/attendance/check-in` - Check-in

### Leaves
- POST `/HRMS/leaves/` - Create leave request

### Payroll
- POST `/HRMS/payroll/` - Create payroll record
