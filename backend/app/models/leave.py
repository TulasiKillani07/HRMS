from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Leave Type Configuration
# ---------------------------------------------------------------------------

class LeaveTypeConfig(BaseModel):
    """Individual leave type configuration"""
    id: Optional[str] = None                     # UUID assigned on creation
    name: str                                    # e.g., "Casual Leave"
    code: str                                    # e.g., "CL"
    days_per_year: int = Field(0, ge=-1)         # -1 means unlimited (e.g., LWP)
    is_paid: bool = True
    carry_forward: bool = False
    max_carry_forward_days: int = Field(0, ge=0)
    applicable_after_days: int = Field(0, ge=0)  # Available after X days of joining
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LeaveConfigurationModel(BaseModel):
    """Leave configuration for an organization — stored in db.leave_configurations"""
    organization_id: str
    year: int
    leave_types: List[LeaveTypeConfig] = []
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "year": 2025,
                "leave_types": [
                    {
                        "id": "uuid-1",
                        "name": "Casual Leave",
                        "code": "CL",
                        "days_per_year": 12,
                        "is_paid": True,
                        "carry_forward": False,
                        "applicable_after_days": 0,
                        "is_active": True
                    }
                ]
            }
        }


# ---------------------------------------------------------------------------
# Default Leave Types — applied when org creates first configuration
# ---------------------------------------------------------------------------

DEFAULT_LEAVE_TYPES = [
    {
        "name": "Casual Leave",
        "code": "CL",
        "days_per_year": 12,
        "is_paid": True,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "applicable_after_days": 0,
        "description": "For personal/short-term needs",
        "is_active": True,
    },
    {
        "name": "Sick Leave",
        "code": "SL",
        "days_per_year": 6,
        "is_paid": True,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "applicable_after_days": 0,
        "description": "For medical reasons or illness",
        "is_active": True,
    },
    {
        "name": "Earned Leave",
        "code": "EL",
        "days_per_year": 15,
        "is_paid": True,
        "carry_forward": True,
        "max_carry_forward_days": 30,
        "applicable_after_days": 180,
        "description": "Planned leave, accrued over time",
        "is_active": True,
    },
    {
        "name": "Maternity Leave",
        "code": "ML",
        "days_per_year": 182,
        "is_paid": True,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "applicable_after_days": 80,
        "description": "For female employees during pregnancy and childbirth",
        "is_active": True,
    },
    {
        "name": "Paternity Leave",
        "code": "PL",
        "days_per_year": 15,
        "is_paid": True,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "applicable_after_days": 0,
        "description": "For male employees on birth of child",
        "is_active": True,
    },
    {
        "name": "Marriage Leave",
        "code": "MRL",
        "days_per_year": 3,
        "is_paid": True,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "applicable_after_days": 0,
        "description": "For employee's own marriage",
        "is_active": True,
    },
    {
        "name": "Bereavement Leave",
        "code": "BL",
        "days_per_year": 5,
        "is_paid": True,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "applicable_after_days": 0,
        "description": "On death of immediate family member",
        "is_active": True,
    },
    {
        "name": "Comp Off",
        "code": "CO",
        "days_per_year": -1,
        "is_paid": True,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "applicable_after_days": 0,
        "description": "Compensatory off for working on holidays/weekends",
        "is_active": True,
    },
    {
        "name": "Optional Holiday",
        "code": "OH",
        "days_per_year": 2,
        "is_paid": True,
        "carry_forward": False,
        "max_carry_forward_days": 0,
        "applicable_after_days": 0,
        "description": "Choose from list of optional/restricted holidays",
        "is_active": True,
    },
]


# ---------------------------------------------------------------------------
# Leave Request Model
# ---------------------------------------------------------------------------

class LeaveRequestModel(BaseModel):
    """Leave request submitted by employee — stored in db.leave_requests"""
    organization_id: str
    employee_id: str                             # MongoDB ObjectId of employee
    employee_name: str
    department: str
    leave_type_code: str                         # Code from leave configuration (CL, SL, etc.)
    leave_type_name: str                         # Name for display
    start_date: str                              # "YYYY-MM-DD"
    end_date: str                                # "YYYY-MM-DD"
    days: float                                  # Can be 0.5 for half-day
    is_half_day: bool = False
    half_day_type: Optional[str] = None          # first_half | second_half
    reason: str
    status: str = "pending"                      # pending | approved | rejected | cancelled
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "employee_id": "65emp001abc",
                "employee_name": "Rahul Verma",
                "department": "Engineering",
                "leave_type_code": "CL",
                "leave_type_name": "Casual Leave",
                "start_date": "2025-07-10",
                "end_date": "2025-07-11",
                "days": 2,
                "is_half_day": False,
                "reason": "Personal work",
                "status": "pending"
            }
        }


# ---------------------------------------------------------------------------
# Leave Balance Adjustment Model
# ---------------------------------------------------------------------------

class LeaveBalanceAdjustmentModel(BaseModel):
    """Manual balance adjustment by HR — stored in db.leave_balance_adjustments"""
    organization_id: str
    employee_id: str
    employee_name: str
    leave_type_code: str
    leave_type_name: str
    action: str                                  # credit | deduct | reset
    days: float                                  # Number of days adjusted
    reason: str
    adjusted_by: str                             # User ID of HR who made the change
    adjusted_by_name: str
    year: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "employee_id": "65emp001abc",
                "employee_name": "Rahul Verma",
                "leave_type_code": "CL",
                "leave_type_name": "Casual Leave",
                "action": "credit",
                "days": 2,
                "reason": "Comp off for weekend work",
                "adjusted_by": "65hr001abc",
                "adjusted_by_name": "Pranavi",
                "year": 2025
            }
        }


# ---------------------------------------------------------------------------
# Leave Approval Workflow Configuration
# ---------------------------------------------------------------------------

class ApprovalLevelConfig(BaseModel):
    """Single level in approval chain"""
    level: int                                   # 1, 2, 3...
    approver_type: str                           # reporting_manager | hr_admin | org_admin | specific_user
    approver_id: Optional[str] = None            # User ID if approver_type is specific_user
    approver_name: Optional[str] = None          # Display name
    can_skip: bool = False                       # If true, can auto-skip if approver not assigned


class AutoApprovalRule(BaseModel):
    """Rules for auto-approving leaves"""
    enabled: bool = False
    max_days: int = 0                            # Auto-approve if days <= this
    leave_types: Optional[List[str]] = None      # Apply only to these types, None = all


class LeaveApprovalWorkflowModel(BaseModel):
    """Approval workflow config per organization — stored in db.leave_approval_workflows"""
    organization_id: str
    name: str = "Default Workflow"
    levels: List[dict] = []                      # List of ApprovalLevelConfig dicts
    auto_approval: Optional[dict] = None         # AutoApprovalRule dict
    is_active: bool = True
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "name": "Default Workflow",
                "levels": [
                    {"level": 1, "approver_type": "reporting_manager", "can_skip": False},
                    {"level": 2, "approver_type": "hr_admin", "can_skip": False}
                ],
                "auto_approval": {
                    "enabled": True,
                    "max_days": 1,
                    "leave_types": ["CL"]
                }
            }
        }
