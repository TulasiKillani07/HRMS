"""
Temporal Weighting Service
Recent experience matters more than old experience.
2025 GenAI work > 2019 Java internship
"""

import re
from datetime import datetime
from typing import Dict, List


class TemporalScorer:
    """
    Applies temporal weighting to experience and skills.
    Recent roles and technologies get higher weight.
    """

    # Decay factor per year (0.9 = 10% less weight per year of age)
    DECAY_FACTOR = 0.88

    # Technologies that are "hot" right now (2025-2026) get a recency bonus
    TRENDING_TECH = {
        "LLM", "Generative AI", "LangChain", "RAG", "GPT",
        "Kubernetes", "Terraform", "MLOps", "FastAPI",
        "Next.js", "TypeScript", "Rust", "Go",
    }

    def calculate_temporal_score(self, text: str, experience_data: Dict) -> Dict:
        """
        Calculate temporal relevance score.
        Returns a multiplier (0.7 - 1.2) to apply to the final score.
        """
        current_year = datetime.now().year

        # Extract date ranges from experience
        roles = self._extract_role_dates(text)

        if not roles:
            # No dates found, neutral score
            return {
                "temporal_multiplier": 1.0,
                "recency_score": 0.5,
                "has_recent_experience": False,
                "most_recent_year": None,
            }

        # Calculate weighted recency
        most_recent_year = max(r.get("end_year", current_year) for r in roles)
        years_since_last_role = current_year - most_recent_year

        # Recency score: how recent is their latest experience
        if years_since_last_role <= 0:
            recency_score = 1.0  # Currently employed
        elif years_since_last_role <= 1:
            recency_score = 0.9
        elif years_since_last_role <= 2:
            recency_score = 0.75
        elif years_since_last_role <= 3:
            recency_score = 0.6
        else:
            recency_score = 0.4

        # Calculate experience-weighted score (recent roles count more)
        weighted_months = 0
        total_months = 0
        for role in roles:
            months = role.get("months", 12)
            end_year = role.get("end_year", current_year)
            age = current_year - end_year  # How old is this role

            # Apply decay: recent roles get full weight, old roles get less
            weight = self.DECAY_FACTOR ** age
            weighted_months += months * weight
            total_months += months

        # Temporal multiplier: 0.8 to 1.15
        if total_months > 0:
            temporal_ratio = weighted_months / total_months
            temporal_multiplier = 0.85 + (temporal_ratio * 0.30)
        else:
            temporal_multiplier = 1.0

        # Bonus for trending tech in recent roles
        trending_bonus = self._check_trending_tech(text, roles)
        temporal_multiplier = min(1.15, temporal_multiplier + trending_bonus)

        return {
            "temporal_multiplier": round(temporal_multiplier, 3),
            "recency_score": round(recency_score, 2),
            "has_recent_experience": years_since_last_role <= 1,
            "most_recent_year": most_recent_year,
        }

    def _extract_role_dates(self, text: str) -> List[Dict]:
        """Extract role date ranges from text"""
        current_year = datetime.now().year
        roles = []

        months_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        month_names = '|'.join(months_map.keys())

        # Pattern: "Month Year - Month Year/Present"
        pattern = (
            r'(' + month_names + r')\w*[\s,]*(\d{4})\s*'
            r'[-\u2013\u2014]+\s*'
            r'(?:(' + month_names + r')\w*[\s,]*(\d{4})|present|current|now)'
        )

        for match in re.finditer(pattern, text, re.IGNORECASE):
            start_year = int(match.group(2))
            end_year_str = match.group(4)
            if end_year_str:
                end_year = int(end_year_str)
            else:
                end_year = current_year

            start_month = months_map.get(match.group(1).lower()[:3], 1)
            end_month = months_map.get((match.group(3) or 'dec').lower()[:3], 12)

            months = (end_year - start_year) * 12 + (end_month - start_month)
            if 1 <= months <= 360:
                roles.append({
                    "start_year": start_year,
                    "end_year": end_year,
                    "months": months,
                })

        # Also try "Year - Year/Present"
        year_pattern = r'(\d{4})\s*[-\u2013\u2014]+\s*(\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)'
        for match in re.finditer(year_pattern, text):
            start_year = int(match.group(1))
            end_str = match.group(2).lower()
            end_year = current_year if end_str in ('present', 'current', 'now') else int(end_str)

            if 1990 <= start_year <= current_year and end_year >= start_year:
                months = (end_year - start_year) * 12
                if 1 <= months <= 360:
                    # Avoid duplicates
                    if not any(r["start_year"] == start_year and r["end_year"] == end_year for r in roles):
                        roles.append({
                            "start_year": start_year,
                            "end_year": end_year,
                            "months": months,
                        })

        return roles

    def _check_trending_tech(self, text: str, roles: List[Dict]) -> float:
        """Check if trending tech appears in recent roles"""
        current_year = datetime.now().year
        text_lower = text.lower()

        # Check if any trending tech is mentioned
        trending_found = sum(1 for tech in self.TRENDING_TECH if tech.lower() in text_lower)

        # Check if recent roles exist (within last 2 years)
        has_recent = any(r.get("end_year", 0) >= current_year - 1 for r in roles)

        if trending_found >= 3 and has_recent:
            return 0.05  # Small bonus for trending + recent
        elif trending_found >= 2:
            return 0.02
        return 0.0
