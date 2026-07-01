"""
Section Detection Service
Rule-based section detection with fuzzy matching
"""

import re
from rapidfuzz import fuzz


class SectionDetector:
    """Detects resume sections using heading heuristics and fuzzy matching"""

    # Section name mappings for normalization
    SECTION_MAPPINGS = {
        "skills": [
            "skills", "technical skills", "expertise", "core competencies",
            "technologies", "tech stack", "proficiencies", "tools",
            "programming languages", "frameworks", "technical expertise",
            "key skills", "professional skills", "competencies"
        ],
        "experience": [
            "experience", "professional experience", "employment history",
            "work history", "work experience", "career history",
            "professional background", "employment", "positions held"
        ],
        "education": [
            "education", "academic background", "qualifications",
            "academic qualifications", "educational background",
            "academic history", "degrees", "schooling"
        ],
        "projects": [
            "projects", "portfolio", "personal projects",
            "academic projects", "key projects", "notable projects",
            "side projects", "project experience"
        ],
        "certifications": [
            "certifications", "credentials", "licenses",
            "professional certifications", "certificates",
            "training", "courses", "professional development"
        ],
        "summary": [
            "summary", "professional summary", "objective",
            "career objective", "profile", "about me",
            "personal statement", "career summary", "overview"
        ],
        "achievements": [
            "achievements", "accomplishments", "awards",
            "honors", "recognition", "highlights"
        ],
        "publications": [
            "publications", "papers", "research",
            "research papers", "articles"
        ]
    }

    # Minimum fuzzy match score to consider a match
    FUZZY_THRESHOLD = 75

    def detect_sections(self, text: str) -> dict:
        """
        Detect and extract sections from resume text.
        Returns dict mapping section names to their content.
        """
        lines = text.split('\n')
        sections = {}
        current_section = "header"
        current_content = []

        for line in lines:
            detected = self._is_section_heading(line)
            if detected:
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = detected
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections

    def _is_section_heading(self, line: str) -> str | None:
        """
        Check if a line is a section heading.
        Returns normalized section name or None.
        """
        stripped = line.strip()

        # Skip empty lines or very long lines (not headings)
        if not stripped or len(stripped) > 60:
            return None

        # Skip lines that look like content (contain too many words)
        if len(stripped.split()) > 6:
            return None

        # Remove common heading decorators
        cleaned = re.sub(r'[:\-_|#*=]+$', '', stripped).strip()
        cleaned = re.sub(r'^[:\-_|#*=]+', '', cleaned).strip()
        cleaned_lower = cleaned.lower()

        # Check against section mappings using fuzzy matching
        for section_name, variants in self.SECTION_MAPPINGS.items():
            # Exact match first
            if cleaned_lower in variants:
                return section_name

            # Fuzzy match
            for variant in variants:
                score = fuzz.ratio(cleaned_lower, variant)
                if score >= self.FUZZY_THRESHOLD:
                    return section_name

        return None

    def get_section_text(self, sections: dict, section_name: str) -> str:
        """Get text for a specific section, returns empty string if not found"""
        return sections.get(section_name, "")
