"""
Achievement/Impact Detection Service
Detects quantified achievements, business outcomes, and impact metrics
"""

import re
from typing import List, Dict


class AchievementDetector:
    """
    Detects and scores quantified achievements in resumes.
    Looks for percentages, scale indicators, time savings, and business outcomes.
    """

    # Patterns that indicate quantified impact
    IMPACT_PATTERNS = [
        # Percentage improvements
        (r'(?:improved|increased|boosted|enhanced|grew|raised)\s+.*?(\d+)\s*%', "improvement"),
        (r'(\d+)\s*%\s*(?:improvement|increase|growth|boost|reduction|decrease)', "improvement"),
        (r'(?:reduced|decreased|cut|lowered|minimized)\s+.*?(\d+)\s*%', "reduction"),
        (r'(\d+)\s*%\s*(?:faster|quicker|more efficient)', "efficiency"),

        # Scale indicators
        (r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M)\s*(?:users?|customers?|records?|transactions?|requests?)', "scale_millions"),
        (r'(\d+(?:,\d{3})*(?:K|k))\s*(?:users?|customers?|records?|daily|monthly)', "scale_thousands"),
        (r'(?:served|handled|processed|managed)\s+(\d+(?:,\d{3})*)\s*(?:users?|requests?|transactions?)', "scale"),
        (r'(\d+(?:,\d{3})*)\+?\s*(?:users?|customers?|clients?)', "user_base"),

        # Revenue/cost impact
        (r'\$(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:million|M|K|k)?(?:\s+(?:revenue|savings?|cost))', "revenue"),
        (r'(?:saved|generated|revenue of)\s+\$(\d+(?:,\d{3})*)', "revenue"),

        # Time savings
        (r'(?:reduced|cut|saved)\s+.*?(\d+)\s*(?:hours?|days?|weeks?|months?)', "time_saving"),
        (r'(\d+)x\s*(?:faster|improvement|speedup)', "multiplier"),

        # Accuracy/performance metrics
        (r'(\d+(?:\.\d+)?)\s*%\s*(?:accuracy|precision|recall|F1|AUC)', "ml_metric"),
        (r'(?:accuracy|precision|recall)\s*(?:of|:)?\s*(\d+(?:\.\d+)?)\s*%', "ml_metric"),

        # Team/leadership
        (r'(?:led|managed|mentored)\s+(?:a\s+)?(?:team\s+of\s+)?(\d+)\s*(?:engineers?|developers?|people|members?)', "leadership"),

        # Deployment/production
        (r'(?:deployed|launched|shipped)\s+.*?(?:production|live|prod)', "deployment"),
        (r'(?:production|live)\s+(?:system|service|application)', "deployment"),
    ]

    # Action verbs that indicate strong contributions
    STRONG_ACTION_VERBS = [
        "architected", "designed", "built", "developed", "implemented",
        "led", "spearheaded", "pioneered", "established", "created",
        "optimized", "scaled", "automated", "transformed", "launched",
        "reduced", "improved", "increased", "achieved", "delivered",
    ]

    def detect_achievements(self, text: str) -> Dict:
        """
        Detect and score achievements in resume text.
        Returns achievement details and an impact score.
        """
        achievements = []
        impact_score = 0.0

        for pattern, category in self.IMPACT_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = match.group(1) if match.groups() else ""
                context = self._get_context(text, match.start(), match.end())
                achievements.append({
                    "category": category,
                    "value": value,
                    "context": context,
                })

        # Score based on achievements found
        if achievements:
            # More achievements = higher score, with diminishing returns
            count_score = min(1.0, len(achievements) * 0.15)

            # Bonus for high-impact categories
            category_bonus = 0.0
            categories = [a["category"] for a in achievements]
            if "scale_millions" in categories:
                category_bonus += 0.15
            if "revenue" in categories:
                category_bonus += 0.1
            if "leadership" in categories:
                category_bonus += 0.1
            if "ml_metric" in categories:
                category_bonus += 0.1

            impact_score = min(1.0, count_score + category_bonus)
        else:
            # Check for strong action verbs as a weaker signal
            verb_count = self._count_action_verbs(text)
            impact_score = min(0.4, verb_count * 0.05)

        return {
            "achievements": achievements[:10],  # Top 10
            "achievement_count": len(achievements),
            "impact_score": impact_score,
            "has_quantified_impact": len(achievements) > 0,
        }

    def _get_context(self, text: str, start: int, end: int, window: int = 80) -> str:
        """Get surrounding context for an achievement match"""
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        context = text[ctx_start:ctx_end].strip()
        # Clean up to sentence boundaries if possible
        context = re.sub(r'^\S*\s', '', context)  # Remove partial word at start
        context = re.sub(r'\s\S*$', '', context)  # Remove partial word at end
        return context

    def _count_action_verbs(self, text: str) -> int:
        """Count strong action verbs in text"""
        text_lower = text.lower()
        count = 0
        for verb in self.STRONG_ACTION_VERBS:
            count += len(re.findall(r'\b' + verb + r'\b', text_lower))
        return count
