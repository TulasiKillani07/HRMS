from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Any, List, Dict


# ---------------------------------------------------------------------------
# Salary structure
# ---------------------------------------------------------------------------

class SalaryStructureSchema(BaseModel):
    ctc: float = Field(..., gt=0, description="Annual CTC. Breakdown (basic, HRA, special) auto-calculated from payroll config during payroll run.")


# ---------------------------------------------------------------------------
# Create — HR fills this
# ---------------------------------------------------------------------------

class EmployeeCreateRequest(BaseModel):
    employee_id: str = Field(..., min_length=1, max_length=50)
    organization_id: Optional[str] = Field(
        None, description="Required for superadmin only"
    )
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    official_email: EmailStr
    phone: str = Field(..., min_length=7, max_length=20)
    gender: str = Field(..., description="male | female | other")
    department: str = Field(..., min_length=1, max_length=100)
    designation: str = Field(..., min_length=2, max_length=100)
    reporting_manager: Optional[str] = None
    joining_date: str = Field(..., description="YYYY-MM-DD")
    employment_type: str = Field("full-time", description="full-time | part-time | contract")
    shift: Optional[str] = None
    work_location: Optional[str] = None
    salary_structure: SalaryStructureSchema
    is_fresher: bool = Field(
        ...,
        description="true = fresher (no prior experience), false = experienced."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "EMP001",
                "first_name": "Rahul",
                "last_name": "Verma",
                "official_email": "rahul@company.com",
                "phone": "+919876543210",
                "gender": "male",
                "department": "Engineering",
                "designation": "Senior Developer",
                "reporting_manager": "Vikram Singh",
                "joining_date": "2025-07-01",
                "employment_type": "full-time",
                "shift": "General",
                "work_location": "Hyderabad Office",
                "is_fresher": False,
                "salary_structure": {
                    "basic": 50000,
                    "hra": 20000,
                    "special_allowance": 15000,
                    "ctc": 1200000
                }
            }
        }

# ---------------------------------------------------------------------------
# Update — HR updates HR-controlled fields only
# ---------------------------------------------------------------------------

class EmployeeUpdateRequest(BaseModel):
    department: Optional[str] = None
    designation: Optional[str] = None
    reporting_manager: Optional[str] = None
    shift: Optional[str] = None
    work_location: Optional[str] = None
    employment_type: Optional[str] = None
    salary_structure: Optional[SalaryStructureSchema] = None
    status: Optional[str] = Field(
        None, description="pending_onboarding | onboarding_in_progress | active | inactive"
    )


# ---------------------------------------------------------------------------
# Create response
# ---------------------------------------------------------------------------

class EmployeeCreateResponse(BaseModel):
    id: str
    employee_id: str
    status: str
    onboarding_progress: int
    invite_sent: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# List item (compact)
# ---------------------------------------------------------------------------

class EmployeeListItem(BaseModel):
    id: str
    employee_id: str
    first_name: str
    last_name: str
    official_email: str
    phone: str
    gender: Optional[str] = None
    department: str
    designation: str
    status: str
    onboarding_progress: int
    joining_date: str
    is_fresher: Optional[bool] = None
    created_at: datetime


class EmployeeListResponse(BaseModel):
    employees: List[Any]
    total: int
    page: int
    limit: int
    pages: int


# ---------------------------------------------------------------------------
# CSV Import response
# ---------------------------------------------------------------------------

class CSVImportError(BaseModel):
    row: int
    employee_id: Optional[str] = None
    email: Optional[str] = None
    error: str


class CSVImportResponse(BaseModel):
    imported: int
    failed: int
    errors: List[CSVImportError]


# ---------------------------------------------------------------------------
# Onboarding section submission schemas
# ---------------------------------------------------------------------------

class PersonalDetailsRequest(BaseModel):
    date_of_birth: str = Field(..., description="YYYY-MM-DD")
    gender: str = Field(..., description="male | female | other")
    blood_group: Optional[str] = None
    marital_status: Optional[str] = Field(None, description="single | married | divorced")
    resume_url: Optional[str] = Field(None, description="Cloudinary URL of uploaded resume (PDF)")

    class Config:
        json_schema_extra = {
            "example": {
                "date_of_birth": "1995-03-15",
                "gender": "male",
                "blood_group": "O+",
                "marital_status": "single",
                "resume_url": "https://res.cloudinary.com/dxbjp7jno/raw/upload/v1/hrms/resumes/rahul_resume.pdf"
            }
        }


class AddressEntryRequest(BaseModel):
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    country: str = "India"


class AddressRequest(BaseModel):
    current: AddressEntryRequest
    permanent: Optional[AddressEntryRequest] = None

    class Config:
        json_schema_extra = {
            "example": {
                "current": {
                    "line1": "Flat 4B, Sunrise Apartments",
                    "city": "Hyderabad",
                    "state": "Telangana",
                    "pincode": "500032"
                },
                "permanent": {
                    "line1": "12 Gandhi Nagar",
                    "city": "Visakhapatnam",
                    "state": "Andhra Pradesh",
                    "pincode": "530002"
                }
            }
        }


class EmergencyContactRequest(BaseModel):
    name: str
    relation: str
    phone: str

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Priya Verma",
                "relation": "Spouse",
                "phone": "+919876543211"
            }
        }


