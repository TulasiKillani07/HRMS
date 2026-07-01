"""
Candidate Benchmarking Service
Compares candidates relative to each other, not just against JD.
Provides percentile rankings and relative positioning.
"""

from typing import List, Dict
import statistics


class CandidateBenchmarker:
    """
    Provides relative benchmarking across the candidate pool:
    - Percentile ranking for each score dimension
    - Skill rarity scoring (rare skills = more valuable)
    - Relative strength identification
    """

    def benchmark_all(self, candidates: List[Dict], jd_skills: List[str]) -> List[Dict]:
        """
        Add benchmarking data to each candidate.
        Must be called AFTER scoring but BEFORE final response formatting.
        """
        if len(candidates) < 2:
            # Not enough candidates to benchmark
            for c in candidates:
                c["percentile"] = 100
                c["skill_rarity_bonus"] = 0.0
                c["relative_strengths"] = []
            return candidates

        # Calculate percentiles for each score dimension
        self._add_percentiles(candidates)

        # Calculate skill rarity (rare skills among this pool = more valuable)
        self._add_skill_rarity(candidates, jd_skills)

        # Identify relative strengths (what makes this candidate stand out)
        self._add_relative_strengths(candidates)

        return candidates

    def _add_percentiles(self, candidates: List[Dict]):
        """Add percentile ranking for overall score"""
        scores = sorted([c.get("final_score", 0) for c in candidates])
        n = len(scores)

        for candidate in candidates:
            score = candidate.get("final_score", 0)
            # Percentile: what % of candidates score below this one
            below = sum(1 for s in scores if s < score)
            percentile = round((below / n) * 100)
            candidate["percentile"] = percentile

    def _add_skill_rarity(self, candidates: List[Dict], jd_skills: List[str]):
        """
        Calculate skill rarity bonus.
        If a candidate has a JD-required skill that few others have, that's more valuable.
        """
        # Count how many candidates have each JD skill
        skill_frequency = {}
        for skill in jd_skills:
            skill_lower = skill.lower()
            count = sum(
                1 for c in candidates
                if skill_lower in [s.lower() for s in c.get("matched_skills", [])]
            )
            skill_frequency[skill] = count

        n = len(candidates)

        for candidate in candidates:
            matched = candidate.get("matched_skills", [])
            rarity_bonus = 0.0

            for skill in matched:
                freq = skill_frequency.get(skill, n)
                # Rarity: if only 1 out of 10 candidates has this skill, it's rare
                if freq > 0:
                    rarity = 1.0 - (freq / n)
                    if rarity > 0.7:  # Skill is rare (< 30% of candidates have it)
                        rarity_bonus += 0.01

            candidate["skill_rarity_bonus"] = min(0.05, rarity_bonus)
            # Apply rarity bonus to final score
            candidate["final_score"] = min(1.0,
                candidate.get("final_score", 0) + candidate["skill_rarity_bonus"]
            )

    def _add_relative_strengths(self, candidates: List[Dict]):
        """Identify what makes each candidate stand out relative to others"""
        # Calculate averages for each dimension
        dimensions = ["semantic_score", "skills_score", "experience_score",
                     "project_score", "achievement_score"]

        averages = {}
        for dim in dimensions:
            values = [c.get(dim, 0) for c in candidates]
            averages[dim] = statistics.mean(values) if values else 0

        dim_labels = {
            "semantic_score": "Semantic relevance",
            "skills_score": "Skills match",
            "experience_score": "Experience fit",
            "project_score": "Project relevance",
            "achievement_score": "Quantified impact",
        }

        for candidate in candidates:
            strengths = []
            for dim in dimensions:
                candidate_val = candidate.get(dim, 0)
                avg_val = averages[dim]
                # If candidate is significantly above average in this dimension
                if candidate_val > avg_val + 0.15:
                    strengths.append(dim_labels[dim])

            candidate["relative_strengths"] = strengths[:3]  # Top 3
