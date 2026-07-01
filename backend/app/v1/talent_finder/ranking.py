"""
Ranking Service
Sorts candidates by final ATS score with tie-breaking logic
"""

from typing import List, Dict


class RankingService:
    """Ranks candidates based on their ATS scores"""

    def rank(self, scored_candidates: List[Dict]) -> List[Dict]:
        """
        Rank candidates by final_score with intelligent tie-breaking.
        Tie-breaking priority:
        1. Skills match score (most important for ATS)
        2. Semantic similarity
        3. Experience match
        """
        ranked = sorted(
            scored_candidates,
            key=lambda c: (
                c.get("final_score", 0),
                c.get("skills_score", 0),
                c.get("semantic_score", 0),
                c.get("experience_score", 0),
            ),
            reverse=True
        )

        # Assign ranks
        for i, candidate in enumerate(ranked):
            candidate["rank"] = i + 1

        return ranked

    def get_top_n(self, ranked_candidates: List[Dict], n: int) -> List[Dict]:
        """Get top N candidates"""
        return ranked_candidates[:n]

    def get_score_distribution(self, ranked_candidates: List[Dict]) -> Dict:
        """Get score distribution statistics"""
        if not ranked_candidates:
            return {"min": 0, "max": 0, "avg": 0, "median": 0}

        scores = [c.get("final_score", 0) for c in ranked_candidates]
        scores.sort()

        return {
            "min": round(scores[0] * 100, 1),
            "max": round(scores[-1] * 100, 1),
            "avg": round(sum(scores) / len(scores) * 100, 1),
            "median": round(scores[len(scores) // 2] * 100, 1),
            "total": len(scores)
        }
