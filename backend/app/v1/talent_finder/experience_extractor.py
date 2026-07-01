"""
Experience Extraction Service - Fixed v2
Properly calculates experience from WORK section only.
NEVER counts education year ranges as work experience.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional


class ExperienceExtractor:
    """Extracts work experience details and calculates seniority"""

    SENIORITY_KEYWORDS = {
        "intern": ["intern", "internship", "trainee"],
        "junior": ["junior", "jr", "entry level", "associate", "fresher", "graduate"],
        "mid": ["mid", "intermediate"],
        "senior": ["senior", "sr", "principal", "staff", "architect"],
        "lead": ["lead", "manager", "director", "head", "vp", "chief", "cto", "ceo"],
    }

    MONTHS = {
        'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
        'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
        'may': 5, 'jun': 6, 'june': 6,
        'jul': 7, 'july': 7, 'aug': 8, 'august': 8,
        'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
        'nov': 11, 'november': 11, 'dec': 12, 'december': 12
    }

    def extract_experience(self, text: str) -> Dict:
        """Extract experience information from text"""
        exp_section = self._get_experience_section(text)
        total_years = self._calculate_total_years(text, exp_section)
        seniority = self._detect_seniority(exp_section if exp_section else text, total_years)
        job_titles = self._extract_job_titles(exp_section if exp_section else text)
        companies = self._extract_companies(exp_section if exp_section else text)

        return {
            "total_years": total_years,
            "seniority": seniority,
            "job_titles": job_titles,
            "companies": companies,
        }

    def _get_experience_section(self, text: str) -> str:
        """Extract the work experience section ONLY from resume text"""
        lines = text.split('\n')
        in_exp = False
        exp_lines = []
        exp_start_keywords = ['work experience', 'professional experience', 'experience',
                              'employment history', 'employment', 'career history',
                              'work history']
        end_keywords = ['education', 'academic', 'qualification', 'skills',
                       'technical skills', 'projects', 'certification',
                       'achievements', 'publications', 'featured projects',
                       'personal traits', 'interests', 'hobbies',
                       'career objective', 'objective', 'technical projects',
                       'other']

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            if not in_exp:
                # Detect experience section start
                # Check if line is a heading (short) containing experience keywords
                if len(lower.split()) <= 6:
                    if any(lower == kw or lower.startswith(kw) or kw in lower for kw in exp_start_keywords):
                        # Make sure it's not "experience: 5 years" in summary
                        if not any(x in lower for x in ['years', 'yrs', 'delivering', 'building']):
                            in_exp = True
                            continue
            else:
                # Detect next section (exit experience)
                if stripped and len(lower.split()) <= 5:
                    if any(lower == kw or lower.startswith(kw) for kw in end_keywords):
                        break
                exp_lines.append(line)

        return '\n'.join(exp_lines)

    def _calculate_total_years(self, full_text: str, exp_section: str) -> float:
        """
        Calculate total years of experience.
        Priority:
        1. Explicit mention ("4+ years of experience")
        2. Date ranges from EXPERIENCE section ONLY
        3. Fallback: date ranges from full text excluding education lines
        """
        # Priority 1: Explicit mention
        explicit_years = self._find_explicit_years(full_text)
        if explicit_years is not None:
            return explicit_years

        # Priority 2: Date ranges from experience section ONLY
        if exp_section and exp_section.strip():
            date_ranges = self._extract_month_year_ranges(exp_section)
            if date_ranges:
                total_months = self._sum_non_overlapping(date_ranges)
                return round(total_months / 12, 1)

            # Try year-only ranges in experience section
            year_ranges = self._extract_year_ranges_strict(exp_section)
            if year_ranges:
                total_months = self._sum_non_overlapping(year_ranges)
                return round(total_months / 12, 1)

        # Priority 3: Fallback - scan full text for work-like date ranges
        # Only use this if no experience section was found
        if not exp_section or not exp_section.strip():
            work_ranges = self._extract_work_ranges_from_full_text(full_text)
            if work_ranges:
                total_months = self._sum_non_overlapping(work_ranges)
                return round(total_months / 12, 1)

        return 0.0

    def _extract_work_ranges_from_full_text(self, text: str) -> List[Dict]:
        """
        Fallback: extract date ranges from full text, but only those
        that appear near work-related context (job titles, company names).
        Skip anything near education context.
        """
        lines = text.split('\n')
        work_ranges = []
        in_education = False

        for line in lines:
            lower = line.strip().lower()

            # Track education section
            if len(lower.split()) <= 4:
                if any(kw in lower for kw in ['education', 'academic', 'qualification']):
                    in_education = True
                    continue
                elif any(kw in lower for kw in ['experience', 'employment', 'work']):
                    in_education = False
                    continue
                elif any(kw in lower for kw in ['skills', 'projects', 'certification']):
                    in_education = False
                    continue

            if in_education or self._is_education_line(line):
                continue

            # Look for year ranges on lines that have work context
            # (company names, job titles, or just year ranges with "Present")
            has_work_context = any(kw in lower for kw in [
                'engineer', 'developer', 'analyst', 'manager', 'consultant',
                'intern', 'architect', 'lead', 'present', 'current',
                '|', ' at ', ' - ', 'inc', 'ltd', 'pvt', 'llc', 'corp',
                'technologies', 'systems', 'solutions', 'labs'
            ])

            if has_work_context:
                # Extract month-year ranges
                month_ranges = self._extract_month_year_ranges(line)
                work_ranges.extend(month_ranges)

                # Extract year ranges
                pattern = r'(\d{4})\s*[\-\u2013\u2014\u2012\u2015–—]+\s*(\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)'
                for match in re.finditer(pattern, line):
                    start_year = int(match.group(1))
                    end_str = match.group(2).lower()
                    if end_str in ('present', 'current', 'now'):
                        end_year = datetime.now().year
                    else:
                        end_year = int(end_str)
                    if 1990 <= start_year <= datetime.now().year and end_year >= start_year:
                        months = (end_year - start_year) * 12
                        if 1 <= months <= 360:
                            work_ranges.append({
                                'start_year': start_year,
                                'end_year': end_year,
                                'months': months
                            })

        return work_ranges

    def _find_explicit_years(self, text: str) -> Optional[float]:
        """Find explicitly stated years of experience"""
        patterns = [
            r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)',
            r'(?:experience|exp)\s*(?:of)?\s*(\d+)\+?\s*(?:years?|yrs?)',
            r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:professional|industry|work)',
            r'with\s+(\d+)\+?\s*(?:years?|yrs?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                years = float(match.group(1))
                if 0 < years <= 40:
                    return years
        return None

    def _extract_month_year_ranges(self, text: str) -> List[Dict]:
        """Extract 'Month Year - Month Year/Present' patterns with all dash types"""
        ranges = []
        month_names = '|'.join(self.MONTHS.keys())
        # Match all types of dashes and separators
        pattern = (
            r'(' + month_names + r')\w*[\s,]*(\d{4})\s*'
            r'[\-\u2013\u2014\u2012\u2015–—]+\s*'
            r'(?:(' + month_names + r')\w*[\s,]*(\d{4})|[Pp]resent|[Cc]urrent|[Nn]ow|[Oo]ngoing|[Tt]ill\s+[Dd]ate)'
        )

        for match in re.finditer(pattern, text, re.IGNORECASE):
            start_month_str = match.group(1).lower()[:3]
            start_year = int(match.group(2))
            end_month_str = match.group(3)
            end_year_str = match.group(4)

            start_month = self.MONTHS.get(start_month_str, 1)

            if end_month_str and end_year_str:
                end_month = self.MONTHS.get(end_month_str.lower()[:3], 12)
                end_year = int(end_year_str)
            else:
                end_month = datetime.now().month
                end_year = datetime.now().year

            # Validate
            if start_year < 1990 or start_year > datetime.now().year:
                continue
            if end_year < start_year or end_year > datetime.now().year + 1:
                continue

            months = (end_year - start_year) * 12 + (end_month - start_month)
            if 1 <= months <= 360:
                ranges.append({
                    'start_year': start_year,
                    'start_month': start_month,
                    'end_year': end_year,
                    'end_month': end_month,
                    'months': months
                })

        return ranges

    def _extract_year_ranges_strict(self, exp_text: str) -> List[Dict]:
        """
        Extract 'Year - Year/Present' patterns from experience section only.
        Handles all dash types: -, –, —, to
        """
        ranges = []
        lines = exp_text.split('\n')

        for line in lines:
            # Skip lines that look like education
            if self._is_education_line(line):
                continue

            # Match year ranges with any dash type
            pattern = r'(\d{4})\s*[\-\u2013\u2014\u2012\u2015–—]+\s*(\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow|[Oo]ngoing)'
            for match in re.finditer(pattern, line):
                start_year = int(match.group(1))
                end_str = match.group(2).lower()

                if end_str in ('present', 'current', 'now', 'ongoing'):
                    end_year = datetime.now().year
                else:
                    end_year = int(end_str)

                if start_year < 1990 or end_year < start_year:
                    continue
                if end_year > datetime.now().year + 1:
                    continue

                months = (end_year - start_year) * 12
                if 1 <= months <= 360:
                    ranges.append({
                        'start_year': start_year,
                        'end_year': end_year,
                        'months': months
                    })

        return ranges

    def _is_education_line(self, line: str) -> bool:
        """Check if a line contains education context"""
        lower = line.lower()
        edu_indicators = [
            'university', 'college', 'institute', 'school',
            'b.tech', 'btech', 'm.tech', 'mtech', 'bachelor', 'master',
            'phd', 'diploma', 'cgpa', 'gpa', 'percentage', 'grade',
            'graduated', 'degree', 'bca', 'mca', 'bba', 'mba',
            'intermediate', 'ssc', 'hsc', '10th', '12th',
            'narayana', 'high school'
        ]
        return any(kw in lower for kw in edu_indicators)

    def _sum_non_overlapping(self, ranges: List[Dict]) -> int:
        """Sum months from non-overlapping date ranges"""
        if not ranges:
            return 0

        sorted_ranges = sorted(ranges, key=lambda r: (r.get('start_year', 0), r.get('start_month', 1)))

        total_months = 0
        prev_end_year = 0
        prev_end_month = 0

        for r in sorted_ranges:
            start_year = r.get('start_year', 0)
            start_month = r.get('start_month', 1)
            end_year = r.get('end_year', start_year)
            end_month = r.get('end_month', 12)

            # Skip if completely within previous range
            if start_year < prev_end_year or (start_year == prev_end_year and start_month < prev_end_month):
                start_year = prev_end_year
                start_month = prev_end_month

            months = (end_year - start_year) * 12 + (end_month - start_month)
            if months > 0:
                total_months += months

            if end_year > prev_end_year or (end_year == prev_end_year and end_month > prev_end_month):
                prev_end_year = end_year
                prev_end_month = end_month

        return total_months

    def _detect_seniority(self, text: str, years: float) -> str:
        """Detect seniority level from job titles and experience years"""
        text_lower = text.lower()

        # Check for explicit seniority keywords in job title lines
        # Priority: check from highest to lowest, and prefer years-based if ambiguous
        title_patterns = [
            (r'\b(?:lead|manager|director|head|vp|chief|cto)\s+', "lead"),
            (r'\b(?:senior|sr\.?|principal|staff)\s+(?:software|data|ml|ai|full)', "senior"),
            (r'\b(?:junior|jr\.?)\s+(?:software|data|ml|ai|full)', "junior"),
        ]

        detected_levels = []
        for pattern, level in title_patterns:
            if re.search(pattern, text_lower):
                detected_levels.append(level)

        # If we found senior/lead titles, use that
        if "lead" in detected_levels:
            return "lead"
        if "senior" in detected_levels:
            return "senior"

        # Primarily use years-based detection (most reliable)
        if years >= 10:
            return "lead"
        elif years >= 6:
            return "senior"
        elif years >= 3:
            return "mid"
        elif years >= 1:
            return "junior"
        elif years > 0:
            return "intern"
        return "fresher"

    def _extract_job_titles(self, text: str) -> List[str]:
        """Extract job titles from text"""
        titles = []
        common_titles = [
            r'(?:senior|junior|lead|principal|staff)?\s*(?:software\s+)?(?:engineer|developer)',
            r'(?:frontend|front-end|back-end|backend|full[\s\-]?stack)\s+(?:engineer|developer)',
            r'data\s+(?:scientist|engineer|analyst)',
            r'(?:devops|sre|cloud)\s+engineer',
            r'(?:product|project|engineering)\s+manager',
            r'(?:machine\s+learning|ml|ai)\s+(?:engineer|scientist|analyst)',
            r'(?:genai|gen\s+ai)\s+(?:engineer|analyst)',
            r'(?:web|mobile|ios|android)\s+developer',
            r'(?:solutions?|enterprise)\s+architect',
            r'(?:technical|tech)\s+lead',
            r'(?:data\s+science|ai)\s+consultant',
            r'research\s+assistant',
            r'graduate\s+research\s+assistant',
        ]

        for pattern in common_titles:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                title = match.group(0).strip()
                if title and title.title() not in titles:
                    titles.append(title.title())

        return titles[:5]

    def _extract_companies(self, text: str) -> List[str]:
        """Extract company names"""
        companies = []
        # Pattern: "Title at/| Company" or "Company |" in experience section
        patterns = [
            r'(?:at|@)\s+([A-Z][A-Za-z0-9\s&\.]+?)(?:\s*[\-\|,]|\s+as\s)',
            r'(?:worked\s+(?:at|for|with))\s+([A-Z][A-Za-z0-9\s&\.]+?)(?:\s*[\-\|,\.])',
            r'\|\s*([A-Z][A-Za-z0-9\s&\.]+?)\s*\|',  # | Company |
        ]
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                company = match.group(1).strip()
                if company and len(company) < 50 and company not in companies:
                    companies.append(company)

        return companies[:10]

    def calculate_experience_match(self, candidate_years: float, jd_text: str) -> float:
        """Calculate how well candidate experience matches JD requirements"""
        required_years = 0.0
        patterns = [
            r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)',
            r'(?:minimum|min|at\s+least)\s*(\d+)\s*(?:years?|yrs?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, jd_text, re.IGNORECASE)
            if match:
                required_years = float(match.group(1))
                break

        if required_years == 0:
            if candidate_years >= 5:
                return 0.9
            elif candidate_years >= 3:
                return 0.7
            elif candidate_years >= 1:
                return 0.5
            return 0.3

        if candidate_years >= required_years:
            return min(1.0, 0.8 + (candidate_years - required_years) * 0.05)
        else:
            if candidate_years == 0:
                return 0.1
            ratio = candidate_years / required_years
            return max(0.1, ratio * 0.7)
