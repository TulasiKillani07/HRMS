"""
Pydantic models for request/response schemas
"""

from pydantic import BaseModel
from typing import List, Optional, Dict


class Education(BaseModel):
    degree: str = ""
    university: str = ""
    graduation_year: str = ""


class CandidateResult(BaseModel):
    rank: int
    match_score: float
    candidate_name: str
    email: str
    phone: str
    skills: List[str]
    matched_skills: List[str]
    missing_skills: List[str]
    experience_years: float
    education: Education
    projects: List[str]
    certifications: List[str]
    strengths: List[str]
    weaknesses: List[str]
    summary: str
    why_top_ranked: str
    semantic_similarity_score: float
    skills_match_score: float
    experience_match_score: float
    education_match_score: float
    project_match_score: float
    certification_match_score: float
    seniority_level: str


class MatchResponse(BaseModel):
    success: bool
    total_candidates: int
    results: List[CandidateResult]
    job_title: str
    required_skills: List[str]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    version: str
