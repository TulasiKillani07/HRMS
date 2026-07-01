"""
Fraud & Buzzword Detection Service
Detects keyword stuffing, unrealistic claims, and suspicious patterns
"""

import re
from typing import Dict, List
from collections import Counter


class FraudDetector:
    """
    Detects suspicious resume patterns:
    - Keyword stuffing (same skill repeated excessively)
    - Buzzword density (too many buzzwords, no substance)
    - Unrealistic experience claims
    - Copy-paste indicators
    """

    # Buzzwords that are suspicious when overused without supporting context
    BUZZWORDS = [
        "innovative", "synergy", "leverage", "paradigm", "disruptive",
        "cutting-edge", "state-of-the-art", "world-class", "best-in-class",
        "thought leader", "visionary", "guru", "ninja", "rockstar",
        "passionate", "self-starter", "go-getter", "results-driven",
        "detail-oriented", "team player", "proactive",
    ]

    # Maximum reasonable repetitions of a skill keyword
    MAX_SKILL_REPETITIONS = 5

    # Suspicious patterns
    SUSPICIOUS_PATTERNS = [
        # Hidden text (white text on white background trick - shows as repeated keywords)
        r'(\b\w+\b)(?:\s+\1){4,}',  # Same word repeated 5+ times consecutively
        # Unrealistic years of experience for newer technologies
    ]

    # Technologies with max realistic experience years (as of 2026)
    TECH_MAX_YEARS = {
        "langchain": 3, "chatgpt": 3, "gpt-4": 3, "llama": 2,
        "generative ai": 4, "stable diffusion": 3, "midjourney": 3,
        "github copilot": 3, "bard": 2, "gemini": 2,
        "next.js 13": 3, "next.js 14": 2, "react 18": 4,
        "kubernetes": 10, "docker": 11, "terraform": 9,
        "pytorch": 8, "tensorflow": 10,
    }

    def analyze(self, text: str, skills: List[str], experience_years: float) -> Dict:
        """
        Analyze resume for fraud signals.
        Returns fraud score (0 = clean, 1 = highly suspicious) and flags.
        """
        flags = []
        penalty = 0.0

        # Check 1: Keyword stuffing
        stuffing_result = self._detect_keyword_stuffing(text, skills)
        if stuffing_result["is_stuffed"]:
            flags.append(f"Keyword stuffing detected: {', '.join(stuffing_result['stuffed_skills'])}")
            penalty += 0.15

        # Check 2: Buzzword density
        buzzword_result = self._detect_buzzword_overuse(text)
        if buzzword_result["is_excessive"]:
            flags.append(f"High buzzword density ({buzzword_result['count']} buzzwords)")
            penalty += 0.05

        # Check 3: Unrealistic experience claims for newer tech
        unrealistic = self._detect_unrealistic_claims(text, experience_years)
        if unrealistic["has_unrealistic"]:
            flags.extend(unrealistic["claims"])
            penalty += 0.10

        # Check 4: Skill-to-content ratio (many skills listed but no project/experience detail)
        ratio_result = self._check_skill_content_ratio(text, skills)
        if ratio_result["is_suspicious"]:
            flags.append("Many skills listed but minimal supporting experience/projects")
            penalty += 0.08

        # Check 5: Consecutive word repetition (hidden text trick)
        repetition = self._detect_repetition(text)
        if repetition:
            flags.append("Suspicious text repetition detected")
            penalty += 0.20

        fraud_score = min(1.0, penalty)
        is_suspicious = fraud_score > 0.15

        return {
            "fraud_score": fraud_score,
            "is_suspicious": is_suspicious,
            "flags": flags,
            "confidence_penalty": min(0.15, penalty),  # Cap penalty applied to final score
        }

    def _detect_keyword_stuffing(self, text: str, skills: List[str]) -> Dict:
        """Detect if skills are repeated excessively"""
        text_lower = text.lower()
        stuffed = []

        for skill in skills:
            skill_lower = skill.lower()
            count = len(re.findall(r'\b' + re.escape(skill_lower) + r'\b', text_lower))
            if count > self.MAX_SKILL_REPETITIONS:
                stuffed.append(f"{skill} ({count}x)")

        return {
            "is_stuffed": len(stuffed) > 0,
            "stuffed_skills": stuffed,
        }

    def _detect_buzzword_overuse(self, text: str) -> Dict:
        """Detect excessive buzzword usage"""
        text_lower = text.lower()
        count = sum(1 for bw in self.BUZZWORDS if bw in text_lower)
        word_count = len(text.split())

        # More than 5 buzzwords per 500 words is suspicious
        density = count / max(1, word_count / 500)
        is_excessive = density > 5 or count > 8

        return {
            "count": count,
            "density": round(density, 2),
            "is_excessive": is_excessive,
        }

    def _detect_unrealistic_claims(self, text: str, total_years: float) -> Dict:
        """Detect unrealistic experience claims for newer technologies"""
        text_lower = text.lower()
        claims = []

        for tech, max_years in self.TECH_MAX_YEARS.items():
            # Look for patterns like "5 years of LangChain" or "LangChain (5 years)"
            patterns = [
                r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?' + re.escape(tech),
                re.escape(tech) + r'\s*[\(\|:]\s*(\d+)\s*(?:years?|yrs?)',
            ]
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    claimed = int(match.group(1))
                    if claimed > max_years:
                        claims.append(
                            f"Claims {claimed} years of {tech} (max realistic: {max_years})"
                        )

        return {
            "has_unrealistic": len(claims) > 0,
            "claims": claims,
        }

    def _check_skill_content_ratio(self, text: str, skills: List[str]) -> Dict:
        """
        Check if many skills are listed but there's minimal supporting content.
        A resume with 30 skills but only 200 words of experience is suspicious.
        """
        word_count = len(text.split())
        skill_count = len(skills)

        # Ratio: words per skill. Less than 30 words per skill is suspicious
        if skill_count > 0:
            ratio = word_count / skill_count
            is_suspicious = skill_count > 15 and ratio < 25
        else:
            is_suspicious = False
            ratio = 0

        return {
            "is_suspicious": is_suspicious,
            "ratio": round(ratio, 1),
            "skill_count": skill_count,
            "word_count": word_count,
        }

    def _detect_repetition(self, text: str) -> bool:
        """Detect suspicious consecutive word repetition"""
        # Find any word repeated 5+ times consecutively
        match = re.search(r'(\b\w{3,}\b)(?:\s+\1){4,}', text, re.IGNORECASE)
        return match is not None
