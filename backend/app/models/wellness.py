from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class MoodEntryModel(BaseModel):
    """Daily mood entry — stored in db.wellness_mood_entries"""
    organization_id: str
    employee_id: str
    employee_name: str
    department: str
    date: str                                    # "YYYY-MM-DD"
    score: int                                   # 1-5 (terrible to great)
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WellnessProgramModel(BaseModel):
    """Wellness program — stored in db.wellness_programs"""
    organization_id: str
    name: str
    description: Optional[str] = None
    type: str = "ongoing"                        # ongoing | challenge | event
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    max_participants: Optional[int] = None
    participants: List[str] = []                  # employee_ids
    created_by: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
