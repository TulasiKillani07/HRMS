"""
Reranking Service - Enhanced
Refines initial rankings using:
- Role-aware skill importance
- Achievement signals
- Critical skill matching
- Seniority alignment
Modular architecture ready for bge-reranker-base integration
"""

from typing import List, Dict


class Reranker:
    """
    Enhanced reranker with role-aware precision signals.
    Architecture supports future cross-encoder model integration.
    """

    def rerank(self, ranked_candidates: List[Dict], jd_text: str,
               jd_skills: List[str]) -> List[Dict]:
        """
        Rerank candidates with enhanced precision signals.
        """
        for candidate in ranked_candidates:
            adjustment = self._calculate_adjustment(candidate, jd_text, jd_skills)
            candidate["final_score"] = min(1.0, max(0.0,
                candidate.get("final_score", 0) + adjustment
            ))

        # Re-sort after adjustments
        reranked = sorted(
            ranked_candidates,
            key=lambda c: c.get("final_score", 0),
            reverse=True
        )

        # Reassign ranks
        for i, candidate in enumerate(reranked):
            candidate["rank"] = i + 1

        return reranked

    def _calculate_adjustment(self, candidate: Dict, jd_text: str,
                              jd_skills: List[str]) -> float:
        """
        Calculate score adjustment based on enhanced precision signals.
        """
        adjustment = 0.0

        skills_score = candidate.get("skills_score", 0)
        semantic_score = candidate.get("semantic_score", 0)
        role_type = candidate.get("role_type", "unknown")

        # Signal 1: Well-rounded candidates (high skills + high semantic)
        if skills_score > 0.7 and semantic_score > 0.7:
            adjustment += 0.02

        # Signal 2: Penalize semantic-only matches (similar domain, wrong skills)
        if skills_score < 0.2 and semantic_score > 0.6:
            adjustment -= 0.03

        # Signal 3: Critical skills bonus (first 5 JD skills are most important)
        critical_skills = jd_skills[:5] if jd_skills else []
        matched = candidate.get("matched_skills", [])
        if critical_skills:
            matched_lower = set(s.lower() for s in matched)
            critical_match = sum(1 for s in critical_skills if s.lower() in matched_lower)
            critical_ratio = critical_match / len(critical_skills)
            if critical_ratio > 0.6:
                adjustment += 0.03
            elif critical_ratio < 0.2:
                adjustment -= 0.02

        # Signal 4: Achievement bonus - candidates with quantified impact
        if candidate.get("has_quantified_impact", False):
            adjustment += 0.02
            # Extra bonus for multiple achievements
            if len(candidate.get("achievements", [])) >= 3:
                adjustment += 0.01

        # Signal 5: Inferred skills bonus - candidate has related domain expertise
        inferred = candidate.get("inferred_skills", [])
        if len(inferred) >= 5:
            adjustment += 0.01

        # Signal 6: Experience alignment
        experience_score = candidate.get("experience_score", 0)
        if experience_score > 0.8:
            adjustment += 0.01

        # Signal 7: Penalize if no experience detected but JD requires it
        candidate_years = candidate.get("experience", {}).get("total_years", 0)
        if candidate_years == 0 and "experience" in jd_text.lower():
            adjustment -= 0.03

        # Signal 8: Seniority mismatch penalty
        jd_lower = jd_text.lower()
        candidate_seniority = candidate.get("experience", {}).get("seniority", "unknown")
        if "senior" in jd_lower and candidate_seniority in ("junior", "intern"):
            adjustment -= 0.03
        elif "junior" in jd_lower and candidate_seniority in ("lead", "senior"):
            adjustment -= 0.01  # Slight penalty for overqualified

        # Cap adjustment to prevent large swings
        return max(-0.08, min(0.08, adjustment))
