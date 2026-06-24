from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ---------------------------------------------------------------------------
# Performance Cycle Schemas
# ---------------------------------------------------------------------------

class CycleCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Q2 2025",
                "start_date": "2025-04-01",
                "end_date": "2025-06-30"
            }
        }


class CycleUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, description="draft | active | review | closed")
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class CycleResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    start_date: str
    end_date: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class CycleListResponse(BaseModel):
    cycles: List[Any]
    total: int


# ---------------------------------------------------------------------------
# OKR Schemas
# ---------------------------------------------------------------------------

class KeyResultRequest(BaseModel):
    title: str = Field(..., min_length=5)
    target: float = Field(..., gt=0)
    current: float = Field(0.0, ge=0)
    unit: str = Field(..., min_length=1, max_length=50)
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Reduce production bugs to under 5/month",
                "target": 5,
                "current": 0,
                "unit": "bugs/month"
            }
        }


class ObjectiveRequest(BaseModel):
    title: str = Field(..., min_length=5)
    description: Optional[str] = None
    weight: int = Field(..., ge=1, le=100, description="Percentage weight")
    key_results: List[KeyResultRequest] = Field(..., min_items=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Improve platform stability",
                "description": "Reduce bugs and improve uptime",
                "weight": 60,
                "key_results": [
                    {
                        "title": "Reduce bugs to <5/month",
                        "target": 5,
                        "unit": "bugs/month"
                    }
                ]
            }
        }


class OKRCreateRequest(BaseModel):
    cycle_id: str
    employee_id: Optional[str] = Field(
        None,
        description="Required for HR/admin. Employee role omits (auto-inferred from token)"
    )
    objectives: List[ObjectiveRequest] = Field(..., min_items=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "cycle_id": "65cycle789abc",
                "employee_id": "65emp001abc",
                "objectives": [
                    {
                        "title": "Improve platform stability",
                        "description": "Reduce bugs and improve uptime",
                        "weight": 60,
                        "key_results": [
                            {"title": "Reduce bugs to <5/month", "target": 5, "unit": "bugs/month"},
                            {"title": "99.9% uptime", "target": 99.9, "unit": "%"}
                        ]
                    }
                ]
            }
        }


class KeyResultUpdateRequest(BaseModel):
    id: str
    current: Optional[float] = None
    title: Optional[str] = None
    target: Optional[float] = None
    unit: Optional[str] = None


class ObjectiveUpdateRequest(BaseModel):
    id: Optional[str] = None  # Existing objective ID, or None for new
    title: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[int] = None
    key_results: Optional[List[KeyResultUpdateRequest]] = None


class OKRUpdateRequest(BaseModel):
    objectives: Optional[List[ObjectiveUpdateRequest]] = None
    status: Optional[str] = Field(None, description="draft | in_progress | self_reviewed | manager_reviewed | closed")


class OKRResponse(BaseModel):
    id: str
    organization_id: str
    cycle_id: str
    employee_id: str
    employee_name: str
    department: str
    objectives: List[Any]
    overall_progress: float
    status: str
    created_at: datetime
    updated_at: datetime


class OKRListItem(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    department: str
    overall_progress: float
    status: str
    objectives_count: int
    cycle_name: str


class OKRListResponse(BaseModel):
    okrs: List[Any]
    total: int
    page: int
    limit: int
    pages: int


# ---------------------------------------------------------------------------
# Performance Review Schemas
# ---------------------------------------------------------------------------

class CompetenciesRequest(BaseModel):
    communication: Optional[float] = Field(None, ge=1, le=5)
    leadership: Optional[float] = Field(None, ge=1, le=5)
    problem_solving: Optional[float] = Field(None, ge=1, le=5)
    teamwork: Optional[float] = Field(None, ge=1, le=5)
    technical: Optional[float] = Field(None, ge=1, le=5)


class ReviewSubmitRequest(BaseModel):
    cycle_id: str
    employee_id: Optional[str] = Field(
        None,
        description="Required for manager review. Employee omits (self-review)"
    )
    
    # Self-review fields
    self_rating: Optional[float] = Field(None, ge=1, le=5)
    self_comments: Optional[str] = None
    
    # Manager review fields
    manager_rating: Optional[float] = Field(None, ge=1, le=5)
    manager_comments: Optional[str] = None
    
    # Competencies (can be filled by employee or manager)
    competencies: Optional[CompetenciesRequest] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "cycle_id": "65cycle789abc",
                "self_rating": 4.0,
                "self_comments": "Good quarter overall",
                "competencies": {
                    "communication": 4,
                    "leadership": 3,
                    "problem_solving": 5,
                    "teamwork": 4,
                    "technical": 5
                }
            }
        }


class ReviewResponse(BaseModel):
    id: str
    organization_id: str
    cycle_id: str
    employee_id: str
    employee_name: str
    self_rating: Optional[float]
    manager_rating: Optional[float]
    final_rating: Optional[float]
    status: str
    created_at: datetime
    updated_at: datetime


class ReviewListItem(BaseModel):
    id: str
    employee_name: str
    department: str
    self_rating: Optional[float]
    manager_rating: Optional[float]
    final_rating: Optional[float]
    status: str


class ReviewListResponse(BaseModel):
    reviews: List[Any]
    total: int


# ---------------------------------------------------------------------------
# Analytics Schemas
# ---------------------------------------------------------------------------

class LeaderboardEntry(BaseModel):
    rank: int
    employee_name: str
    employee_id: str
    department: str
    final_rating: Optional[float]
    okr_progress: float


class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardEntry]


class AnalyticsResponse(BaseModel):
    distribution: Dict[str, int]  # exceeds, meets, below
    department_avg: Dict[str, float]
    avg_rating: float
    total_reviewed: int
