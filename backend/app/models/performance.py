from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Performance Cycle Model
# ---------------------------------------------------------------------------

class PerformanceCycleModel(BaseModel):
    """Performance review cycle model"""
    organization_id: str
    name: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    status: str = "draft"  # draft | active | review | closed
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "name": "Q2 2025",
                "start_date": "2025-04-01",
                "end_date": "2025-06-30",
                "status": "active",
                "created_by": "65xyz789abc012"
            }
        }


# ---------------------------------------------------------------------------
# OKR Model
# ---------------------------------------------------------------------------

class KeyResultEntry(BaseModel):
    """Individual Key Result"""
    id: str  # UUID
    title: str
    target: float
    current: float = 0.0
    unit: str  # bugs/month, %, count, etc.
    progress: float = 0.0  # Auto-calculated: (current/target) × 100


class ObjectiveEntry(BaseModel):
    """Individual Objective with Key Results"""
    id: str  # UUID
    title: str
    description: Optional[str] = None
    weight: int = Field(..., ge=1, le=100)  # Percentage weight
    key_results: List[KeyResultEntry]
    progress: float = 0.0  # Auto-calculated: average of KR progress


class PerformanceOKRModel(BaseModel):
    """Employee OKR model"""
    organization_id: str
    cycle_id: str
    employee_id: str
    employee_name: str
    department: str
    objectives: List[ObjectiveEntry]
    overall_progress: float = 0.0  # Weighted average of objectives
    status: str = "draft"  # draft | in_progress | self_reviewed | manager_reviewed | closed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "cycle_id": "65cycle789abc",
                "employee_id": "65emp001abc",
                "employee_name": "Rahul Verma",
                "department": "Engineering",
                "objectives": [
                    {
                        "id": "obj-uuid-1",
                        "title": "Improve platform stability",
                        "description": "Reduce bugs and improve uptime",
                        "weight": 60,
                        "key_results": [
                            {
                                "id": "kr-uuid-1",
                                "title": "Reduce production bugs to under 5/month",
                                "target": 5,
                                "current": 3,
                                "unit": "bugs/month",
                                "progress": 100
                            }
                        ]
                    }
                ]
            }
        }


# ---------------------------------------------------------------------------
# Performance Review Model
# ---------------------------------------------------------------------------

class CompetenciesRating(BaseModel):
    """Competency ratings"""
    communication: Optional[float] = Field(None, ge=1, le=5)
    leadership: Optional[float] = Field(None, ge=1, le=5)
    problem_solving: Optional[float] = Field(None, ge=1, le=5)
    teamwork: Optional[float] = Field(None, ge=1, le=5)
    technical: Optional[float] = Field(None, ge=1, le=5)


class PerformanceReviewModel(BaseModel):
    """Performance review model"""
    organization_id: str
    cycle_id: str
    employee_id: str
    employee_name: str
    okr_id: Optional[str] = None  # Reference to OKR
    
    # Self-review
    self_rating: Optional[float] = Field(None, ge=1, le=5)
    self_comments: Optional[str] = None
    
    # Manager review
    manager_id: Optional[str] = None
    manager_rating: Optional[float] = Field(None, ge=1, le=5)
    manager_comments: Optional[str] = None
    
    # HR review (optional)
    hr_rating: Optional[float] = Field(None, ge=1, le=5)
    hr_comments: Optional[str] = None
    
    # Final calculated rating
    final_rating: Optional[float] = None
    
    # Competencies
    competencies: Optional[Dict] = None
    
    status: str = "pending"  # pending | self_reviewed | manager_reviewed | closed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "65abc123def456",
                "cycle_id": "65cycle789abc",
                "employee_id": "65emp001abc",
                "employee_name": "Rahul Verma",
                "self_rating": 4.0,
                "self_comments": "Good quarter, hit most targets",
                "manager_rating": 4.5,
                "manager_comments": "Great on mentoring",
                "final_rating": 4.35,
                "status": "manager_reviewed"
            }
        }
