from datetime import datetime, date
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, EmailStr


# ---------------------------------------------------------------------------
# Sub-models — HR filled at creation
# ---------------------------------------------------------------------------

class SalaryStructure(BaseModel):
    ctc: float = Field(..., gt=0)                # Annual CTC only. Breakdown calculated from payroll config.


# ---------------------------------------------------------------------------
# Sub-models — Employee filled during onboarding
# ---------------------------------------------------------------------------

class PersonalDetails(BaseModel):
    date_of_birth: Optional[str] = None          # "YYYY-MM-DD"
    gender: Optional[str] = None                  # male | female | other
    blood_group: Optional[str] = None
    marital_status: Optional[str] = None          # single | married | divorced


class AddressEntry(BaseModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    country: Optional[str] = "India"


class Address(BaseModel):
    current: Optional[AddressEntry] = None
    permanent: Optional[AddressEntry] = None


class EmergencyContact(BaseModel):
    name: Optional[str] = None
    relation: Optional[str] = None
    phone: Optional[str] = None


class BankDetails(BaseModel):
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    branch: Optional[str] = None
    account_type: Optional[str] = None           # savings | current


class GovernmentIDEntry(BaseModel):
    number: Optional[str] = None
    document_url: Optional[str] = None           # Cloudinary URL


class GovernmentIDs(BaseModel):
    pan: Optional[GovernmentIDEntry] = None
    aadhaar: Optional[GovernmentIDEntry] = None
    passport: Optional[GovernmentIDEntry] = None


class EducationEntry(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    grade: Optional[str] = None
    document_url: Optional[str] = None           # Cloudinary URL


class ExperienceEntry(BaseModel):
    company: Optional[str] = None
    designation: Optional[str] = None
    start_date: Optional[str] = None             # "YYYY-MM-DD"
    end_date: Optional[str] = None               # null if current
    is_current: bool = False
    description: Optional[str] = None
    document_url: Optional[str] = None           # Relieving letter URL


class PolicyAcceptance(BaseModel):
    accepted: bool = False
    accepted_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Onboarding section tracking
# ---------------------------------------------------------------------------

ONBOARDING_SECTIONS = [
    "personal_details",
    "address",
    "emergency_contact",
    "bank_details",
    "government_ids",
    "education",
    "experience",
    "policy_acceptance",
]

# Sections HR must verify before approving
CRITICAL_SECTIONS = ["bank_details", "government_ids"]


class SectionStatus(BaseModel):
    status: str = "pending"          # pending | completed | needs_revision
    verified: bool = False
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    hr_notes: Optional[str] = None


def default_onboarding_sections() -> Dict[str, dict]:
    return {s: SectionStatus().model_dump() for s in ONBOARDING_SECTIONS}


# ---------------------------------------------------------------------------
# Main Employee Model
# ---------------------------------------------------------------------------

class EmployeeModel(BaseModel):
    """Employee database model — stored in db.employees"""

    # Identity
    organization_id: str
    employee_id: str                             # Company-specific: EMP001
    user_id: Optional[str] = None               # Links to db.users after account creation

    # HR-filled at creation
    first_name: str
    last_name: str
    official_email: EmailStr
    phone: str
    gender: Optional[str] = None                 # male | female | other
    department: str
    designation: str
    reporting_manager: Optional[str] = None
    joining_date: str                            # "YYYY-MM-DD"
    employment_type: str = "full-time"           # full-time | part-time | contract
    shift: Optional[str] = None
    work_location: Optional[str] = None
    salary_structure: SalaryStructure
    is_fresher: Optional[bool] = None            # true = fresher, false = experienced
    uan_number: Optional[str] = None             # UAN number if PF applicable
    pf_applicable: bool = False                  # Is PF applicable
    esi_applicable: bool = False                 # Is ESI applicable
    esic_number: Optional[str] = None            # ESIC number if ESI applicable

    # Status & onboarding
    status: str = "pending_onboarding"
    # pending_onboarding | onboarding_in_progress | active | inactive
    onboarding_progress: int = 0                 # 0-100
    hr_notes: Optional[str] = None

    # Onboarding section tracking
    onboarding_sections: Dict[str, dict] = Field(
        default_factory=default_onboarding_sections
    )

    # Employee-filled during onboarding
    personal_details: Optional[dict] = None
    address: Optional[dict] = None
    emergency_contact: Optional[dict] = None
    bank_details: Optional[dict] = None
    government_ids: Optional[dict] = None
    education: Optional[List[dict]] = None
    experience: Optional[List[dict]] = None
    policy_acceptance: Optional[dict] = None

    # Soft delete
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    activated_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "employee_id": "EMP001",
                "first_name": "Rahul",
                "last_name": "Verma",
                "official_email": "rahul@company.com",
                "phone": "+919876543210",
                "department": "Engineering",
                "designation": "Senior Developer",
                "joining_date": "2025-07-01",
                "employment_type": "full-time",
                "salary_structure": {
                    "basic": 50000,
                    "hra": 20000,
                    "special_allowance": 15000,
                    "ctc": 1200000
                }
            }
        }
