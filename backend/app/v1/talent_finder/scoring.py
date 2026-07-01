"""
ATS Scoring Service - Enhanced v2
Hybrid deterministic + semantic scoring with:
- Section-level semantic matching (not merged)
- Role-aware skill weighting
- Inferred skills from ontology
- Achievement/impact detection
- Fraud/buzzword detection
- Temporal weighting (recent experience matters more)
- Skill confidence scoring
"""

from typing import List, Dict
from app.v1.talent_finder.embeddings import EmbeddingService
from app.v1.talent_finder.skills_extractor import SkillsExtractor
from app.v1.talent_finder.experience_extractor import ExperienceExtractor
from app.v1.talent_finder.education_extractor import EducationExtractor
from app.v1.talent_finder.skill_ontology import SkillOntology
from app.v1.talent_finder.achievement_detector import AchievementDetector
from app.v1.talent_finder.fraud_detector import FraudDetector
from app.v1.talent_finder.temporal_scorer import TemporalScorer


class ATSScorer:
    """
    Enhanced hybrid ATS scoring combining:
    - Section-level semantic similarity (skills, experience, projects scored independently)
    - Role-aware skill matching (missing React doesn't hurt AI roles)
    - Inferred skills from skill graph
    - Achievement/impact detection
    - Weighted ranking formula
    """

    # Base scoring weights
    WEIGHTS = {
        "semantic": 0.30,
        "skills": 0.25,
        "experience": 0.18,
        "projects": 0.12,
        "achievements": 0.05,
        "education": 0.05,
        "certifications": 0.05,
    }

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        self.skills_extractor = SkillsExtractor()
        self.experience_extractor = ExperienceExtractor()
        self.education_extractor = EducationExtractor()
        self.skill_ontology = SkillOntology()
        self.achievement_detector = AchievementDetector()
        self.fraud_detector = FraudDetector()
        self.temporal_scorer = TemporalScorer()

    def score_all(self, jd_text: str, jd_skills: List[str],
                  jd_experience: Dict, candidates: List[Dict]) -> List[Dict]:
        """Score all candidates against the JD with enhanced pipeline"""
        # Detect role type once for all candidates
        role_type = self.skill_ontology.detect_role_type(jd_text)

        # Get inferred JD skills from ontology
        jd_inferred = self.skill_ontology.get_inferred_skills(jd_skills)

        # PRE-COMPUTE: Generate JD embedding ONCE (not per candidate)
        jd_embedding = self.embedding_service.encode_single(jd_text)

        # BATCH: Collect all texts to embed at once
        all_texts = []
        text_map = []  # Track which texts belong to which candidate/section

        for i, candidate in enumerate(candidates):
            raw_text = candidate.get("raw_text", "")
            sections = candidate.get("sections", {})

            all_texts.append(raw_text)
            text_map.append((i, "full"))

            skills_text = sections.get("skills", "")
            all_texts.append(skills_text if skills_text else "")
            text_map.append((i, "skills"))

            exp_text = sections.get("experience", "")
            all_texts.append(exp_text if exp_text else "")
            text_map.append((i, "experience"))

            proj_text = sections.get("projects", "")
            if not proj_text:
                projects = candidate.get("info", {}).get("projects", [])
                proj_text = " ".join(projects) if projects else ""
            all_texts.append(proj_text)
            text_map.append((i, "projects"))

        # BATCH ENCODE all texts at once (much faster than one-by-one)
        all_embeddings = self.embedding_service.encode(all_texts) if all_texts else []

        # Organize embeddings by candidate
        candidate_embeddings = {}
        for idx, (cand_idx, section_name) in enumerate(text_map):
            if cand_idx not in candidate_embeddings:
                candidate_embeddings[cand_idx] = {}
            candidate_embeddings[cand_idx][section_name] = all_embeddings[idx] if len(all_embeddings) > idx else None

        # Score each candidate using pre-computed embeddings
        scored = []
        for i, candidate in enumerate(candidates):
            embeddings = candidate_embeddings.get(i, {})
            score_result = self._score_candidate(
                jd_text, jd_skills, jd_inferred, jd_experience,
                candidate, role_type, jd_embedding, embeddings
            )
            candidate.update(score_result)
            scored.append(candidate)

        return scored

    def _score_candidate(self, jd_text: str, jd_skills: List[str],
                         jd_inferred: List[str], jd_experience: Dict,
                         candidate: Dict, role_type: str,
                         jd_embedding=None, pre_embeddings: Dict = None) -> Dict:
        """Calculate comprehensive ATS score for a single candidate"""

        # 1. Section-level semantic similarity (using pre-computed embeddings)
        if jd_embedding is not None and pre_embeddings:
            semantic_scores = self._compute_section_semantics_fast(jd_embedding, pre_embeddings)
        else:
            semantic_scores = self._compute_section_semantics(jd_text, candidate)

        # Weighted semantic score from independent sections
        semantic_score = (
            semantic_scores["full_similarity"] * 0.25 +
            semantic_scores["skills_similarity"] * 0.25 +
            semantic_scores["experience_similarity"] * 0.30 +
            semantic_scores["project_similarity"] * 0.20
        )

        # 2. Role-aware skills matching
        candidate_skills = candidate.get("skills", [])

        # Get inferred skills for candidate too
        candidate_inferred = self.skill_ontology.get_inferred_skills(candidate_skills)
        all_candidate_skills = list(set(candidate_skills + candidate_inferred))

        # Match against both explicit and inferred JD skills
        all_jd_skills = list(set(jd_skills + jd_inferred))
        matched_skills = self.skills_extractor.get_matched_skills(all_candidate_skills, all_jd_skills)
        missing_skills = self.skills_extractor.get_missing_skills(all_candidate_skills, jd_skills)

        # Role-aware skill score (missing React doesn't hurt AI roles)
        skills_score = self.skill_ontology.calculate_role_aware_skill_score(
            matched_skills, missing_skills, role_type
        )

        # 3. Experience match score
        candidate_years = candidate.get("experience", {}).get("total_years", 0)
        experience_score = self.experience_extractor.calculate_experience_match(
            candidate_years, jd_text
        )

        # 4. Project relevance - section-level semantic (not keyword overlap)
        project_score = semantic_scores.get("project_similarity", 0.0)
        # Boost if candidate has projects and they're semantically relevant
        projects = candidate.get("info", {}).get("projects", [])
        if projects:
            project_score = max(project_score, 0.3)
            # Additional boost for project count
            if len(projects) >= 3:
                project_score = min(1.0, project_score + 0.1)

        # 5. Achievement/impact detection
        achievement_data = self.achievement_detector.detect_achievements(
            candidate.get("raw_text", "")
        )
        achievement_score = achievement_data.get("impact_score", 0.0)

        # 6. Education match score
        education_score = self.education_extractor.calculate_education_match(
            candidate.get("education", {}), jd_text
        )

        # 7. Certification match score
        certification_score = self._calculate_certification_score(
            candidate.get("info", {}).get("certifications", []), jd_text
        )

        # Calculate final weighted score
        final_score = (
            semantic_score * self.WEIGHTS["semantic"] +
            skills_score * self.WEIGHTS["skills"] +
            experience_score * self.WEIGHTS["experience"] +
            project_score * self.WEIGHTS["projects"] +
            achievement_score * self.WEIGHTS["achievements"] +
            education_score * self.WEIGHTS["education"] +
            certification_score * self.WEIGHTS["certifications"]
        )

        # Apply temporal weighting (recent experience matters more)
        raw_text = candidate.get("raw_text", "")
        temporal_data = self.temporal_scorer.calculate_temporal_score(
            raw_text, candidate.get("experience", {})
        )
        final_score *= temporal_data["temporal_multiplier"]

        # Apply PRIMARY SKILL penalty (missing core framework = hard penalty)
        primary_penalty = self.skill_ontology.calculate_primary_skill_penalty(
            candidate.get("skills", []), role_type
        )
        final_score *= primary_penalty

        # Apply fraud detection penalty
        fraud_data = self.fraud_detector.analyze(
            raw_text, candidate.get("skills", []),
            candidate.get("experience", {}).get("total_years", 0)
        )
        final_score -= fraud_data["confidence_penalty"]
        final_score = max(0.0, min(1.0, final_score))

        return {
            "semantic_score": semantic_score,
            "skills_score": skills_score,
            "experience_score": experience_score,
            "project_score": project_score,
            "achievement_score": achievement_score,
            "education_score": education_score,
            "certification_score": certification_score,
            "final_score": final_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "inferred_skills": candidate_inferred,
            "role_type": role_type,
            "achievements": achievement_data.get("achievements", []),
            "has_quantified_impact": achievement_data.get("has_quantified_impact", False),
            "temporal_multiplier": temporal_data["temporal_multiplier"],
            "recency_score": temporal_data["recency_score"],
            "has_recent_experience": temporal_data["has_recent_experience"],
            "primary_skill_penalty": primary_penalty,
            "fraud_score": fraud_data["fraud_score"],
            "fraud_flags": fraud_data["flags"],
            "is_suspicious": fraud_data["is_suspicious"],
        }

    def _compute_section_semantics(self, jd_text: str, candidate: Dict) -> Dict:
        """Fallback: compute section semantics one-by-one (used if no pre-computed embeddings)"""
        sections = candidate.get("sections", {})
        raw_text = candidate.get("raw_text", "")

        jd_embedding = self.embedding_service.encode_single(jd_text)
        resume_embedding = self.embedding_service.encode_single(raw_text)
        full_similarity = self.embedding_service.compute_similarity(jd_embedding, resume_embedding)

        skills_text = sections.get("skills", "")
        skills_similarity = 0.0
        if skills_text:
            skills_embedding = self.embedding_service.encode_single(skills_text)
            skills_similarity = self.embedding_service.compute_similarity(jd_embedding, skills_embedding)

        exp_text = sections.get("experience", "")
        exp_similarity = 0.0
        if exp_text:
            exp_embedding = self.embedding_service.encode_single(exp_text)
            exp_similarity = self.embedding_service.compute_similarity(jd_embedding, exp_embedding)

        proj_text = sections.get("projects", "")
        proj_similarity = 0.0
        if proj_text:
            proj_embedding = self.embedding_service.encode_single(proj_text)
            proj_similarity = self.embedding_service.compute_similarity(jd_embedding, proj_embedding)
        else:
            projects = candidate.get("info", {}).get("projects", [])
            if projects:
                proj_combined = " ".join(projects)
                proj_embedding = self.embedding_service.encode_single(proj_combined)
                proj_similarity = self.embedding_service.compute_similarity(jd_embedding, proj_embedding)

        return {
            "full_similarity": full_similarity,
            "skills_similarity": skills_similarity,
            "experience_similarity": exp_similarity,
            "project_similarity": proj_similarity,
        }

    def _compute_section_semantics_fast(self, jd_embedding, pre_embeddings: Dict) -> Dict:
        """
        FAST: Compute section semantics using pre-computed batch embeddings.
        No model calls needed — just cosine similarity on cached vectors.
        """
        import numpy as np

        full_emb = pre_embeddings.get("full")
        skills_emb = pre_embeddings.get("skills")
        exp_emb = pre_embeddings.get("experience")
        proj_emb = pre_embeddings.get("projects")

        full_similarity = self.embedding_service.compute_similarity(jd_embedding, full_emb) if full_emb is not None and np.any(full_emb) else 0.0
        skills_similarity = self.embedding_service.compute_similarity(jd_embedding, skills_emb) if skills_emb is not None and np.any(skills_emb) else 0.0
        exp_similarity = self.embedding_service.compute_similarity(jd_embedding, exp_emb) if exp_emb is not None and np.any(exp_emb) else 0.0
        proj_similarity = self.embedding_service.compute_similarity(jd_embedding, proj_emb) if proj_emb is not None and np.any(proj_emb) else 0.0

        return {
            "full_similarity": full_similarity,
            "skills_similarity": skills_similarity,
            "experience_similarity": exp_similarity,
            "project_similarity": proj_similarity,
        }

    def _calculate_certification_score(self, certifications: List[str], jd_text: str) -> float:
        """Calculate certification relevance score"""
        if not certifications:
            return 0.3  # Neutral score if no certs

        jd_lower = jd_text.lower()
        relevant_certs = 0

        cert_keywords = [
            "aws certified", "azure certified", "google certified",
            "pmp", "scrum", "cissp", "comptia", "oracle certified",
            "kubernetes", "terraform", "docker", "tensorflow",
            "databricks", "snowflake"
        ]

        for cert in certifications:
            cert_lower = cert.lower()
            if any(kw in jd_lower for kw in cert_lower.split()):
                relevant_certs += 1
            elif any(kw in cert_lower for kw in cert_keywords):
                relevant_certs += 0.5

        if relevant_certs >= 2:
            return 1.0
        elif relevant_certs >= 1:
            return 0.8
        elif certifications:
            return 0.5
        return 0.3
