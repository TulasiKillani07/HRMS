"""
Education Extraction Service - Fixed
Properly extracts degree, specialization, university, and graduation year
from the education section only (not from the whole resume)
"""

import re
from typing import Dict, List, Optional


class EducationExtractor:
    """Extracts education information from resume text"""

    # Degree patterns ordered by priority (highest first)
    DEGREE_PATTERNS = [
        # PhD
        (r'(?:ph\.?\s*d|doctorate|doctoral)', "PhD"),
        # Master's variants
        (r'm\s*\.?\s*tech(?:nology)?', "M.Tech"),
        (r'm\s*\.?\s*s\s*\.?(?:\s|$|,)', "M.S."),
        (r'm\s*\.?\s*sc\.?', "M.Sc."),
        (r'm\s*\.?\s*e\s*\.?(?:\s|$|,)', "M.E."),
        (r'mba', "MBA"),
        (r'mca', "MCA"),
        (r"master(?:'?s)?(?:\s+of\s+\w+)?", "Master's"),
        # Bachelor's variants - handle "B.Tech", "B .Tech", "B. Tech", "B . Tech"
        (r'b\s*\.?\s*tech(?:nology)?', "B.Tech"),
        (r'b\s*\.?\s*s\s*\.?(?:\s|$|,)', "B.S."),
        (r'b\s*\.?\s*sc\.?', "B.Sc."),
        (r'b\s*\.?\s*e\s*\.?(?:\s|$|,)', "B.E."),
        (r'b\s*\.?\s*eng\.?', "B.Eng"),
        (r'bba', "BBA"),
        (r'bca', "BCA"),
        (r"bachelor(?:'?s)?(?:\s+of\s+\w+)?", "Bachelor's"),
        # Associate/Diploma
        (r'diploma', "Diploma"),
        (r'associate', "Associate"),
    ]

    # Specialization/branch patterns - match these NEAR the degree
    SPECIALIZATIONS = [
        # Engineering branches
        ("computer science and engineering", "Computer Science and Engineering"),
        ("computer science & engineering", "Computer Science and Engineering"),
        ("computer science", "Computer Science"),
        ("information technology", "Information Technology"),
        ("software engineering", "Software Engineering"),
        ("electrical and electronics", "Electrical and Electronics Engineering"),
        ("electrical engineering", "Electrical Engineering"),
        ("electronics and communication", "Electronics and Communication Engineering"),
        ("electronics & communication", "Electronics and Communication Engineering"),
        ("electronics and instrumentation", "Electronics and Instrumentation"),
        ("electronics & instrumentation", "Electronics and Instrumentation"),
        ("electronics and telecommunication", "Electronics and Telecommunication Engineering"),
        ("electronics engineering", "Electronics Engineering"),
        ("mechanical engineering", "Mechanical Engineering"),
        ("civil engineering", "Civil Engineering"),
        ("chemical engineering", "Chemical Engineering"),
        ("aerospace engineering", "Aerospace Engineering"),
        ("biomedical engineering", "Biomedical Engineering"),
        ("artificial intelligence", "Artificial Intelligence"),
        ("data science", "Data Science"),
        ("machine learning", "Machine Learning"),
        # Science
        ("mathematics", "Mathematics"),
        ("statistics", "Statistics"),
        ("physics", "Physics"),
        ("chemistry", "Chemistry"),
        # Business
        ("business administration", "Business Administration"),
        ("commerce", "Commerce"),
        ("economics", "Economics"),
        ("finance", "Finance"),
        ("marketing", "Marketing"),
        # Short forms
        ("cse", "Computer Science and Engineering"),
        ("ece", "Electronics and Communication Engineering"),
        ("eee", "Electrical and Electronics Engineering"),
        ("eie", "Electronics and Instrumentation"),
        ("it", "Information Technology"),
        ("mech", "Mechanical Engineering"),
        ("cs", "Computer Science"),

        # Additional Engineering branches
        ("computer engineering", "Computer Engineering"),
        ("information science", "Information Science"),
        ("information systems", "Information Systems"),
        ("computer applications", "Computer Applications"),
        ("electrical and computer", "Electrical and Computer Engineering"),
        ("instrumentation and control", "Instrumentation and Control Engineering"),
        ("instrumentation engineering", "Instrumentation Engineering"),
        ("power systems", "Power Systems Engineering"),
        ("vlsi", "VLSI Design"),
        ("embedded systems", "Embedded Systems"),
        ("automobile engineering", "Automobile Engineering"),
        ("automotive engineering", "Automotive Engineering"),
        ("production engineering", "Production Engineering"),
        ("manufacturing engineering", "Manufacturing Engineering"),
        ("industrial engineering", "Industrial Engineering"),
        ("industrial and production", "Industrial and Production Engineering"),
        ("mechatronics", "Mechatronics Engineering"),
        ("robotics", "Robotics Engineering"),
        ("aerospace engineering", "Aerospace Engineering"),
        ("aeronautical engineering", "Aeronautical Engineering"),
        ("structural engineering", "Structural Engineering"),
        ("environmental engineering", "Environmental Engineering"),
        ("construction engineering", "Construction Engineering"),

        # Bio & Pharma
        ("biotechnology", "Biotechnology"),
        ("bioinformatics", "Bioinformatics"),
        ("biochemistry", "Biochemistry"),
        ("microbiology", "Microbiology"),
        ("genetics", "Genetics"),
        ("pharmaceutical", "Pharmaceutical Sciences"),
        ("life sciences", "Life Sciences"),
        ("food technology", "Food Technology"),

        # Data & Cyber
        ("data analytics", "Data Analytics"),
        ("cyber security", "Cyber Security"),
        ("cybersecurity", "Cyber Security"),
        ("information security", "Information Security"),
        ("cloud computing", "Cloud Computing"),
        ("internet of things", "Internet of Things"),

        # Applied Science
        ("applied mathematics", "Applied Mathematics"),
        ("applied physics", "Applied Physics"),
        ("applied chemistry", "Applied Chemistry"),
        ("computing", "Computing"),

        # Business & Management
        ("human resource", "Human Resource Management"),
        ("operations management", "Operations Management"),
        ("supply chain", "Supply Chain Management"),
        ("international business", "International Business"),
        ("entrepreneurship", "Entrepreneurship"),
        ("accounting", "Accounting"),

        # Design & Arts
        ("design", "Design"),
        ("graphic design", "Graphic Design"),
        ("communication design", "Communication Design"),
        ("architecture", "Architecture"),
        ("animation", "Animation"),

        # Other
        ("english", "English"),
        ("journalism", "Journalism"),
        ("mass communication", "Mass Communication"),
        ("psychology", "Psychology"),
        ("sociology", "Sociology"),
        ("political science", "Political Science"),
        ("public administration", "Public Administration"),
        ("law", "Law"),
        ("agriculture", "Agriculture"),
        ("textile engineering", "Textile Engineering"),
        ("mining engineering", "Mining Engineering"),
        ("petroleum engineering", "Petroleum Engineering"),
        ("marine engineering", "Marine Engineering"),

        # More short forms
        ("ete", "Electronics and Telecommunication Engineering"),
        ("is", "Information Science"),
        ("ai", "Artificial Intelligence"),
        ("ml", "Machine Learning"),
    ]

    # Known university patterns (Indian + International)
    # These are checked via regex against the education section
    UNIVERSITY_PATTERNS = [
        # Premier Indian Institutes
        r'((?:Indian\s+)?Institute\s+of\s+Technology[\s,]+[A-Za-z]+)',
        r'(IIT\s+[A-Za-z]+)',
        r'(NIT\s+[A-Za-z]+)',
        r'(IIIT\s+[A-Za-z\-]+)',
        r'(BITS\s+[A-Za-z]+)',
        r'(VIT\s+[A-Za-z]*)',
        r'(SRM\s+Institute\s+of\s+Science\s+and\s+Technology)',
        r'(SRM\s+University)',
        r'(Amity\s+University)',
        r'(LPU|Lovely\s+Professional\s+University)',
        r'(Manipal\s+(?:Institute|University|Academy))',
        r'(Christ\s+University)',
        r'(Symbiosis\s+(?:International\s+)?University)',
        # State Universities
        r'(Anna\s+University)',
        r'(Osmania\s+University)',
        r'(JNTU\s+[A-Za-z]+)',
        r'(Jawaharlal\s+Nehru\s+Technological\s+University)',
        r'(Delhi\s+University|University\s+of\s+Delhi)',
        r'(Mumbai\s+University|University\s+of\s+Mumbai)',
        r'(Pune\s+University|Savitribai\s+Phule\s+Pune\s+University)',
        r'(Bangalore\s+University)',
        r'(Calcutta\s+University)',
        r'(Madras\s+University)',
        r'(Andhra\s+University)',
        r'(Calicut\s+University)',
        r'(Kerala\s+University)',
        r'(Gujarat\s+University)',
        r'(Rajasthan\s+University)',
        # Specific colleges
        r'(KL\s+University)',
        r'(K\s*L\s+University)',
        r'(Koneru\s+Lakshmaiah[A-Za-z\s]*)',
        r'(Saint\s+Peter\'?s?\s+University)',
        r'(St\.?\s+Peter\'?s?\s+University)',
        r'(Rutgers\s+University)',
        r'(Raghu\s+Institute(?:\s+(?:of|Of)\s+Technology)?)',
        r'(RV\s+College\s+of\s+Engineering)',
        r'(Narayana\s+(?:Junior\s+)?College)',
        r'(PSG\s+(?:College|Institute|Tech))',
        r'(Sathyabama\s+(?:Institute|University))',
        r'(Vel\s+Tech[A-Za-z\s]*)',
        r'(Saveetha\s+(?:Institute|University|Engineering))',
        r'(Hindustan\s+(?:Institute|University|College))',
        r'(Presidency\s+(?:University|College))',
        r'(Loyola\s+College)',
        r'(St\.?\s+Xavier\'?s?\s+(?:College|University))',
        r'(Birla\s+Institute[A-Za-z\s]*)',
        r'(Thapar\s+(?:Institute|University))',
        r'(PES\s+University)',
        r'(Dayananda\s+Sagar[A-Za-z\s]*)',
        r'(BMS\s+College[A-Za-z\s]*)',
        r'(MS\s+Ramaiah[A-Za-z\s]*)',
        r'(NMIMS[A-Za-z\s]*)',
        r'(Shiv\s+Nadar\s+University)',
        r'(Ashoka\s+University)',
        r'(IISC|Indian\s+Institute\s+of\s+Science)',
        r'(ISI|Indian\s+Statistical\s+Institute)',
        # International
        r'(MIT|Massachusetts\s+Institute\s+of\s+Technology)',
        r'(Stanford\s+University)',
        r'(Harvard\s+University)',
        r'(UC\s+Berkeley|University\s+of\s+California)',
        r'(Carnegie\s+Mellon\s+University)',
        r'(Georgia\s+(?:Institute\s+of\s+Technology|Tech))',
        r'(University\s+of\s+(?:Texas|Michigan|Illinois|Washington|Florida|Maryland))',
        r'(Purdue\s+University)',
        r'(Columbia\s+University)',
        r'(Cornell\s+University)',
        r'(NYU|New\s+York\s+University)',
        r'(USC|University\s+of\s+Southern\s+California)',
        r'(Northeastern\s+University)',
        r'(Arizona\s+State\s+University)',
        r'(Oxford\s+University|University\s+of\s+Oxford)',
        r'(Cambridge\s+University|University\s+of\s+Cambridge)',
        r'(Imperial\s+College)',
        # Generic patterns
        r'([A-Z][A-Za-z\.\']+(?:\s+[A-Z][a-z]+)*\s+University)',
        r'(University\s+of\s+[A-Z][A-Za-z\s]+)',
    ]

    # Keywords that identify a line as containing an institution name
    # Used for line-by-line scanning in the education section
    INSTITUTION_KEYWORDS = [
        'university', 'institute', 'college', 'school of',
        'academy', 'polytechnic', 'vidyalaya', 'vidyapeeth',
        'iit', 'nit', 'iiit', 'bits', 'vit', 'srm', 'lpu',
        'jntu', 'jntuh', 'jntuk', 'jntua',
        'cusat', 'gitam', 'kiit', 'klu', 'mit ', 'mits',
        'rvce', 'bmsit', 'dsce', 'pes', 'nmims', 'iisc',
        'iim', 'xlri', 'iiser', 'nift', 'nid',
        'deemed', 'autonomous',
        # More Indian institutions
        'amrita', 'manipal', 'thapar', 'chitkara', 'chandigarh',
        'sharda', 'galgotias', 'bennett', 'ashoka',
        'iiitd', 'iiitb', 'iiith', 'dtu', 'nsit', 'igdtuw',
        'jadavpur', 'presidency', 'iiest', 'ism',
        'coep', 'vjti', 'ict', 'spit', 'djsce',
        'psg', 'ssn', 'ceg', 'mit-wpu',
        'reva', 'christ', 'jain', 'ramaiah',
        # International
        'stanford', 'harvard', 'berkeley', 'caltech',
        'princeton', 'yale', 'columbia', 'cornell',
        'purdue', 'northeastern', 'nyu', 'usc',
        'oxford', 'cambridge', 'imperial',
    ]

    # Words that should NOT be university names
    UNIVERSITY_BLACKLIST = [
        "experience", "skills", "projects", "education", "summary",
        "professional", "technical", "certifications", "achievements",
        "work history", "employment", "objective", "profile",
        "senior", "junior", "engineer", "developer", "manager",
        "high school", "secondary", "intermediate",
    ]

    def extract_education(self, text: str) -> Dict:
        """Extract education details from the education section of the resume"""
        edu_section = self._get_education_section(text)
        search_text = edu_section if edu_section else text

        # Extract all education entries (degree + university pairs)
        edu_entries = self._extract_education_entries(search_text)

        if not edu_entries:
            # Fallback to old method
            degrees = self._extract_all_degrees(search_text)
            university = self._extract_university(search_text)
            graduation_year = self._extract_graduation_year(search_text)
            primary_degree = degrees[0] if degrees else ""
            undergrad_degree = degrees[1] if len(degrees) > 1 else ""
            return {
                "degree": primary_degree,
                "undergrad_degree": undergrad_degree,
                "all_degrees": degrees,
                "university": university,
                "undergrad_university": "",
                "graduation_year": graduation_year,
            }

        # First entry = highest degree (Master's/PhD), second = undergrad
        primary = edu_entries[0]
        undergrad = edu_entries[1] if len(edu_entries) > 1 else {}

        return {
            "degree": primary.get("degree", ""),
            "undergrad_degree": undergrad.get("degree", ""),
            "all_degrees": [e["degree"] for e in edu_entries if e.get("degree")],
            "university": primary.get("university", ""),
            "undergrad_university": undergrad.get("university", ""),
            "graduation_year": primary.get("year", "") or self._extract_graduation_year(search_text),
        }

    def _extract_education_entries(self, text: str) -> List[Dict]:
        """
        Parse education section into individual entries.
        Each entry = {degree, university, year}
        Handles formats where degree and university are on separate lines,
        same line, or pipe-separated.
        """
        lines = text.split('\n')
        entries = []
        current_entry = {}

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()

            # Skip non-degree lines (intermediate, SSC, high school)
            if any(kw in lower for kw in ['intermediate', 'ssc', 'hsc', '10th', '12th', 'high school', 'secondary']):
                if current_entry.get("degree"):
                    entries.append(current_entry)
                    current_entry = {}
                continue

            # Handle pipe-separated lines (e.g., "M.S. |Data Science |Saint Peter's University")
            if '|' in stripped:
                degree = self._extract_degree_from_line(lower)
                if degree:
                    if current_entry.get("degree"):
                        entries.append(current_entry)
                    current_entry = {"degree": degree, "university": "", "year": ""}
                    # Extract university from pipe parts
                    parts = [p.strip() for p in stripped.split('|')]
                    for part in parts:
                        if any(kw in part.lower() for kw in self.INSTITUTION_KEYWORDS):
                            cleaned = self._clean_university_line(part)
                            if cleaned and self._is_valid_university(cleaned):
                                current_entry["university"] = cleaned
                                break
                    year = self._extract_year_from_line(stripped)
                    if year:
                        current_entry["year"] = year
                    continue

            # Check if this line contains a degree
            degree = self._extract_degree_from_line(lower)
            if degree:
                # Save previous entry
                if current_entry.get("degree"):
                    entries.append(current_entry)
                current_entry = {"degree": degree, "university": "", "year": ""}

                # Check if university is on the SAME line
                # Handle "Rutgers University Master's in IT" (uni before degree)
                # and "B.Tech in CS - VIT University" (uni after degree)
                uni = self._extract_university_from_line(stripped)
                if uni:
                    current_entry["university"] = uni

                year = self._extract_year_from_line(stripped)
                if year:
                    current_entry["year"] = year
                continue

            # Check if this line is a university (comes after a degree line)
            if current_entry.get("degree") and not current_entry.get("university"):
                if any(kw in lower for kw in self.INSTITUTION_KEYWORDS):
                    uni = self._clean_university_line(stripped)
                    if uni and self._is_valid_university(uni):
                        current_entry["university"] = uni
                        year = self._extract_year_from_line(stripped)
                        if year and not current_entry.get("year"):
                            current_entry["year"] = year
                        continue

            # Check for year on standalone line
            if current_entry.get("degree") and not current_entry.get("year"):
                year = self._extract_year_from_line(stripped)
                if year:
                    current_entry["year"] = year

        # Don't forget the last entry
        if current_entry.get("degree"):
            entries.append(current_entry)

        # Filter out likely false positives (e.g., "Associate" from "AWS Certified Developer - Associate")
        filtered = []
        for entry in entries:
            degree = entry.get("degree", "")
            # Skip bare "Associate" or "Diploma" with no university (likely from certifications)
            if degree in ("Associate", "Diploma") and not entry.get("university"):
                continue
            filtered.append(entry)

        return filtered

    def _extract_degree_from_line(self, line_lower: str) -> str:
        """Check if a line contains a degree and return it"""
        for pattern, degree_name in self.DEGREE_PATTERNS:
            match = re.search(r'\b' + pattern + r'\b', line_lower)
            if match:
                spec = self._find_specialization_near(line_lower, match.start(), match.end())
                if spec:
                    return f"{degree_name} in {spec}"
                return degree_name
        return ""

    def _extract_university_from_line(self, line: str) -> str:
        """Try to extract university from the same line as the degree"""
        lower = line.lower()

        # Handle pipe-separated format: "Degree |Branch |University, Location"
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            for part in parts:
                if any(kw in part.lower() for kw in self.INSTITUTION_KEYWORDS):
                    cleaned = self._clean_university_line(part)
                    if cleaned and self._is_valid_university(cleaned):
                        return cleaned
            return ""

        # Handle format where university is BEFORE degree on same line:
        # "Rutgers University Master's in IT" or "RV College of Engineering Bachelor of Engineering..."
        # Strategy: find the degree keyword position and take text before it
        for pattern, _ in self.DEGREE_PATTERNS:
            match = re.search(r'\b' + pattern + r'\b', lower)
            if match:
                before_degree = line[:match.start()].strip()
                if before_degree and any(kw in before_degree.lower() for kw in self.INSTITUTION_KEYWORDS):
                    cleaned = self._clean_university_line(before_degree)
                    if cleaned and self._is_valid_university(cleaned):
                        return cleaned
                # Also check AFTER degree (e.g., "B.Tech in CS - VIT University")
                after_degree = line[match.end():].strip()
                if after_degree and any(kw in after_degree.lower() for kw in self.INSTITUTION_KEYWORDS):
                    cleaned = self._clean_university_line(after_degree)
                    if cleaned and self._is_valid_university(cleaned):
                        return cleaned
                break  # Only check first degree match

        # Handle dash-separated: "B.Tech in CS - VIT University"
        if any(kw in lower for kw in self.INSTITUTION_KEYWORDS):
            cleaned = self._clean_university_line(line)
            if cleaned and self._is_valid_university(cleaned):
                return cleaned
        return ""

    def _extract_year_from_line(self, line: str) -> str:
        """Extract graduation year from a line"""
        # Year range: take end year
        match = re.search(r'(\d{4})\s*[-\u2013\u2014]\s*(\d{4})', line)
        if match:
            year = match.group(2)
            if 1970 <= int(year) <= 2030:
                return year
        # Standalone year
        years = re.findall(r'\b(20\d{2}|19\d{2})\b', line)
        if years:
            return max(years)
        return ""

    def _get_education_section(self, text: str) -> str:
        """Extract the education section from resume text"""
        lines = text.split('\n')
        in_edu = False
        edu_lines = []
        section_start_keywords = ['education', 'academic', 'qualification', 'degree', 'schooling']
        section_end_keywords = ['experience', 'skills', 'projects', 'certification',
                               'achievement', 'work history', 'employment', 'publications']

        for line in lines:
            lower = line.strip().lower()

            # Detect education section start
            if not in_edu:
                if any(lower.startswith(kw) or lower == kw for kw in section_start_keywords):
                    in_edu = True
                    continue
                # Also check if line IS a section heading for education
                if len(lower.split()) <= 3 and any(kw in lower for kw in section_start_keywords):
                    in_edu = True
                    continue
            else:
                # Detect next section (exit education)
                if len(lower.split()) <= 4 and any(kw in lower for kw in section_end_keywords):
                    break
                edu_lines.append(line)

        return '\n'.join(edu_lines)

    def _extract_all_degrees(self, text: str) -> List[str]:
        """Extract ALL degrees found in education section, ordered highest to lowest"""
        text_lower = text.lower()
        found_degrees = []

        for pattern, degree_name in self.DEGREE_PATTERNS:
            # Find ALL occurrences of this degree pattern
            for match in re.finditer(r'\b' + pattern + r'\b', text_lower):
                spec = self._find_specialization_near(text_lower, match.start(), match.end())
                if spec:
                    degree_str = f"{degree_name} in {spec}"
                else:
                    degree_str = degree_name
                # Avoid duplicates
                if degree_str not in found_degrees:
                    found_degrees.append(degree_str)

        return found_degrees

    def _extract_degree(self, text: str) -> str:
        """Extract highest degree with proper specialization from education section"""
        degrees = self._extract_all_degrees(text)
        return degrees[0] if degrees else ""

    def _find_specialization_near(self, text: str, degree_start: int, degree_end: int) -> str:
        """
        Find specialization within context around the degree mention.
        Only looks on the SAME LINE or immediately adjacent lines.
        """
        import re as _re

        # Get the line containing the degree
        line_start = text.rfind('\n', 0, degree_start)
        line_start = line_start + 1 if line_start != -1 else 0
        line_end = text.find('\n', degree_end)
        if line_end == -1:
            line_end = len(text)

        # Also get the next line
        next_line_end = text.find('\n', line_end + 1)
        if next_line_end == -1:
            next_line_end = len(text)

        # Search area: current line + next line only
        search_area = text[line_start:next_line_end]

        # Text immediately after degree keyword (e.g., "M.Tech in Data Science")
        after_degree = text[degree_end:degree_end + 80]

        # Check specializations - longer matches first (more specific)
        # First check immediately after the degree keyword
        for spec_lower, spec_proper in self.SPECIALIZATIONS:
            if self._spec_matches(spec_lower, after_degree):
                return spec_proper

        # Then check the line context
        for spec_lower, spec_proper in self.SPECIALIZATIONS:
            if self._spec_matches(spec_lower, search_area):
                return spec_proper

        return ""

    def _spec_matches(self, spec: str, text: str) -> bool:
        """
        Check if a specialization matches in text with proper boundaries.
        Short specs (<=4 chars like 'it', 'cs', 'ai', 'mech') use word boundaries.
        Longer specs use simple substring match.
        """
        import re as _re
        if len(spec) <= 4:
            # Short form — must be a standalone word
            return bool(_re.search(r'(?<![a-z])' + _re.escape(spec) + r'(?![a-z])', text))
        else:
            return spec in text

    def _extract_university(self, text: str) -> str:
        """Extract university/college name from education section"""
        # First: handle pipe-separated formats
        pipe_uni = self._extract_from_pipe_format(text)
        if pipe_uni:
            return pipe_uni

        # Second: scan lines for institution names
        # In Indian resumes, the college name is typically on the line AFTER the degree
        lines = text.split('\n')
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            # Skip very short or very long lines
            if len(stripped) < 5 or len(stripped) > 150:
                continue

            # Skip lines that are clearly degree lines (start with B.Tech, M.Tech etc.)
            if re.match(r'^(?:b\s*\.?\s*(?:tech|e|eng|sc|s|ca|ba)|m\s*\.?\s*(?:tech|e|s|sc|ca|ba)|bachelor|master|phd|diploma|intermediate|ssc|hsc|10th|12th)\b', lower):
                # But check if university is on the SAME line after a dash or comma
                if any(kw in lower for kw in self.INSTITUTION_KEYWORDS):
                    cleaned = self._clean_university_line(stripped)
                    if cleaned and self._is_valid_university(cleaned):
                        return cleaned
                continue

            # Check if line contains institution keywords
            if any(kw in lower for kw in self.INSTITUTION_KEYWORDS):
                cleaned = self._clean_university_line(stripped)
                if cleaned and self._is_valid_university(cleaned):
                    return cleaned

        # Third: try regex patterns as fallback
        for pattern in self.UNIVERSITY_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                uni = match.group(1).strip()
                uni = re.sub(r'[,\.\|]+\s*$', '', uni).strip()
                if len(uni) > 60:
                    uni = re.sub(r',\s*[A-Za-z\s]+$', '', uni).strip()
                if self._is_valid_university(uni):
                    return uni

        return ""

    def _clean_university_line(self, line: str) -> str:
        """
        Clean a line that contains a university/college name.
        Removes CGPA, percentages, year ranges, locations, degree prefixes.
        """
        cleaned = line.strip()

        # Remove leading bullets/dashes
        cleaned = re.sub(r'^[\-\*\u2022\u25cf\s]+', '', cleaned)

        # If line has format "Degree - University" or "Degree | University", extract university part
        dash_parts = re.split(r'\s+[-\u2013\u2014]\s+', cleaned)
        if len(dash_parts) >= 2:
            for part in dash_parts:
                if any(kw in part.lower() for kw in self.INSTITUTION_KEYWORDS):
                    cleaned = part.strip()
                    break

        # Handle "from University" format
        from_match = re.search(r'\bfrom\s+(.+)', cleaned, re.IGNORECASE)
        if from_match:
            candidate = from_match.group(1).strip()
            if any(kw in candidate.lower() for kw in self.INSTITUTION_KEYWORDS):
                cleaned = candidate

        # Handle "at University" format
        at_match = re.search(r'\bat\s+([A-Z].+)', cleaned)
        if at_match:
            candidate = at_match.group(1).strip()
            if any(kw in candidate.lower() for kw in self.INSTITUTION_KEYWORDS):
                cleaned = candidate

        # Remove parenthetical content (CGPA, GPA, percentages, Autonomous, Affiliated)
        cleaned = re.sub(r'\([^)]*(?:cgpa|gpa|percentage|%|\d+/10|\d+\.\d+)[^)]*\)', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\(\s*\d+[\.\d]*/\d+\s*\)', '', cleaned)
        # Keep "(Autonomous)" or "(Affiliated to X)" as part of name but clean it
        cleaned = re.sub(r'\(Affiliated\s+to\s+[^)]+\)', '', cleaned, flags=re.IGNORECASE)

        # Remove year ranges and standalone years
        cleaned = re.sub(r'\b\d{4}\s*[-\u2013\u2014]\s*\d{4}\b', '', cleaned)
        cleaned = re.sub(r'\b(?:19|20)\d{2}\b', '', cleaned)

        # Remove CGPA/GPA mentions not in parentheses
        cleaned = re.sub(r'(?:CGPA|GPA|cgpa|gpa)\s*[-:]\s*\d+[\.\d]*/?\d*', '', cleaned)

        # Remove trailing location after last comma (city names)
        # But only if the main institution name is before the comma
        parts = cleaned.split(',')
        if len(parts) > 1:
            main_part = parts[0].strip()
            if any(kw in main_part.lower() for kw in self.INSTITUTION_KEYWORDS):
                cleaned = main_part
            elif len(parts) > 2 and any(kw in (parts[0] + parts[1]).lower() for kw in self.INSTITUTION_KEYWORDS):
                cleaned = (parts[0] + ', ' + parts[1]).strip()

        # Remove trailing slash and location (e.g., "/ Visakhapatnam")
        cleaned = re.sub(r'\s*/\s*[A-Za-z]+(?:\s*\([^)]*\))?$', '', cleaned)

        # Remove degree prefixes if they got included
        # Strategy: if line has commas, find the part with institution keyword
        if ',' in cleaned:
            comma_parts = [p.strip() for p in cleaned.split(',')]
            for i, part in enumerate(comma_parts):
                if any(kw in part.lower() for kw in self.INSTITUTION_KEYWORDS):
                    # Take this part (and maybe the next if it's part of the name)
                    cleaned = part
                    break
        else:
            # No commas - try regex removal of degree prefix
            cleaned = re.sub(
                r'^(?:B\s*\.?\s*Tech|M\s*\.?\s*Tech|B\s*\.?\s*E\s*\.?|M\s*\.?\s*E\s*\.?|M\s*\.?\s*S\s*\.?|B\s*\.?\s*S\s*\.?|B\s*\.?\s*Sc|M\s*\.?\s*Sc|MBA|BCA|MCA|BBA|Ph\.?D|Bachelor[\'s]*|Master[\'s]*|Diploma)'
                r'(?:\s+(?:of|in)\s+[A-Za-z\s&]+)?[\s\-\|,]+',
                '', cleaned, flags=re.IGNORECASE
            )

        # Remove "Pursued" and similar prefixes
        cleaned = re.sub(r'^(?:Pursued|Completed|Obtained|Earned)\s+', '', cleaned, flags=re.IGNORECASE)

        # Final cleanup
        cleaned = re.sub(r'^[\s\-,|/]+', '', cleaned).strip()
        cleaned = re.sub(r'[,\.\|/]+$', '', cleaned).strip()
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        # Remove trailing "(Autonomous)" parenthetical
        cleaned = re.sub(r'\s*\(Autonomous\)\s*$', '', cleaned, flags=re.IGNORECASE).strip()

        return cleaned

        return ""

    def _extract_from_pipe_format(self, text: str) -> str:
        """
        Handle pipe-separated education formats like:
        'Master of Science |Data Science |Saint Peter's University, Jersey City, NJ    Feb 2023-Nov 2024'
        'Bachelor of Technology |Computer Science Engineering | KL University, Andhra Pradesh'
        'Bachelor of Technology | Electronics | Sathyabama Institute, Chennai 2021'
        """
        lines = text.split('\n')
        for line in lines:
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                for part in parts:
                    lower = part.lower()
                    if any(kw in lower for kw in self.INSTITUTION_KEYWORDS):
                        # Clean using the standard cleaner
                        cleaned = self._clean_university_line(part)
                        if cleaned and self._is_valid_university(cleaned):
                            return cleaned
        return ""

    def _is_valid_university(self, name: str) -> bool:
        """Validate that a string is likely a university/college name"""
        if not name or len(name) < 3 or len(name) > 100:
            return False
        lower = name.lower()
        # Check blacklist
        if any(bl == lower or lower.startswith(bl) for bl in self.UNIVERSITY_BLACKLIST):
            return False
        # Reject if it contains degree keywords (picked up too much text)
        degree_words = ["master's", "masters", "bachelor's", "bachelors", "m.tech",
                       "b.tech", "mba", "phd", "diploma", "degree", "concentration",
                       "b . tech", "m . tech", "b.e.", "m.e."]
        if any(dw in lower for dw in degree_words):
            return False
        # Should contain at least one institution-related word
        if any(kw in lower for kw in self.INSTITUTION_KEYWORDS):
            return True
        # Or be a known abbreviation (all caps, 2-5 chars)
        if name.isupper() and 2 <= len(name) <= 6:
            return True
        # Or be a proper noun with 2+ words
        if name[0].isupper() and len(name.split()) >= 2:
            return True
        return False

    def _extract_graduation_year(self, text: str) -> str:
        """Extract graduation year from education section"""
        # Pattern 1: Explicit graduation mention
        patterns = [
            r'(?:graduated|graduation|batch|class of|passed out|completed)\s*(?:in|:)?\s*(\d{4})',
            r'(\d{4})\s*[\-\u2013\u2014]\s*(\d{4})',  # Year range like 2016-2020
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.lastindex and match.lastindex >= 2:
                    year = match.group(2)  # End year of range
                else:
                    year = match.group(1)
                if 1970 <= int(year) <= 2030:
                    return year

        # Pattern 2: Look for standalone years in education context
        years = re.findall(r'\b(20\d{2}|19\d{2})\b', text)
        if years:
            # Return the most recent year (likely graduation)
            valid_years = [y for y in years if 1970 <= int(y) <= 2030]
            if valid_years:
                return max(valid_years)

        return ""

    def calculate_education_match(self, candidate_edu: Dict, jd_text: str) -> float:
        """Calculate education match score"""
        jd_lower = jd_text.lower()
        score = 0.5  # Base score

        degree = candidate_edu.get("degree", "").lower()

        # Check if JD requires specific degree
        if "phd" in jd_lower or "doctoral" in jd_lower:
            if "phd" in degree:
                score = 1.0
            elif "master" in degree or "m.tech" in degree or "m.s" in degree:
                score = 0.7
            else:
                score = 0.4
        elif any(kw in jd_lower for kw in ["master", "mba", "m.tech", "m.s."]):
            if "phd" in degree or "master" in degree or "m.tech" in degree or "m.s" in degree or "mba" in degree:
                score = 1.0
            elif "bachelor" in degree or "b.tech" in degree or "b.e" in degree:
                score = 0.6
            else:
                score = 0.4
        elif any(kw in jd_lower for kw in ["bachelor", "b.tech", "b.e.", "degree", "b.s."]):
            if degree:
                score = 0.8
            else:
                score = 0.4
        else:
            # No specific education requirement
            if degree:
                score = 0.7
            else:
                score = 0.5

        return score
