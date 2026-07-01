"""
Groq LLM Explanation Service - Async
Uses llama-3.1-8b-instant with PARALLEL execution for low latency.
All LLM calls fire simultaneously using asyncio.gather().

IMPORTANT: LLM does NOT perform core ranking - only generates explanations
"""

import os
import json
import asyncio
from typing import List, Dict
from groq import AsyncGroq


class GroqExplanationService:
    """Async recruiter-style explanations using Groq LLM"""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self.client = None
        if self.api_key and self.api_key != "your_groq_api_key_here":
            self.client = AsyncGroq(api_key=self.api_key)

    async def generate_explanations(self, candidates: List[Dict],
                                     jd_text: str, jd_skills: List[str]) -> List[Dict]:
        """
        Generate explanations for top candidates IN PARALLEL.
        All Groq calls fire simultaneously — 5 calls in ~450ms instead of ~2000ms.
        """
        if not self.client:
            return [self._default_explanation(c) for c in candidates]

        # Fire all LLM calls in parallel
        tasks = [
            self._generate_single_async(candidate, jd_text, jd_skills)
            for candidate in candidates
        ]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _generate_single_async(self, candidate: Dict,
                                      jd_text: str, jd_skills: List[str]) -> Dict:
        """Generate explanation for one candidate (async)"""
        try:
            return await self._generate_recruiter_evaluation(candidate, jd_text, jd_skills)
        except Exception as e:
            print(f"Groq API error for {candidate.get('info', {}).get('name', 'Unknown')}: {e}")
            return self._default_explanation(candidate)

        return explained

    async def _generate_recruiter_evaluation(self, candidate: Dict,
                                        jd_text: str, jd_skills: List[str]) -> Dict:
        """
        Generate recruiter-style evaluation (async).
        Asks: "Would a recruiter shortlist this candidate for this role?"
        """
        candidate_name = candidate.get("info", {}).get("name", "Unknown")
        candidate_skills = candidate.get("skills", [])
        matched_skills = candidate.get("matched_skills", [])
        missing_skills = candidate.get("missing_skills", [])
        inferred_skills = candidate.get("inferred_skills", [])
        experience_years = candidate.get("experience", {}).get("total_years", 0)
        seniority = candidate.get("experience", {}).get("seniority", "unknown")
        score = candidate.get("final_score", 0)
        role_type = candidate.get("role_type", "unknown")
        has_impact = candidate.get("has_quantified_impact", False)
        achievements = candidate.get("achievements", [])

        # Build achievement context
        achievement_context = ""
        if achievements:
            achievement_examples = [a.get("context", "") for a in achievements[:3]]
            achievement_context = f"\nQuantified Achievements: {'; '.join(achievement_examples)}"

        prompt = f"""You are a senior technical recruiter evaluating a candidate. Think like a recruiter who has reviewed thousands of resumes.

JOB DESCRIPTION (first 600 chars):
{jd_text[:600]}

CANDIDATE PROFILE:
- Name: {candidate_name}
- ATS Score: {round(score * 100, 1)}%
- Role Type Detected: {role_type}
- Experience: {experience_years} years ({seniority} level)
- Matched Skills: {', '.join(matched_skills[:12])}
- Missing Skills: {', '.join(missing_skills[:8])}
- Inferred Skills (from skill graph): {', '.join(inferred_skills[:8])}
- Has Quantified Impact: {has_impact}{achievement_context}

EVALUATE AS A RECRUITER. Consider:
1. Would you shortlist this candidate? Why?
2. What are their strongest selling points for THIS specific role?
3. What gaps concern you most?
4. What context might explain the gaps (career stage, domain shift)?

Respond in this exact JSON format (no markdown, no code blocks):
{{
    "strengths": ["strength 1", "strength 2", "strength 3"],
    "weaknesses": ["weakness 1", "weakness 2"],
    "summary": "One sentence recruiter summary of the candidate",
    "why_top_ranked": "One sentence explaining fit for this specific role",
    "recruiter_verdict": "shortlist/maybe/pass",
    "improvement_suggestion": "One actionable suggestion for the candidate"
}}

Keep each point concise (under 20 words). Be specific to THIS role, not generic."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert technical recruiter. Evaluate candidates realistically. Always respond with valid JSON only. No markdown formatting."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400,
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON response
        try:
            # Clean potential markdown code blocks
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])
                if content.startswith("json"):
                    content = content[4:]
            parsed = json.loads(content)
            return {
                "strengths": parsed.get("strengths", [])[:5],
                "weaknesses": parsed.get("weaknesses", [])[:3],
                "summary": parsed.get("summary", ""),
                "why_top_ranked": parsed.get("why_top_ranked", ""),
                "recruiter_verdict": parsed.get("recruiter_verdict", ""),
                "improvement_suggestion": parsed.get("improvement_suggestion", ""),
            }
        except json.JSONDecodeError:
            return self._default_explanation(candidate)

    def _default_explanation(self, candidate: Dict) -> Dict:
        """Generate default explanation without LLM - still useful"""
        matched = candidate.get("matched_skills", [])
        missing = candidate.get("missing_skills", [])
        inferred = candidate.get("inferred_skills", [])
        score = candidate.get("final_score", 0)
        years = candidate.get("experience", {}).get("total_years", 0)
        name = candidate.get("info", {}).get("name", "Candidate")
        role_type = candidate.get("role_type", "unknown")
        has_impact = candidate.get("has_quantified_impact", False)

        strengths = []
        if len(matched) > 3:
            strengths.append(f"Strong skills alignment ({len(matched)} matching skills)")
        elif len(matched) > 0:
            strengths.append(f"Partial skills match ({len(matched)} skills)")
        if years >= 5:
            strengths.append(f"Solid experience ({years} years)")
        elif years >= 3:
            strengths.append(f"Relevant experience ({years} years)")
        if candidate.get("semantic_score", 0) > 0.7:
            strengths.append("High semantic relevance to job requirements")
        if has_impact:
            strengths.append("Demonstrates quantified business impact")
        if inferred:
            strengths.append(f"Inferred domain expertise: {', '.join(inferred[:3])}")
        if candidate.get("info", {}).get("certifications"):
            strengths.append("Has relevant certifications")
        if not strengths:
            strengths.append("Meets basic job requirements")

        weaknesses = []
        if missing:
            # Filter missing skills by role relevance
            weaknesses.append(f"Missing skills: {', '.join(missing[:4])}")
        if years < 2 and "senior" in candidate.get("experience", {}).get("seniority", ""):
            weaknesses.append("Experience may not match seniority expectations")
        elif years < 2:
            weaknesses.append("Limited professional experience")
        if not has_impact:
            weaknesses.append("No quantified achievements detected")
        if not weaknesses:
            weaknesses.append("No significant gaps identified")

        summary = f"{name} - {years} years experience, {len(matched)} matching skills, {role_type} profile."
        why = f"Scored {round(score * 100, 1)}% with strong alignment in skills and semantic relevance."

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "summary": summary,
            "why_top_ranked": why,
            "recruiter_verdict": "shortlist" if score > 0.7 else "maybe" if score > 0.5 else "pass",
            "improvement_suggestion": f"Consider adding {', '.join(missing[:2])} to strengthen profile." if missing else "Profile is well-aligned.",
        }
