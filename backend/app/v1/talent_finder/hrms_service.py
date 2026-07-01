"""
HRMS TalentFinder Service
Integrates AI resume matching with HRMS employee data.
HR uploads JD → selects department → system fetches employee resumes → runs AI matching
"""

import os
import httpx
import asyncio
from datetime import datetime
from fastapi import HTTPException, UploadFile
from bson import ObjectId
from app.database import get_database
from app.utils.logger import logger

from app.v1.talent_finder.parser import ResumeParser
from app.v1.talent_finder.section_detector import SectionDetector
from app.v1.talent_finder.extractor import InformationExtractor
from app.v1.talent_finder.skills_extractor import SkillsExtractor
from app.v1.talent_finder.experience_extractor import ExperienceExtractor
from app.v1.talent_finder.education_extractor import EducationExtractor
from app.v1.talent_finder.embeddings import EmbeddingService
from app.v1.talent_finder.scoring import ATSScorer
from app.v1.talent_finder.ranking import RankingService
from app.v1.talent_finder.reranker import Reranker
from app.v1.talent_finder.benchmarker import CandidateBenchmarker
from app.v1.talent_finder.groq_service import GroqExplanationService


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


class HRMSTalentFinderService:
    def __init__(self, db=None):
        self.db = db if db is not None else get_database()
        self._embedding_service = None

    def _org_id(self, user: dict, explicit: str = None) -> str:
        if user.get("role") == "superadmin":
            if not explicit: raise HTTPException(status_code=400, detail="superadmin must supply organization_id")
            return explicit
        return user.get("organization_id") or ""

    def _get_embedding_service(self) -> EmbeddingService:
        if not self._embedding_service:
            model_name = os.getenv("MODEL_NAME", "BAAI/bge-base-en-v1.5")
            self._embedding_service = EmbeddingService(model_name)
        return self._embedding_service

    # ------------------------------------------------------------------
    # MAIN: Run talent search
    # ------------------------------------------------------------------

    async def run_talent_search(
        self, jd_file: UploadFile, department: str, employee_ids: list,
        top_n: int, title: str, current_user: dict, org_id_param: str = None
    ) -> dict:
        """
        Main talent finder flow:
        1. Parse uploaded JD
        2. Get employees from HRMS (department or specific IDs)
        3. Fetch their resumes from personal_details.resume_url
        4. Run AI matching pipeline
        5. Save results to db.talent_search_results
        6. Return ranked candidates
        """
        org_id = self._org_id(current_user, org_id_param)

        # Step 1: Parse JD
        parser = ResumeParser()
        jd_content = await jd_file.read()
        try:
            if jd_file.filename.endswith('.pdf'):
                jd_text = parser.parse_pdf(jd_content)
            elif jd_file.filename.endswith('.docx'):
                jd_text = parser.parse_docx(jd_content)
            else:
                jd_text = jd_content.decode('utf-8', errors='ignore')
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse JD: {str(e)}")

        if not jd_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from JD")

        # Step 2: Get employees
        query = {"organization_id": org_id, "is_deleted": False, "status": "active"}
        if employee_ids:
            try:
                query["_id"] = {"$in": [ObjectId(eid) for eid in employee_ids]}
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid employee ID format")
        elif department:
            query["department"] = {"$regex": department, "$options": "i"}

        employees = await self.db.employees.find(query).to_list(200)
        if not employees:
            raise HTTPException(status_code=404, detail="No active employees found for given criteria")

        # Step 3: Fetch resumes
        candidates_with_resumes = []
        employees_without_resume = []

        for emp in employees:
            personal_details = emp.get("personal_details", {}) or {}
            resume_url = personal_details.get("resume_url")

            if not resume_url:
                employees_without_resume.append(f"{emp['first_name']} {emp['last_name']}")
                continue

            # Fetch resume content from Cloudinary URL
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(resume_url)
                    if resp.status_code == 200:
                        resume_content = resp.content
                        # Detect file type from URL
                        if resume_url.lower().endswith('.pdf') or 'pdf' in resume_url.lower():
                            resume_text = parser.parse_pdf(resume_content)
                        elif resume_url.lower().endswith('.docx'):
                            resume_text = parser.parse_docx(resume_content)
                        else:
                            resume_text = resp.text

                        if resume_text.strip():
                            candidates_with_resumes.append({
                                "employee_id": str(emp["_id"]),
                                "employee_code": emp.get("employee_id", ""),
                                "filename": f"{emp['first_name']}_{emp['last_name']}_resume",
                                "raw_text": resume_text,
                                "emp_data": emp
                            })
            except Exception as e:
                logger.warning(f"Failed to fetch resume for {emp['first_name']}: {e}")
                employees_without_resume.append(f"{emp['first_name']} {emp['last_name']}")

        if not candidates_with_resumes:
            raise HTTPException(
                status_code=400,
                detail=f"No resumes found. Employees without resume: {', '.join(employees_without_resume)}"
            )

        # Step 4: Run AI pipeline
        section_detector = SectionDetector()
        extractor = InformationExtractor()
        skills_extractor = SkillsExtractor()
        experience_extractor = ExperienceExtractor()
        education_extractor = EducationExtractor()

        # Extract JD info
        jd_skills = skills_extractor.extract_skills(jd_text)
        jd_experience = experience_extractor.extract_experience(jd_text)

        # Process each candidate
        candidates = []
        for cand in candidates_with_resumes:
            text = cand["raw_text"]
            emp = cand["emp_data"]
            try:
                sections = section_detector.detect_sections(text)
                info = extractor.extract_info(text)
                # Override with actual HRMS data
                info["name"] = f"{emp['first_name']} {emp['last_name']}"
                info["email"] = emp.get("official_email", info.get("email", ""))
                info["phone"] = emp.get("phone", info.get("phone", ""))

                skills = skills_extractor.extract_skills(text)
                experience = experience_extractor.extract_experience(text)
                education = education_extractor.extract_education(text)

                candidates.append({
                    "employee_id": cand["employee_id"],
                    "employee_code": cand["employee_code"],
                    "department": emp.get("department", ""),
                    "designation": emp.get("designation", ""),
                    "filename": cand["filename"],
                    "raw_text": text,
                    "sections": sections,
                    "info": info,
                    "skills": skills,
                    "experience": experience,
                    "education": education
                })
            except Exception as e:
                logger.warning(f"Error processing {emp['first_name']}: {e}")

        if not candidates:
            raise HTTPException(status_code=500, detail="Failed to process any resumes")

        # Score
        embedding_service = self._get_embedding_service()
        scorer = ATSScorer(embedding_service)
        scored = scorer.score_all(jd_text, jd_skills, jd_experience, candidates)

        # Rank
        ranking_service = RankingService()
        ranked = ranking_service.rank(scored)

        # Rerank
        reranker = Reranker()
        reranked = reranker.rerank(ranked, jd_text, jd_skills)

        # Benchmark
        benchmarker = CandidateBenchmarker()
        reranked = benchmarker.benchmark_all(reranked, jd_skills)

        # LLM explanations (top N only)
        max_llm = min(int(os.getenv("MAX_LLM_CANDIDATES", "5")), len(reranked))
        groq_service = GroqExplanationService()
        top = reranked[:max_llm]
        explained = await groq_service.generate_explanations(top, jd_text, jd_skills)
        for i, c in enumerate(reranked):
            if i < len(explained):
                c.update(explained[i])

        # Apply verdict
        for c in reranked:
            score_pct = c.get("final_score", 0) * 100
            llm_verdict = c.get("recruiter_verdict", "")
            if score_pct >= 60:
                if llm_verdict == "pass": c["recruiter_verdict"] = "maybe"
                elif not llm_verdict: c["recruiter_verdict"] = "shortlist"
            elif score_pct >= 40:
                if not llm_verdict: c["recruiter_verdict"] = "maybe"
            else:
                c["recruiter_verdict"] = "pass"

        # Format results
        results = []
        for i, c in enumerate(reranked):
            results.append({
                "rank": i + 1,
                "employee_id": c.get("employee_id", ""),
                "employee_code": c.get("employee_code", ""),
                "match_score": round(c.get("final_score", 0) * 100, 1),
                "candidate_name": c.get("info", {}).get("name", ""),
                "email": c.get("info", {}).get("email", ""),
                "phone": c.get("info", {}).get("phone", ""),
                "department": c.get("department", ""),
                "designation": c.get("designation", ""),
                "skills": c.get("skills", []),
                "matched_skills": c.get("matched_skills", []),
                "missing_skills": c.get("missing_skills", []),
                "inferred_skills": c.get("inferred_skills", []),
                "experience_years": c.get("experience", {}).get("total_years", 0),
                "seniority_level": c.get("experience", {}).get("seniority", ""),
                "education": c.get("education", {}),
                "strengths": c.get("strengths", []),
                "weaknesses": c.get("weaknesses", []),
                "summary": c.get("summary", ""),
                "why_top_ranked": c.get("why_top_ranked", ""),
                "recruiter_verdict": c.get("recruiter_verdict", ""),
                "improvement_suggestion": c.get("improvement_suggestion", ""),
                "semantic_score": round(c.get("semantic_score", 0), 2),
                "skills_score": round(c.get("skills_score", 0), 2),
                "experience_score": round(c.get("experience_score", 0), 2),
                "education_score": round(c.get("education_score", 0), 2),
                "project_score": round(c.get("project_score", 0), 2),
                "achievement_score": round(c.get("achievement_score", 0), 2),
                "percentile": c.get("percentile", 0),
                "fraud_score": c.get("fraud_score", 0),
                "is_suspicious": c.get("is_suspicious", False),
                "fraud_flags": c.get("fraud_flags", []),
            })

        # Apply top_n filter
        if top_n > 0:
            results = results[:top_n]

        job_title = extractor.extract_job_title(jd_text) or title or "Position"

        # Step 5: Save to DB
        search_record = {
            "organization_id": org_id,
            "title": title or job_title,
            "department": department,
            "employee_ids": employee_ids or [],
            "jd_filename": jd_file.filename,
            "total_candidates": len(candidates),
            "results": results,
            "required_skills": jd_skills,
            "employees_without_resume": employees_without_resume,
            "created_by": str(current_user["_id"]),
            "created_by_name": current_user.get("full_name", current_user.get("email", "")),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await self.db.talent_search_results.insert_one(search_record)

        logger.info(f"Talent search completed: {len(results)} results for org {org_id}")

        return {
            "title": job_title,
            "department": department,
            "total_candidates": len(candidates),
            "showing": len(results),
            "required_skills": jd_skills,
            "results": results,
            "employees_without_resume": employees_without_resume
        }

    # ------------------------------------------------------------------
    # GET HISTORY
    # ------------------------------------------------------------------

    async def get_search_history(
        self, current_user: dict, page: int = 1, limit: int = 20,
        org_id_param: str = None
    ) -> dict:
        from app.utils.helpers import paginate_query
        org_id = self._org_id(current_user, org_id_param)
        skip, limit = paginate_query(page, limit)

        total = await self.db.talent_search_results.count_documents({"organization_id": org_id})
        cursor = self.db.talent_search_results.find(
            {"organization_id": org_id},
            {"results": 0}  # exclude full results from list
        ).skip(skip).limit(limit).sort("created_at", -1)
        records = await cursor.to_list(length=limit)
        for r in records:
            _serialize(r)

        return {"searches": records, "total": total, "page": page, "pages": (total + limit - 1) // limit}

    async def get_search_detail(self, search_id: str, current_user: dict) -> dict:
        org_id = self._org_id(current_user)
        try:
            obj_id = ObjectId(search_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid search ID")

        record = await self.db.talent_search_results.find_one({"_id": obj_id, "organization_id": org_id})
        if not record:
            raise HTTPException(status_code=404, detail="Search not found")
        return _serialize(record)