class BankDetailsRequest(BaseModel):
    account_number: str
    ifsc: str
    bank_name: str
    branch: Optional[str] = None
    account_type: str = Field("savings", description="savings | current")

    class Config:
        json_schema_extra = {
            "example": {
                "account_number": "123456789012",
                "ifsc": "HDFC0001234",
                "bank_name": "HDFC Bank",
                "branch": "Madhapur",
                "account_type": "savings"
            }
        }


class GovIDEntryRequest(BaseModel):
    number: str
    document_url: Optional[str] = None


class GovernmentIDsRequest(BaseModel):
    pan: Optional[GovIDEntryRequest] = None
    aadhaar: Optional[GovIDEntryRequest] = None
    passport: Optional[GovIDEntryRequest] = None
    uan: Optional[GovIDEntryRequest] = Field(
        None,
        description="Universal Account Number (EPFO) — optional for all employees"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "pan": {"number": "ABCDE1234F", "document_url": "https://res.cloudinary.com/..."},
                "aadhaar": {"number": "1234 5678 9012", "document_url": "https://res.cloudinary.com/..."},
                "passport": {"number": "N1234567", "document_url": "https://res.cloudinary.com/..."},
                "uan": {"number": "100123456789", "document_url": None}
            }
        }


class EducationEntryRequest(BaseModel):
    degree: str
    institution: str
    field_of_study: Optional[str] = None
    start_year: int
    end_year: Optional[int] = None
    grade: Optional[str] = None
    document_url: Optional[str] = None


class EducationRequest(BaseModel):
    entries: List[EducationEntryRequest]

    class Config:
        json_schema_extra = {
            "example": {
                "entries": [
                    {
                        "degree": "B.Tech",
                        "institution": "JNTU Hyderabad",
                        "field_of_study": "Computer Science",
                        "start_year": 2013,
                        "end_year": 2017,
                        "grade": "8.5 CGPA"
                    }
                ]
            }
        }


class ExperienceEntryRequest(BaseModel):
    company: str
    designation: str
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="YYYY-MM-DD or null if current")
    is_current: bool = False
    description: Optional[str] = None
    document_url: Optional[str] = None


class ExperienceRequest(BaseModel):
    """
    Fresher → send empty entries list.
    Experienced → send at least 1 entry (UAN already captured at creation).
    """
    entries: Optional[List[ExperienceEntryRequest]] = Field(
        default=[],
        description="Past job entries. At least 1 required if employee was marked experienced at creation."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "entries": [
                    {
                        "company": "TechCorp Pvt Ltd",
                        "designation": "Software Developer",
                        "start_date": "2019-07-01",
                        "end_date": "2023-06-30",
                        "is_current": False,
                        "description": "Full stack development",
                        "document_url": "https://res.cloudinary.com/..."
                    }
                ]
            }
        }


class PolicyAcceptanceRequest(BaseModel):
    accepted: bool = Field(..., description="Must be true to complete this section")

    class Config:
        json_schema_extra = {"example": {"accepted": True}}


# ---------------------------------------------------------------------------
# Single wrapper for all onboarding section submissions
# ---------------------------------------------------------------------------

class OnboardingSectionRequest(BaseModel):
    """
    Universal onboarding section submission wrapper.
    The `data` field carries section-specific payload — shape depends on the section.
    """
    data: dict = Field(..., description="Section data — shape varies by section name in path")

    class Config:
        json_schema_extra = {
            "example": {
                "data": {
                    "date_of_birth": "1995-03-15",
                    "gender": "male",
                    "blood_group": "O+",
                    "marital_status": "single"
                }
            }
        }


# ---------------------------------------------------------------------------
# Onboarding progress response
# ---------------------------------------------------------------------------

class OnboardingSectionInfo(BaseModel):
    status: str
    verified: bool


class OnboardingProgressResponse(BaseModel):
    status: str
    progress: int
    is_fresher: Optional[bool] = None
    sections: Dict[str, Any]
    hr_notes: Optional[str] = None
    # HR-filled info at creation
    employee_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    official_email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    reporting_manager: Optional[str] = None
    joining_date: Optional[str] = None
    employment_type: Optional[str] = None
    shift: Optional[str] = None
    work_location: Optional[str] = None
    salary_structure: Optional[Any] = None
    # Employee-filled onboarding data
    personal_details: Optional[Any] = None
    address: Optional[Any] = None
    emergency_contact: Optional[Any] = None
    bank_details: Optional[Any] = None
    government_ids: Optional[Any] = None
    education: Optional[Any] = None
    experience: Optional[Any] = None
    policy_acceptance: Optional[Any] = None


class SectionSubmitResponse(BaseModel):
    section: str
    status: str
    overall_progress: int


# ---------------------------------------------------------------------------
# HR verify/approve request
# ---------------------------------------------------------------------------

class VerifyEmployeeRequest(BaseModel):
    action: str = Field(
        ...,
        description="approve | verify_section | request_changes"
    )
    section: Optional[str] = Field(None, description="Required for verify_section")
    sections: Optional[List[str]] = Field(None, description="Required for request_changes")
    notes: Optional[str] = Field(None, description="HR notes for request_changes")

    class Config:
        json_schema_extra = {
            "example": {
                "action": "approve"
            }
        }
