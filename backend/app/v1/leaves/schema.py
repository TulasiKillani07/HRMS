from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any


# ---------------------------------------------------------------------------
# Leave Type CRUD Schemas
# ---------------------------------------------------------------------------

class LeaveTypeCreateRequest(BaseModel):
    """Add a new leave type to the organization's configuration"""
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=1, max_length=10)
    accrual_type: str = Field("yearly", description="yearly | monthly")
    days_per_year: int = Field(0, ge=-1, description="-1 means unlimited")
    days_per_month: float = Field(0, ge=0, description="If monthly accrual (e.g., 1 CL per month)")
    is_paid: bool = True
    carry_forward: bool = False
    max_carry_forward_days: int = Field(0, ge=0)
    applicable_after_days: int = Field(0, ge=0, description="Available after X days from joining")
    converts_to_lop: bool = Field(True, description="When exhausted, extra leaves become LOP")
    description: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Casual Leave",
                "code": "CL",
                "accrual_type": "monthly",
                "days_per_year": 12,
                "days_per_month": 1,
                "is_paid": True,
                "carry_forward": False,
                "converts_to_lop": True,
                "description": "1 per month, converts to LOP when exhausted"
            }
        }


class LeaveTypeUpdateRequest(BaseModel):
    """Update an existing leave type"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=10)
    accrual_type: Optional[str] = Field(None, description="yearly | monthly")
    days_per_year: Optional[int] = Field(None, ge=-1)
    days_per_month: Optional[float] = Field(None, ge=0)
    is_paid: Optional[bool] = None
    carry_forward: Optional[bool] = None
    max_carry_forward_days: Optional[int] = Field(None, ge=0)
    applicable_after_days: Optional[int] = Field(None, ge=0)
    converts_to_lop: Optional[bool] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    class Config:
        json_schema_extra = {
            "example": {
                "accrual_type": "monthly",
                "days_per_month": 1.5,
                "days_per_year": 18,
                "converts_to_lop": True
            }
        }


class LeaveTypeResponse(BaseModel):
    id: str
    name: str
    code: str
    accrual_type: str = "yearly"
    days_per_year: int
    days_per_month: float = 0
    is_paid: bool
    carry_forward: bool
    max_carry_forward_days: int
    applicable_after_days: int
    converts_to_lop: bool = True
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LeaveConfigurationResponse(BaseModel):
    id: str
    organization_id: str
    year: int
    leave_types: List[Any]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Leave Request Schemas
# ---------------------------------------------------------------------------

class LeaveApplyRequest(BaseModel):
    """Employee applies for leave"""
    leave_type_code: str = Field(..., description="Leave type code (CL, SL, EL, etc.)")
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    reason: str = Field(..., min_length=3, max_length=500)
    is_half_day: bool = Field(False, description="true for half-day leave")
    half_day_type: Optional[str] = Field(None, description="first_half | second_half (required if is_half_day)")
    employee_id: Optional[str] = Field(None, description="HR only: apply on behalf of employee")

    class Config:
        json_schema_extra = {
            "example": {
                "leave_type_code": "CL",
                "start_date": "2025-07-10",
                "end_date": "2025-07-11",
                "reason": "Family function",
                "is_half_day": False
            }
        }


class LeaveApproveRequest(BaseModel):
    """HR approves leave"""
    pass


class LeaveRejectRequest(BaseModel):
    """HR rejects leave with reason"""
    reason: str = Field(..., min_length=3, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Team is short-staffed this week, please reschedule"
            }
        }


class LeaveRequestResponse(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    department: str
    leave_type_code: str
    leave_type_name: str
    start_date: str
    end_date: str
    days: float
    is_half_day: bool
    half_day_type: Optional[str] = None
    reason: str
    status: str
    applied_at: datetime
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    forwarded_to_name: Optional[str] = None
    comments: Optional[List[Any]] = None
    forwards: Optional[List[Any]] = None


class LeaveListResponse(BaseModel):
    leaves: List[Any]
    total: int
    page: int
    limit: int
    pages: int


class LeaveBalanceItem(BaseModel):
    leave_type_code: str
    leave_type_name: str
    total: int
    used: float
    balance: float
    pending: float


class LeaveBalanceResponse(BaseModel):
    employee_id: str
    employee_name: str
    year: int
    balances: List[LeaveBalanceItem]


# ---------------------------------------------------------------------------
# Balance Adjustment Schemas
# ---------------------------------------------------------------------------

class BalanceAdjustRequest(BaseModel):
    """HR adjusts employee leave balance"""
    employee_id: str = Field(..., description="Employee MongoDB ObjectId")
    leave_type_code: str = Field(..., description="Leave type code (CL, SL, etc.)")
    action: str = Field(..., description="credit | deduct | reset")
    days: float = Field(..., gt=0, description="Number of days to credit/deduct (ignored for reset)")
    reason: str = Field(..., min_length=3, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "65emp001abc",
                "leave_type_code": "CL",
                "action": "credit",
                "days": 2,
                "reason": "Comp off for working on Saturday"
            }
        }


class BalanceAdjustResponse(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    leave_type_code: str
    leave_type_name: str
    action: str
    days: float
    reason: str
    adjusted_by_name: str
    new_balance: float
    year: int
    created_at: Any


class BalanceAdjustmentHistoryResponse(BaseModel):
    adjustments: List[Any]
    total: int


# ---------------------------------------------------------------------------
# Forward & Comment Schemas
# ---------------------------------------------------------------------------

class LeaveForwardRequest(BaseModel):
    """Forward leave request to another approver"""
    forward_to: str = Field(..., description="User ID of the person to forward to")
    notes: Optional[str] = Field(None, max_length=500, description="Notes for the approver")

    class Config:
        json_schema_extra = {
            "example": {
                "forward_to": "65user001abc",
                "notes": "Please review this long leave request"
            }
        }


class LeaveCommentRequest(BaseModel):
    """Add comment to a leave request"""
    comment: str = Field(..., min_length=1, max_length=1000)

    class Config:
        json_schema_extra = {
            "example": {
                "comment": "Please provide medical certificate for sick leave > 2 days"
            }
        }


# ---------------------------------------------------------------------------
# Approval Workflow Schemas
# ---------------------------------------------------------------------------

class ApprovalLevelRequest(BaseModel):
    level: int = Field(..., ge=1, le=10)
    approver_type: str = Field(..., description="reporting_manager | hr_admin | org_admin | specific_user")
    approver_id: Optional[str] = Field(None, description="Required if approver_type is specific_user")
    approver_name: Optional[str] = None
    can_skip: bool = Field(False, description="Auto-skip if approver not assigned to employee")


class AutoApprovalRuleRequest(BaseModel):
    enabled: bool = False
    max_days: int = Field(0, ge=0, description="Auto-approve if leave days <= this value")
    leave_types: Optional[List[str]] = Field(None, description="Apply to these types only. Null = all types")


class WorkflowCreateRequest(BaseModel):
    """Create or update approval workflow"""
    name: str = Field("Default Workflow", min_length=2, max_length=200)
    levels: List[ApprovalLevelRequest] = Field(..., min_length=1)
    auto_approval: Optional[AutoApprovalRuleRequest] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Default Workflow",
                "levels": [
                    {"level": 1, "approver_type": "reporting_manager", "can_skip": True},
                    {"level": 2, "approver_type": "hr_admin", "can_skip": False}
                ],
                "auto_approval": {
                    "enabled": True,
                    "max_days": 1,
                    "leave_types": ["CL"]
                }
            }
        }


class WorkflowUpdateRequest(BaseModel):
    """Update approval workflow"""
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    levels: Optional[List[ApprovalLevelRequest]] = None
    auto_approval: Optional[AutoApprovalRuleRequest] = None
    is_active: Optional[bool] = None


class WorkflowResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    levels: List[Any]
    auto_approval: Optional[Any] = None
    is_active: bool
    created_at: Any
    updated_at: Any
