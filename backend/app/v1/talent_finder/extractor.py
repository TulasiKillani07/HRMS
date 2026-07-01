"""
Information Extraction Service - Enhanced
Robust extraction of candidate name, email, phone, projects, certifications
"""

import re


class InformationExtractor:
    """Extracts structured information from resume text"""

    def extract_info(self, text: str) -> dict:
        """Extract all structured information from resume text"""
        return {
            "name": self._extract_name(text),
            "email": self._extract_email(text),
            "phone": self._extract_phone(text),
            "projects": self._extract_projects(text),
            "certifications": self._extract_certifications(text),
        }

    def _extract_name(self, text: str) -> str:
        """
        Extract candidate full name.
        Strategy: Check first 15 lines, try to extract name from each.
        The first line that yields a valid name wins.
        """
        lines = text.split('\n')

        # Section heading words - if a line IS a heading, skip it
        heading_words = ['summary', 'objective', 'experience', 'education', 'skills',
                        'projects', 'certifications', 'achievements', 'career objective',
                        'professional summary', 'technical skills', 'work experience']

        for line in lines[:15]:
            stripped = line.strip()
            if not stripped:
                continue

            lower = stripped.lower()

            # Skip lines that ARE section headings
            if lower in heading_words or any(lower == h for h in heading_words):
                continue

            # Skip lines that are ONLY URLs
            if lower.startswith('http') or lower.startswith('www.'):
                continue

            # Try to extract name from this line (handles mixed content)
            name = self._clean_name_from_line(stripped)
            if name:
                return name

        return "Unknown"

    def _clean_name_from_line(self, line: str) -> str:
        """
        Extract just the name portion from a line that might contain other info.
        Handles:
          "MOHAN VANUKURI +1 551 727 1500| mohan@gmail.com"
          "Rahul Verma AI/ML Engineer rahul@gmail.com | +91-9876543210"
          "Irfan Melekkandy Puthalath irfan@gmail.com | (862) 423-3940"
        """
        # Step 1: Remove email addresses
        cleaned = re.sub(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', '', line)
        # Step 2: Remove phone numbers (various formats)
        cleaned = re.sub(r'\+?1[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}', '', cleaned)
        cleaned = re.sub(r'\(\d{3}\)[\s\-]?\d{3}[\s\-]?\d{4}', '', cleaned)
        cleaned = re.sub(r'\+?91[\s\-]?\d{5}[\s\-]?\d{5}', '', cleaned)
        cleaned = re.sub(r'\+?91[\s\-]?\d{10}', '', cleaned)
        cleaned = re.sub(r'(?<![A-Za-z])\+?\d[\d\s\-\(\)]{8,15}(?![A-Za-z])', '', cleaned)
        # Step 3: Remove URLs and social links
        cleaned = re.sub(r'https?://\S+', '', cleaned)
        cleaned = re.sub(r'(?:github|linkedin|portfolio|website)[:\s./]*\S*', '', cleaned, flags=re.IGNORECASE)
        # Step 4: Remove location info
        cleaned = re.sub(r'(?:Pune|Mumbai|Hyderabad|Chennai|Bangalore|Bengaluru|Delhi|Newark|Jersey City|Remote|India|USA|NJ|NY|CA|TX)(?:\s*,\s*\w+)*', '', cleaned, flags=re.IGNORECASE)
        # Step 5: Remove pipe separators and content after them
        if '|' in cleaned:
            parts = cleaned.split('|')
            # Take the longest part that has alphabetic content
            best = ''
            for part in parts:
                p = part.strip()
                alpha_count = sum(1 for c in p if c.isalpha())
                if alpha_count > sum(1 for c in best if c.isalpha()):
                    best = p
            cleaned = best
        # Step 6: Remove job title suffixes (everything from title keyword onwards)
        title_keywords = r'(?:AI/?ML|ML|AI|Sr\.?|Jr\.?|Senior|Junior|Lead|Staff|Principal|Full[\s\-]?Stack|Frontend|Backend|React\s*Native|Mobile|Software|Data|Cloud|DevOps|Web|iOS|Android)'
        cleaned = re.sub(title_keywords + r'\s+.*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(?:Engineer|Developer|Analyst|Consultant|Scientist|Architect|Designer|Manager)\b.*$', '', cleaned, flags=re.IGNORECASE)
        # Step 7: Clean up
        cleaned = re.sub(r'[|,\-:;/]+\s*$', '', cleaned).strip()
        cleaned = re.sub(r'^\s*[|,\-:;/]+', '', cleaned).strip()
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()

        # Validate: should be 2-5 words, alphabetic
        words = cleaned.split()
        if 2 <= len(words) <= 5:
            if all(re.match(r'^[A-Za-z.\-\']+$', w) for w in words):
                if words[0][0].isupper():
                    # Reject common non-name words
                    non_names = ['professional', 'summary', 'career', 'objective',
                                'technical', 'work', 'education', 'skills', 'experience']
                    if words[0].lower() not in non_names:
                        return cleaned

        # Fallback: try extracting first 2-4 consecutive capitalized words from original line
        words = line.split()
        name_words = []
        for w in words:
            # Stop at non-name characters
            if re.match(r'^[A-Za-z.\-\']+$', w) and w[0].isupper():
                name_words.append(w)
            elif name_words:
                break  # Stop collecting once we hit a non-name word
            # Also stop if we hit a title keyword
            if w.lower() in ['ai/ml', 'ml', 'ai', 'senior', 'junior', 'lead',
                            'software', 'data', 'full-stack', 'fullstack',
                            'react', 'native', 'backend', 'frontend', 'mobile',
                            'cloud', 'devops', 'engineer', 'developer', 'analyst']:
                break

        if 2 <= len(name_words) <= 5:
            non_names = ['professional', 'summary', 'career', 'objective',
                        'technical', 'work', 'education', 'skills']
            if name_words[0].lower() not in non_names:
                return ' '.join(name_words)

        return ""

    def _extract_email(self, text: str) -> str:
        """Extract email address - searches entire text"""
        pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
        matches = re.findall(pattern, text)
        if matches:
            # Return the first valid-looking email (skip generic ones)
            for email in matches:
                # Skip obviously fake/generic emails
                if not any(skip in email.lower() for skip in ['example.com', 'test.com', 'noreply']):
                    return email
        return ""

    def _extract_phone(self, text: str) -> str:
        """
        Extract phone number - handles Indian, US, and international formats.
        Searches the first ~500 chars (header area) for better accuracy.
        """
        # Search in header area first (first 500 chars), then full text
        search_areas = [text[:500], text]

        patterns = [
            # Indian: +91-9876543210 or +91 9876543210 or 9876543210
            r'(?:\+91[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}',
            # US: +1 551 727 1500 or (862) 423-3940 or 551-727-1500
            r'\+?1[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}',
            r'\(\d{3}\)[\s\-]?\d{3}[\s\-]?\d{4}',
            # Generic international: +XX XXXXXXXXXX
            r'\+\d{1,3}[\s\-]?\d{3,5}[\s\-]?\d{3,5}[\s\-]?\d{0,5}',
            # Plain 10-digit
            r'(?<!\d)\d{10}(?!\d)',
            # With dashes: 555-123-4567
            r'\d{3}[\-\s]\d{3}[\-\s]\d{4}',
        ]

        for area in search_areas:
            for pattern in patterns:
                match = re.search(pattern, area)
                if match:
                    phone = match.group(0).strip()
                    # Validate: should have at least 10 digits
                    digits = re.sub(r'\D', '', phone)
                    if 10 <= len(digits) <= 15:
                        return phone
            # If found in header, don't search full text
            if area == text[:500]:
                continue

        return ""

    def _extract_projects(self, text: str) -> list:
        """Extract project descriptions"""
        projects = []
        lines = text.split('\n')
        in_projects = False

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            # Detect project section
            if len(lower.split()) <= 4 and any(kw in lower for kw in ['projects', 'portfolio', 'personal projects', 'featured projects', 'technical projects']):
                in_projects = True
                continue

            # Detect next section (exit projects)
            if in_projects and self._is_likely_heading(stripped):
                break

            # Collect project lines
            if in_projects and stripped and len(stripped) > 10:
                cleaned = re.sub(r'^[\-\*\u2022\u25cf\u25cb]\s*', '', stripped)
                if cleaned and not cleaned.lower().startswith(('tools:', 'role:', 'project repository')):
                    projects.append(cleaned)

        return projects[:10]

    def _extract_certifications(self, text: str) -> list:
        """Extract certifications"""
        certs = []
        lines = text.split('\n')
        in_certs = False

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            if len(lower.split()) <= 4 and any(kw in lower for kw in ['certification', 'credentials', 'licenses', 'certificates']):
                in_certs = True
                continue

            if in_certs and self._is_likely_heading(stripped):
                break

            if in_certs and stripped and len(stripped) > 5:
                cleaned = re.sub(r'^[\-\*\u2022\u25cf\u25cb]\s*', '', stripped)
                if cleaned:
                    certs.append(cleaned)

        return certs[:10]

    def _is_likely_heading(self, line: str) -> bool:
        """Check if a line looks like a section heading"""
        if not line or len(line) > 60:
            return False
        words = line.split()
        if len(words) > 5:
            return False
        lower = line.lower().strip()
        headings = ['experience', 'education', 'skills', 'projects',
                   'certifications', 'summary', 'achievements', 'awards',
                   'work experience', 'technical skills', 'publications',
                   'interests', 'hobbies', 'personal', 'other', 'languages']
        return any(lower == h or lower.startswith(h) for h in headings)

    def extract_job_title(self, jd_text: str) -> str:
        """Extract job title from JD text"""
        lines = jd_text.split('\n')
        # Common JD title patterns
        title_patterns = [
            r'^((?:Senior|Junior|Lead|Staff|Principal)?\s*(?:Software|ML|AI|Data|Full[\s\-]?Stack|Frontend|Backend|DevOps|Cloud)\s*(?:Engineer|Developer|Scientist|Analyst|Architect))',
            r'^((?:Machine Learning|Artificial Intelligence|Data Science)\s+(?:Engineer|Scientist|Analyst))',
        ]

        for line in lines[:10]:
            stripped = line.strip()
            if not stripped or len(stripped) > 100:
                continue
            # Try title patterns
            for pattern in title_patterns:
                match = re.search(pattern, stripped, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            # Fallback: short line that looks like a title
            if len(stripped) < 60 and len(stripped.split()) <= 8:
                if not '@' in stripped and not 'http' in stripped:
                    if any(kw in stripped.lower() for kw in ['engineer', 'developer', 'scientist', 'analyst', 'manager', 'architect']):
                        return stripped

        # Last resort: first non-empty short line
        for line in lines[:5]:
            stripped = line.strip()
            if stripped and len(stripped) < 80 and len(stripped.split()) <= 8:
                if not '@' in stripped and not 'http' in stripped:
                    return stripped
        return "Position"
