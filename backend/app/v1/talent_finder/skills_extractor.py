"""
Skills Extraction Service
Technology dictionaries, normalization, and fuzzy matching
"""

from rapidfuzz import fuzz, process
from typing import List, Dict, Set


class SkillsExtractor:
    """Extracts and normalizes technical skills from text"""

    # Normalization mappings: variant -> canonical name
    NORMALIZATION_MAP = {
        "reactjs": "React", "react.js": "React", "react js": "React",
        "nodejs": "Node.js", "node": "Node.js", "node.js": "Node.js",
        "js": "JavaScript", "javascript": "JavaScript", "es6": "JavaScript",
        "ts": "TypeScript", "typescript": "TypeScript",
        "py": "Python", "python3": "Python", "python": "Python",
        "golang": "Go", "go": "Go",
        "cpp": "C++", "c++": "C++",
        "csharp": "C#", "c#": "C#",
        "aws": "AWS", "amazon web services": "AWS",
        "gcp": "Google Cloud", "google cloud platform": "Google Cloud",
        "azure": "Azure", "microsoft azure": "Azure",
        "k8s": "Kubernetes", "kubernetes": "Kubernetes",
        "docker": "Docker", "containerization": "Docker",
        "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
        "mongo": "MongoDB", "mongodb": "MongoDB",
        "mysql": "MySQL", "my sql": "MySQL",
        "redis": "Redis",
        "elasticsearch": "Elasticsearch", "elastic search": "Elasticsearch",
        "kafka": "Kafka", "apache kafka": "Kafka",
        "rabbitmq": "RabbitMQ", "rabbit mq": "RabbitMQ",
        "graphql": "GraphQL", "graph ql": "GraphQL",
        "restapi": "REST API", "rest": "REST API", "restful": "REST API",
        "ci/cd": "CI/CD", "cicd": "CI/CD",
        "jenkins": "Jenkins",
        "terraform": "Terraform",
        "ansible": "Ansible",
        "git": "Git", "github": "GitHub", "gitlab": "GitLab",
        "html": "HTML", "html5": "HTML",
        "css": "CSS", "css3": "CSS",
        "sass": "SASS", "scss": "SASS",
        "tailwind": "TailwindCSS", "tailwindcss": "TailwindCSS",
        "bootstrap": "Bootstrap",
        "nextjs": "Next.js", "next.js": "Next.js", "next": "Next.js",
        "vue": "Vue.js", "vuejs": "Vue.js", "vue.js": "Vue.js",
        "angular": "Angular", "angularjs": "Angular",
        "express": "Express.js", "expressjs": "Express.js",
        "django": "Django",
        "flask": "Flask",
        "fastapi": "FastAPI",
        "spring": "Spring", "spring boot": "Spring Boot", "springboot": "Spring Boot",
        "tensorflow": "TensorFlow", "tf": "TensorFlow",
        "pytorch": "PyTorch", "torch": "PyTorch",
        "scikit-learn": "Scikit-learn", "sklearn": "Scikit-learn",
        "pandas": "Pandas",
        "numpy": "NumPy",
        "machine learning": "Machine Learning", "ml": "Machine Learning",
        "deep learning": "Deep Learning", "dl": "Deep Learning",
        "nlp": "NLP", "natural language processing": "NLP",
        "computer vision": "Computer Vision", "cv": "Computer Vision",
        "llm": "LLM", "large language model": "LLM",
        "genai": "Generative AI", "generative ai": "Generative AI",
        "sql": "SQL",
        "nosql": "NoSQL",
        "dynamodb": "DynamoDB",
        "s3": "AWS S3", "aws s3": "AWS S3",
        "lambda": "AWS Lambda", "aws lambda": "AWS Lambda",
        "ec2": "AWS EC2",
        "linux": "Linux", "ubuntu": "Linux",
        "agile": "Agile", "scrum": "Scrum",
        "jira": "Jira",
        "figma": "Figma",
        "microservices": "Microservices",
        "serverless": "Serverless",
        "devops": "DevOps",
        "sre": "SRE",
        "java": "Java",
        "ruby": "Ruby", "ruby on rails": "Ruby on Rails", "rails": "Ruby on Rails",
        "php": "PHP", "laravel": "Laravel",
        "swift": "Swift",
        "kotlin": "Kotlin",
        "flutter": "Flutter", "dart": "Dart",
        "react native": "React Native",
        "redux": "Redux",
        "webpack": "Webpack",
        "vite": "Vite",
        "jest": "Jest",
        "cypress": "Cypress",
        "selenium": "Selenium",
        "pytest": "Pytest",
        "junit": "JUnit",
        "nginx": "Nginx",
        "apache": "Apache",
        "prometheus": "Prometheus",
        "grafana": "Grafana",
        "datadog": "Datadog",
        "splunk": "Splunk",

        # UI/UX Design
        "figma": "Figma", "sketch": "Sketch", "adobe xd": "Adobe XD",
        "invision": "InVision", "zeplin": "Zeplin",
        "photoshop": "Photoshop", "illustrator": "Illustrator",
        "after effects": "After Effects", "premiere pro": "Premiere Pro",
        "canva": "Canva", "framer": "Framer",
        "wireframing": "Wireframing", "prototyping": "Prototyping",
        "user research": "User Research", "usability testing": "Usability Testing",
        "design thinking": "Design Thinking", "ux research": "UX Research",
        "interaction design": "Interaction Design", "visual design": "Visual Design",
        "responsive design": "Responsive Design", "accessibility": "Accessibility",
        "design systems": "Design Systems", "material design": "Material Design",
        "ui design": "UI Design", "ux design": "UX Design",
        "user interface": "UI Design", "user experience": "UX Design",
        "information architecture": "Information Architecture",
        "heuristic evaluation": "Heuristic Evaluation",
        "a/b testing": "A/B Testing", "ab testing": "A/B Testing",

        # Product Management
        "product management": "Product Management",
        "product strategy": "Product Strategy",
        "product roadmap": "Product Roadmap", "roadmapping": "Product Roadmap",
        "user stories": "User Stories", "epics": "Epics",
        "okrs": "OKRs", "kpis": "KPIs",
        "stakeholder management": "Stakeholder Management",
        "market research": "Market Research", "competitive analysis": "Competitive Analysis",
        "go-to-market": "Go-to-Market Strategy", "gtm": "Go-to-Market Strategy",
        "product analytics": "Product Analytics",
        "feature prioritization": "Feature Prioritization",
        "product discovery": "Product Discovery",
        "customer journey": "Customer Journey Mapping",
        "product-market fit": "Product-Market Fit",
        "mvp": "MVP Development",
        "prd": "PRD Writing", "product requirements": "PRD Writing",
        "jira": "Jira", "confluence": "Confluence",
        "asana": "Asana", "trello": "Trello", "monday.com": "Monday.com",
        "notion": "Notion", "linear": "Linear",
        "mixpanel": "Mixpanel", "amplitude": "Amplitude",
        "google analytics": "Google Analytics", "ga4": "Google Analytics",
        "hotjar": "Hotjar", "fullstory": "FullStory",

        # QA/Testing
        "manual testing": "Manual Testing", "automation testing": "Automation Testing",
        "test automation": "Test Automation",
        "api testing": "API Testing", "postman": "Postman",
        "load testing": "Load Testing", "jmeter": "JMeter",
        "performance testing": "Performance Testing",
        "regression testing": "Regression Testing",
        "test cases": "Test Case Design", "test plans": "Test Planning",
        "bug tracking": "Bug Tracking", "defect management": "Defect Management",
        "qa": "Quality Assurance", "quality assurance": "Quality Assurance",
        "sdlc": "SDLC", "stlc": "STLC",
        "appium": "Appium", "testng": "TestNG",
        "cucumber": "Cucumber", "bdd": "BDD",
        "tdd": "TDD", "test driven": "TDD",
        "playwright": "Playwright", "puppeteer": "Puppeteer",
        "soapui": "SoapUI", "rest assured": "REST Assured",
        "browserstack": "BrowserStack",
        "charles proxy": "Charles Proxy",

        # Technical Writing
        "technical writing": "Technical Writing",
        "api documentation": "API Documentation",
        "documentation": "Documentation",
        "markdown": "Markdown", "restructuredtext": "reStructuredText",
        "swagger": "Swagger/OpenAPI", "openapi": "Swagger/OpenAPI",
        "dita": "DITA", "madcap flare": "MadCap Flare",
        "readme": "README Writing",
        "knowledge base": "Knowledge Base",
        "content strategy": "Content Strategy",
        "style guides": "Style Guides",
        "release notes": "Release Notes",
        "user manuals": "User Manuals",

        # Sales/Business Development
        "salesforce": "Salesforce", "hubspot": "HubSpot",
        "crm": "CRM", "customer relationship management": "CRM",
        "lead generation": "Lead Generation",
        "cold calling": "Cold Calling", "cold emailing": "Cold Outreach",
        "pipeline management": "Pipeline Management",
        "account management": "Account Management",
        "business development": "Business Development",
        "sales strategy": "Sales Strategy",
        "negotiation": "Negotiation",
        "client relationship": "Client Relationship Management",
        "revenue growth": "Revenue Growth",
        "quota attainment": "Quota Attainment",
        "saas sales": "SaaS Sales", "b2b sales": "B2B Sales",
        "b2c sales": "B2C Sales", "enterprise sales": "Enterprise Sales",
        "solution selling": "Solution Selling",
        "consultative selling": "Consultative Selling",
        "outbound sales": "Outbound Sales", "inbound sales": "Inbound Sales",
        "sales enablement": "Sales Enablement",
        "linkedin sales navigator": "LinkedIn Sales Navigator",
        "zoominfo": "ZoomInfo", "apollo": "Apollo.io",
        "outreach": "Outreach.io", "salesloft": "SalesLoft",

        # HR/Recruitment
        "talent acquisition": "Talent Acquisition",
        "recruitment": "Recruitment", "recruiting": "Recruitment",
        "sourcing": "Sourcing", "candidate sourcing": "Sourcing",
        "employer branding": "Employer Branding",
        "onboarding": "Onboarding",
        "performance management": "Performance Management",
        "employee engagement": "Employee Engagement",
        "compensation and benefits": "Compensation & Benefits",
        "hris": "HRIS", "workday": "Workday",
        "successfactors": "SAP SuccessFactors",
        "bamboohr": "BambooHR", "greenhouse": "Greenhouse ATS",
        "lever": "Lever ATS", "icims": "iCIMS",
        "linkedin recruiter": "LinkedIn Recruiter",
        "boolean search": "Boolean Search",
        "diversity hiring": "Diversity & Inclusion",
        "d&i": "Diversity & Inclusion",
        "labor law": "Labor Law", "employment law": "Employment Law",
        "hr analytics": "HR Analytics", "people analytics": "People Analytics",
        "succession planning": "Succession Planning",
        "learning and development": "Learning & Development",
        "l&d": "Learning & Development",
        "organizational development": "Organizational Development",
        "change management": "Change Management",
        "employee relations": "Employee Relations",
        "payroll": "Payroll Management",
        "benefits administration": "Benefits Administration",
    }

    # Skill categories for grouping
    SKILL_CATEGORIES = {
        "frontend": ["React", "Vue.js", "Angular", "Next.js", "HTML", "CSS", "SASS",
                     "TailwindCSS", "Bootstrap", "JavaScript", "TypeScript", "Redux",
                     "Webpack", "Vite"],
        "backend": ["Node.js", "Express.js", "Django", "Flask", "FastAPI", "Spring Boot",
                    "Java", "Python", "Go", "Ruby on Rails", "PHP", "Laravel",
                    "REST API", "GraphQL"],
        "cloud": ["AWS", "Google Cloud", "Azure", "AWS S3", "AWS Lambda", "AWS EC2",
                  "Serverless"],
        "databases": ["PostgreSQL", "MongoDB", "MySQL", "Redis", "Elasticsearch",
                      "DynamoDB", "SQL", "NoSQL"],
        "devops": ["Docker", "Kubernetes", "CI/CD", "Jenkins", "Terraform", "Ansible",
                   "Git", "GitHub", "GitLab", "Nginx", "Linux"],
        "ai_ml": ["Machine Learning", "Deep Learning", "TensorFlow", "PyTorch",
                  "Scikit-learn", "NLP", "Computer Vision", "LLM", "Generative AI",
                  "Pandas", "NumPy"],
        "mobile": ["React Native", "Flutter", "Swift", "Kotlin", "Dart"],
        "testing": ["Jest", "Cypress", "Selenium", "Pytest", "JUnit", "Appium",
                    "Playwright", "Puppeteer", "Manual Testing", "Automation Testing",
                    "API Testing", "Load Testing", "Performance Testing"],
        "messaging": ["Kafka", "RabbitMQ"],
        "monitoring": ["Prometheus", "Grafana", "Datadog", "Splunk"],
        "design": ["Figma", "Sketch", "Adobe XD", "InVision", "Photoshop",
                   "Illustrator", "Wireframing", "Prototyping", "UX Research",
                   "UI Design", "UX Design", "Design Systems", "Design Thinking",
                   "Interaction Design", "Visual Design", "Accessibility"],
        "product": ["Product Management", "Product Strategy", "Product Roadmap",
                    "User Stories", "OKRs", "KPIs", "Jira", "Confluence",
                    "Product Analytics", "Feature Prioritization", "PRD Writing",
                    "Mixpanel", "Amplitude", "Google Analytics"],
        "sales": ["Salesforce", "HubSpot", "CRM", "Lead Generation",
                  "Pipeline Management", "B2B Sales", "SaaS Sales",
                  "Enterprise Sales", "Solution Selling", "Negotiation",
                  "Account Management", "Business Development"],
        "hr": ["Talent Acquisition", "Recruitment", "Sourcing",
                "Employer Branding", "Onboarding", "Performance Management",
                "Employee Engagement", "HRIS", "Workday", "LinkedIn Recruiter",
                "HR Analytics", "Diversity & Inclusion", "Learning & Development",
                "Compensation & Benefits", "Change Management"],
    }

    # All known skills as a flat set for matching
    ALL_SKILLS: Set[str] = set()

    def __init__(self):
        # Build complete skill set from categories and normalization map
        for skills in self.SKILL_CATEGORIES.values():
            self.ALL_SKILLS.update(skills)
        self.ALL_SKILLS.update(self.NORMALIZATION_MAP.values())

    def extract_skills(self, text: str) -> List[str]:
        """Extract and normalize skills from text"""
        found_skills = set()
        text_lower = text.lower()

        # Direct matching from normalization map
        for variant, canonical in self.NORMALIZATION_MAP.items():
            # Use word boundary matching to avoid false positives
            if self._word_in_text(variant, text_lower):
                found_skills.add(canonical)

        # Fuzzy matching for skills not caught by direct matching
        words = self._extract_potential_skill_tokens(text)
        for token in words:
            token_lower = token.lower()
            # Check normalization map with fuzzy matching
            match = process.extractOne(
                token_lower,
                self.NORMALIZATION_MAP.keys(),
                scorer=fuzz.ratio,
                score_cutoff=85
            )
            if match:
                found_skills.add(self.NORMALIZATION_MAP[match[0]])

        return sorted(list(found_skills))

    def _word_in_text(self, word: str, text: str) -> bool:
        """Check if a word/phrase exists in text with basic boundary checking"""
        import re
        # Escape special regex characters in the word
        escaped = re.escape(word)
        pattern = r'(?<![a-zA-Z])' + escaped + r'(?![a-zA-Z])'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _extract_potential_skill_tokens(self, text: str) -> List[str]:
        """Extract potential skill tokens from text"""
        import re
        # Split by common delimiters
        tokens = re.split(r'[,;|\n\t\u2022\u25cf\u25cb\-\*]+', text)
        cleaned = []
        for token in tokens:
            t = token.strip()
            # Skills are typically 1-4 words
            if t and 1 <= len(t.split()) <= 4 and len(t) < 40:
                cleaned.append(t)
        return cleaned

    def get_matched_skills(self, candidate_skills: List[str], jd_skills: List[str]) -> List[str]:
        """Find skills that match between candidate and JD"""
        candidate_set = set(s.lower() for s in candidate_skills)
        matched = []
        for skill in jd_skills:
            if skill.lower() in candidate_set:
                matched.append(skill)
        return matched

    def get_missing_skills(self, candidate_skills: List[str], jd_skills: List[str]) -> List[str]:
        """Find JD skills missing from candidate"""
        candidate_set = set(s.lower() for s in candidate_skills)
        missing = []
        for skill in jd_skills:
            if skill.lower() not in candidate_set:
                missing.append(skill)
        return missing

    def calculate_skills_match_score(self, candidate_skills: List[str], jd_skills: List[str]) -> float:
        """Calculate skills match percentage (0-1)"""
        if not jd_skills:
            return 0.5  # Neutral if no JD skills detected
        matched = self.get_matched_skills(candidate_skills, jd_skills)
        return len(matched) / len(jd_skills)

    def categorize_skills(self, skills: List[str]) -> Dict[str, List[str]]:
        """Categorize skills into groups"""
        categorized = {}
        for category, category_skills in self.SKILL_CATEGORIES.items():
            category_lower = set(s.lower() for s in category_skills)
            matched = [s for s in skills if s.lower() in category_lower]
            if matched:
                categorized[category] = matched
        return categorized
