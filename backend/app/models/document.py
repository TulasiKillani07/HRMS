from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CompanyDocumentModel(BaseModel):
    """Company document — stored in db.company_documents"""
    organization_id: str
    title: str
    category: str = "other"                      # policy | handbook | template | form | other
    description: Optional[str] = None
    file_url: str
    file_name: str
    file_size: int = 0                           # bytes
    file_type: str = ""                          # MIME type
    target_departments: List[str] = []           # Empty = all
    is_mandatory: bool = False
    acknowledged_by: List[str] = []              # user_ids who acknowledged
    uploaded_by: str
    uploaded_by_name: str
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EmployeeDocumentModel(BaseModel):
    """Employee personal document — stored in db.employee_documents"""
    organization_id: str
    employee_id: str
    employee_name: str
    title: str
    category: str = "other"                      # offer_letter | experience_letter | certificate | id_proof | other
    file_url: str
    file_name: str
    file_size: int = 0
    file_type: str = ""
    uploaded_by: str
    uploaded_by_name: str
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentTemplateModel(BaseModel):
    """Document template — stored in db.document_templates"""
    organization_id: str
    title: str
    description: Optional[str] = None
    file_url: str
    file_name: str
    file_type: str = ""
    download_count: int = 0
    uploaded_by: str
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentRequestModel(BaseModel):
    """HR requests document from employee — stored in db.document_requests"""
    organization_id: str
    employee_id: str
    employee_name: str
    department: str
    title: str                                   # What document is needed
    description: Optional[str] = None            # Additional instructions
    category: str = "other"                      # offer_letter | experience_letter | certificate | id_proof | other
    due_date: Optional[str] = None               # "YYYY-MM-DD"
    status: str = "pending"                      # pending | uploaded | approved | rejected
    # Upload by employee
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: int = 0
    file_type: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    # HR review
    reviewed_by: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    # Metadata
    requested_by: str
    requested_by_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Default Document Titles — for dropdown in frontend
# ---------------------------------------------------------------------------

DEFAULT_DOCUMENT_TITLES = [
    # ID Proofs
    {"title": "Aadhaar Card", "category": "id_proof"},
    {"title": "PAN Card", "category": "id_proof"},
    {"title": "Passport", "category": "id_proof"},
    {"title": "Driving License", "category": "id_proof"},
    {"title": "Voter ID", "category": "id_proof"},
    # Education
    {"title": "10th Marksheet", "category": "certificate"},
    {"title": "12th Marksheet", "category": "certificate"},
    {"title": "Degree Certificate", "category": "certificate"},
    {"title": "Provisional Certificate", "category": "certificate"},
    {"title": "Migration Certificate", "category": "certificate"},
    {"title": "Transfer Certificate", "category": "certificate"},
    # Employment
    {"title": "Offer Letter", "category": "offer_letter"},
    {"title": "Appointment Letter", "category": "offer_letter"},
    {"title": "Experience Letter", "category": "experience_letter"},
    {"title": "Relieving Letter", "category": "experience_letter"},
    {"title": "Salary Slip (Last 3 Months)", "category": "other"},
    {"title": "Hike Letter", "category": "other"},
    # Bank
    {"title": "Bank Passbook / Statement", "category": "other"},
    {"title": "Cancelled Cheque", "category": "other"},
    # Other
    {"title": "Address Proof", "category": "id_proof"},
    {"title": "Medical Certificate", "category": "certificate"},
    {"title": "Background Verification Report", "category": "other"},
    {"title": "Photo (Passport Size)", "category": "other"},
    {"title": "Signed NDA", "category": "other"},
    {"title": "Other", "category": "other"},
]
