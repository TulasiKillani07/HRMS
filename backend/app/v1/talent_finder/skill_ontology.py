"""
Skill Ontology Service
Inferred skills graph, synonym mapping, and role-aware weighting
"""

from typing import List, Dict, Set, Tuple


class SkillOntology:
    """
    Maps skills to parent domains and infers implicit skills.
    Enables role-aware weighting and skill graph traversal.
    """

    # Skill -> inferred parent/related skills
    SKILL_GRAPH: Dict[str, List[str]] = {
        # AI/ML chain
        "LangChain": ["LLM", "Generative AI", "RAG", "NLP"],
        "LlamaIndex": ["LLM", "Generative AI", "RAG"],
        "GPT": ["LLM", "Generative AI", "NLP"],
        "ChatGPT": ["LLM", "Generative AI"],
        "OpenAI": ["LLM", "Generative AI", "NLP"],
        "Hugging Face": ["NLP", "Deep Learning", "Machine Learning"],
        "FAISS": ["Vector Database", "RAG", "Machine Learning"],
        "Pinecone": ["Vector Database", "RAG"],
        "ChromaDB": ["Vector Database", "RAG"],
        "Weaviate": ["Vector Database", "RAG"],
        "TensorFlow": ["Deep Learning", "Machine Learning", "AI"],
        "PyTorch": ["Deep Learning", "Machine Learning", "AI"],
        "Scikit-learn": ["Machine Learning", "Data Science"],
        "Keras": ["Deep Learning", "Machine Learning"],
        "XGBoost": ["Machine Learning", "Data Science"],
        "LightGBM": ["Machine Learning", "Data Science"],
        "spaCy": ["NLP", "Machine Learning"],
        "NLTK": ["NLP", "Machine Learning"],
        "OpenCV": ["Computer Vision", "Deep Learning"],
        "YOLO": ["Computer Vision", "Deep Learning", "Object Detection"],
        "Stable Diffusion": ["Generative AI", "Computer Vision", "Deep Learning"],
        "MLflow": ["MLOps", "Machine Learning"],
        "Kubeflow": ["MLOps", "Kubernetes", "Machine Learning"],
        "DVC": ["MLOps", "Machine Learning"],
        "Pandas": ["Data Science", "Data Analysis", "Python"],
        "NumPy": ["Data Science", "Scientific Computing", "Python"],
        "Matplotlib": ["Data Visualization", "Data Science"],
        "Seaborn": ["Data Visualization", "Data Science"],
        "Plotly": ["Data Visualization", "Data Science"],
        "Apache Spark": ["Big Data", "Data Engineering"],
        "Hadoop": ["Big Data", "Data Engineering"],
        "Airflow": ["Data Engineering", "ETL", "Orchestration"],
        "dbt": ["Data Engineering", "ETL", "Analytics Engineering"],
        "Snowflake": ["Data Warehousing", "Cloud", "SQL"],
        "Databricks": ["Big Data", "Data Engineering", "Machine Learning"],

        # Backend chain
        "Flask": ["Backend", "Python", "REST API"],
        "Django": ["Backend", "Python", "REST API", "Full Stack"],
        "FastAPI": ["Backend", "Python", "REST API", "Async"],
        "Express.js": ["Backend", "Node.js", "REST API"],
        "Spring Boot": ["Backend", "Java", "Microservices"],
        "NestJS": ["Backend", "Node.js", "TypeScript"],
        "Ruby on Rails": ["Backend", "Ruby", "Full Stack"],
        "Laravel": ["Backend", "PHP"],
        "GraphQL": ["API Design", "Backend"],
        "gRPC": ["API Design", "Backend", "Microservices"],

        # Frontend chain
        "React": ["Frontend", "JavaScript", "UI Development"],
        "Next.js": ["Frontend", "React", "Full Stack", "SSR"],
        "Vue.js": ["Frontend", "JavaScript", "UI Development"],
        "Angular": ["Frontend", "TypeScript", "UI Development"],
        "Svelte": ["Frontend", "JavaScript", "UI Development"],
        "TailwindCSS": ["Frontend", "CSS", "UI Development"],
        "Redux": ["State Management", "Frontend", "React"],

        # Cloud/DevOps chain
        "Docker": ["Containerization", "DevOps", "Cloud"],
        "Kubernetes": ["Container Orchestration", "DevOps", "Cloud"],
        "Terraform": ["Infrastructure as Code", "DevOps", "Cloud"],
        "Ansible": ["Configuration Management", "DevOps"],
        "Jenkins": ["CI/CD", "DevOps"],
        "GitHub Actions": ["CI/CD", "DevOps"],
        "AWS Lambda": ["Serverless", "AWS", "Cloud"],
        "AWS": ["Cloud", "Infrastructure"],
        "Google Cloud": ["Cloud", "Infrastructure"],
        "Azure": ["Cloud", "Infrastructure"],

        # Database chain
        "PostgreSQL": ["SQL", "Database", "Backend"],
        "MongoDB": ["NoSQL", "Database", "Backend"],
        "Redis": ["Caching", "Database", "Backend"],
        "Elasticsearch": ["Search", "Database", "Analytics"],
        "Neo4j": ["Graph Database", "Database"],
        "DynamoDB": ["NoSQL", "AWS", "Database"],
        "Cassandra": ["NoSQL", "Distributed Systems", "Database"],

        # Mobile chain - ENHANCED with adjacency
        "React Native": ["Mobile", "React", "Cross-Platform", "Mobile State Management", "Mobile UI"],
        "Flutter": ["Mobile", "Cross-Platform", "Dart", "Mobile UI", "Mobile State Management"],
        "Swift": ["Mobile", "iOS", "Native Mobile"],
        "Kotlin": ["Mobile", "Android", "JVM", "Native Mobile"],
        "Dart": ["Flutter", "Mobile", "Cross-Platform"],
        "Expo": ["React Native", "Mobile", "Cross-Platform"],
        "Firebase": ["Mobile Backend", "Cloud", "Mobile"],
        "SwiftUI": ["Mobile", "iOS", "Mobile UI"],
        "Jetpack Compose": ["Mobile", "Android", "Mobile UI"],

        # Design chain
        "Figma": ["UI Design", "UX Design", "Prototyping", "Design"],
        "Sketch": ["UI Design", "UX Design", "Prototyping", "Design"],
        "Adobe XD": ["UI Design", "UX Design", "Prototyping", "Design"],
        "InVision": ["Prototyping", "Design", "Collaboration"],
        "Photoshop": ["Visual Design", "Design"],
        "Illustrator": ["Visual Design", "Design", "Graphics"],
        "Framer": ["Prototyping", "Interaction Design", "Design"],
        "UX Research": ["User Research", "Design Thinking", "UX Design"],
        "Wireframing": ["UI Design", "UX Design", "Prototyping"],
        "Design Systems": ["UI Design", "Design", "Component Design"],

        # Product Management chain
        "Jira": ["Project Management", "Agile", "Product Management"],
        "Confluence": ["Documentation", "Collaboration", "Product Management"],
        "Mixpanel": ["Product Analytics", "Data Analysis"],
        "Amplitude": ["Product Analytics", "Data Analysis"],
        "Google Analytics": ["Analytics", "Data Analysis", "Marketing"],
        "Hotjar": ["UX Research", "Product Analytics", "User Behavior"],

        # QA/Testing chain
        "Selenium": ["Test Automation", "Web Testing", "QA"],
        "Appium": ["Mobile Testing", "Test Automation", "QA"],
        "Playwright": ["Test Automation", "Web Testing", "QA"],
        "JMeter": ["Load Testing", "Performance Testing", "QA"],
        "Postman": ["API Testing", "QA", "REST API"],
        "Cucumber": ["BDD", "Test Automation", "QA"],

        # Sales chain
        "Salesforce": ["CRM", "Sales", "Sales Operations"],
        "HubSpot": ["CRM", "Marketing Automation", "Sales"],
        "LinkedIn Sales Navigator": ["Prospecting", "Sales", "Lead Generation"],
        "ZoomInfo": ["Prospecting", "Lead Generation", "Sales Intelligence"],

        # HR chain
        "Workday": ["HRIS", "HR Tech", "HR Operations"],
        "Greenhouse ATS": ["Recruitment", "ATS", "Talent Acquisition"],
        "Lever ATS": ["Recruitment", "ATS", "Talent Acquisition"],
        "LinkedIn Recruiter": ["Sourcing", "Recruitment", "Talent Acquisition"],
        "BambooHR": ["HRIS", "HR Tech", "HR Operations"],
    }

    # Adjacency map: skills that are TRANSFERABLE to each other
    # Higher score = more transferable (0.0 - 1.0)
    SKILL_ADJACENCY: Dict[str, Dict[str, float]] = {
        "Flutter": {
            "React Native": 0.75,  # Very transferable (both cross-platform mobile)
            "Dart": 1.0,           # Direct requirement
            "Mobile": 0.6,
            "Cross-Platform": 0.7,
            "Swift": 0.4,          # Native mobile, some transfer
            "Kotlin": 0.4,
            "Firebase": 0.5,
            "React": 0.3,          # Component-based UI, some transfer
            "Mobile State Management": 0.6,
            "Mobile UI": 0.7,
        },
        "React Native": {
            "Flutter": 0.75,
            "React": 0.7,
            "Mobile": 0.8,
            "Cross-Platform": 0.8,
            "JavaScript": 0.5,
            "Firebase": 0.5,
        },
        "React": {
            "Next.js": 0.8,
            "Vue.js": 0.6,
            "Angular": 0.5,
            "React Native": 0.5,
            "Frontend": 0.9,
        },
        "Python": {
            "R": 0.4,
            "Julia": 0.3,
        },
        "TensorFlow": {
            "PyTorch": 0.8,
            "Keras": 0.9,
        },
        "AWS": {
            "Google Cloud": 0.7,
            "Azure": 0.7,
        },
    }

    # Role -> critical skill domains (skills in these domains get boosted)
    ROLE_SKILL_WEIGHTS: Dict[str, Dict[str, float]] = {
        "ai_engineer": {
            "Machine Learning": 1.0, "Deep Learning": 1.0, "NLP": 0.9,
            "LLM": 1.0, "Generative AI": 1.0, "Python": 0.9,
            "Data Science": 0.8, "MLOps": 0.7, "Computer Vision": 0.8,
            "Frontend": 0.1, "UI Development": 0.1, "CSS": 0.05,
            "React": 0.1, "Angular": 0.05, "Mobile": 0.05,
        },
        "data_scientist": {
            "Machine Learning": 1.0, "Data Science": 1.0, "Python": 0.9,
            "Data Analysis": 0.9, "Data Visualization": 0.8,
            "Deep Learning": 0.7, "SQL": 0.8, "Statistics": 0.9,
            "Frontend": 0.1, "React": 0.1, "Mobile": 0.05,
        },
        "ml_engineer": {
            "Machine Learning": 1.0, "Deep Learning": 0.9, "MLOps": 0.9,
            "Python": 0.9, "Data Engineering": 0.7, "Cloud": 0.7,
            "Docker": 0.7, "Kubernetes": 0.6,
            "Frontend": 0.1, "React": 0.1, "Mobile": 0.05,
        },
        "frontend_engineer": {
            "Frontend": 1.0, "React": 1.0, "JavaScript": 1.0,
            "TypeScript": 0.9, "CSS": 0.8, "UI Development": 1.0,
            "Machine Learning": 0.1, "Deep Learning": 0.05, "Mobile": 0.2,
        },
        "backend_engineer": {
            "Backend": 1.0, "REST API": 0.9, "Database": 0.9,
            "Microservices": 0.8, "Cloud": 0.7, "Docker": 0.7,
            "Frontend": 0.2, "Machine Learning": 0.1, "Mobile": 0.1,
        },
        "fullstack_engineer": {
            "Frontend": 0.8, "Backend": 0.8, "Database": 0.7,
            "Cloud": 0.6, "REST API": 0.7, "JavaScript": 0.8,
            "React": 0.7, "Node.js": 0.7, "Mobile": 0.2,
        },
        "devops_engineer": {
            "DevOps": 1.0, "Cloud": 1.0, "CI/CD": 0.9,
            "Docker": 0.9, "Kubernetes": 0.9, "Infrastructure as Code": 0.9,
            "Linux": 0.8, "Frontend": 0.05, "React": 0.05, "Mobile": 0.05,
        },
        "data_engineer": {
            "Data Engineering": 1.0, "ETL": 0.9, "SQL": 0.9,
            "Big Data": 0.9, "Cloud": 0.8, "Python": 0.8,
            "Data Warehousing": 0.8, "Frontend": 0.05, "Mobile": 0.05,
        },
        "mobile_developer": {
            "Mobile": 1.0, "Cross-Platform": 1.0, "Flutter": 1.0,
            "Dart": 1.0, "React Native": 0.8, "Mobile UI": 0.9,
            "Mobile State Management": 0.9, "Firebase": 0.7,
            "iOS": 0.7, "Android": 0.7, "REST API": 0.6,
            "CI/CD": 0.5, "Git": 0.4,
            "Backend": 0.2, "Machine Learning": 0.05,
            "DevOps": 0.15, "Cloud": 0.3,
        },
        "flutter_developer": {
            "Flutter": 1.0, "Dart": 1.0, "Mobile": 1.0,
            "Cross-Platform": 0.9, "Mobile UI": 0.9,
            "Mobile State Management": 0.9, "Firebase": 0.7,
            "React Native": 0.6,  # Transferable but not the same
            "iOS": 0.5, "Android": 0.5, "REST API": 0.6,
            "CI/CD": 0.4, "Git": 0.4,
            "Backend": 0.15, "Machine Learning": 0.05,
            "DevOps": 0.1, "React": 0.2,
        },
        "ios_developer": {
            "Swift": 1.0, "iOS": 1.0, "Mobile": 1.0,
            "SwiftUI": 0.9, "Mobile UI": 0.9,
            "Firebase": 0.6, "REST API": 0.6,
            "Flutter": 0.4, "React Native": 0.4,
            "Backend": 0.15, "Machine Learning": 0.05,
        },
        "android_developer": {
            "Kotlin": 1.0, "Android": 1.0, "Mobile": 1.0,
            "Jetpack Compose": 0.9, "Mobile UI": 0.9,
            "Firebase": 0.6, "REST API": 0.6,
            "Flutter": 0.4, "React Native": 0.4,
            "Backend": 0.15, "Machine Learning": 0.05,
        },
        "uiux_designer": {
            "UI Design": 1.0, "UX Design": 1.0, "Figma": 1.0,
            "Prototyping": 0.9, "Wireframing": 0.9, "Design Systems": 0.9,
            "User Research": 0.9, "UX Research": 0.9, "Design Thinking": 0.8,
            "Interaction Design": 0.8, "Visual Design": 0.8,
            "Sketch": 0.7, "Adobe XD": 0.7, "InVision": 0.6,
            "Accessibility": 0.7, "A/B Testing": 0.6,
            "HTML": 0.4, "CSS": 0.5, "JavaScript": 0.2,
            "Backend": 0.05, "Machine Learning": 0.02,
        },
        "product_manager": {
            "Product Management": 1.0, "Product Strategy": 1.0,
            "Product Roadmap": 0.9, "User Stories": 0.8,
            "OKRs": 0.7, "KPIs": 0.7, "Stakeholder Management": 0.8,
            "Product Analytics": 0.9, "Feature Prioritization": 0.8,
            "PRD Writing": 0.8, "Market Research": 0.7,
            "Jira": 0.6, "Confluence": 0.5,
            "Mixpanel": 0.6, "Amplitude": 0.6, "Google Analytics": 0.6,
            "A/B Testing": 0.7, "Data Analysis": 0.6,
            "Agile": 0.7, "Scrum": 0.6,
            "SQL": 0.4, "Python": 0.3,
            "Backend": 0.1, "Frontend": 0.1,
        },
        "qa_engineer": {
            "Quality Assurance": 1.0, "Test Automation": 1.0,
            "Manual Testing": 0.8, "Automation Testing": 1.0,
            "Selenium": 0.9, "Appium": 0.8, "Playwright": 0.9,
            "API Testing": 0.8, "Postman": 0.7,
            "Load Testing": 0.7, "Performance Testing": 0.7,
            "JMeter": 0.7, "Cucumber": 0.7, "BDD": 0.7, "TDD": 0.7,
            "SDLC": 0.6, "STLC": 0.7, "Bug Tracking": 0.6,
            "Python": 0.6, "Java": 0.5, "JavaScript": 0.5,
            "CI/CD": 0.6, "Git": 0.5,
            "Machine Learning": 0.05, "Frontend": 0.1,
        },
        "technical_writer": {
            "Technical Writing": 1.0, "Documentation": 1.0,
            "API Documentation": 0.9, "Swagger/OpenAPI": 0.8,
            "Markdown": 0.7, "Content Strategy": 0.8,
            "Knowledge Base": 0.7, "Style Guides": 0.7,
            "User Manuals": 0.8, "Release Notes": 0.7,
            "DITA": 0.6, "MadCap Flare": 0.6,
            "Git": 0.5, "HTML": 0.4,
            "Python": 0.3, "REST API": 0.4,
            "Machine Learning": 0.05,
        },
        "sales_representative": {
            "CRM": 1.0, "Salesforce": 0.9, "HubSpot": 0.8,
            "Lead Generation": 1.0, "Pipeline Management": 0.9,
            "B2B Sales": 0.9, "SaaS Sales": 0.9, "Enterprise Sales": 0.8,
            "Solution Selling": 0.8, "Consultative Selling": 0.8,
            "Negotiation": 0.8, "Account Management": 0.8,
            "Business Development": 0.9, "Cold Outreach": 0.7,
            "Sales Strategy": 0.8, "Revenue Growth": 0.7,
            "LinkedIn Sales Navigator": 0.6, "ZoomInfo": 0.5,
            "Product Management": 0.3, "Marketing": 0.3,
            "Python": 0.05, "Machine Learning": 0.02,
        },
        "hr_recruiter": {
            "Talent Acquisition": 1.0, "Recruitment": 1.0,
            "Sourcing": 0.9, "LinkedIn Recruiter": 0.8,
            "Boolean Search": 0.7, "Employer Branding": 0.7,
            "Onboarding": 0.7, "HRIS": 0.6, "Workday": 0.6,
            "Greenhouse ATS": 0.7, "Lever ATS": 0.7,
            "Diversity & Inclusion": 0.7, "HR Analytics": 0.6,
            "Employee Engagement": 0.6, "Stakeholder Management": 0.6,
            "Compensation & Benefits": 0.5,
            "Python": 0.05, "Machine Learning": 0.02,
        },
        "hr_manager": {
            "Performance Management": 1.0, "Employee Relations": 0.9,
            "Talent Acquisition": 0.8, "Recruitment": 0.7,
            "Learning & Development": 0.8, "Change Management": 0.8,
            "Organizational Development": 0.8, "Succession Planning": 0.7,
            "HRIS": 0.7, "Workday": 0.6, "HR Analytics": 0.7,
            "Compensation & Benefits": 0.7, "Labor Law": 0.7,
            "Employee Engagement": 0.8, "Diversity & Inclusion": 0.7,
            "Stakeholder Management": 0.7, "Payroll Management": 0.5,
            "Python": 0.05, "Machine Learning": 0.02,
        },
    }

    # PRIMARY SKILLS per role - if these are ALL missing, apply hard penalty
    ROLE_PRIMARY_SKILLS: Dict[str, List[str]] = {
        "ai_engineer": ["Python", "Machine Learning"],
        "ml_engineer": ["Python", "Machine Learning"],
        "data_scientist": ["Python", "Machine Learning"],
        "frontend_engineer": ["JavaScript", "React"],
        "backend_engineer": ["Backend", "REST API"],
        "devops_engineer": ["Docker", "Cloud", "CI/CD"],
        "data_engineer": ["Python", "SQL", "Data Engineering"],
        "mobile_developer": ["Mobile"],
        "flutter_developer": ["Flutter", "Dart"],
        "ios_developer": ["Swift", "iOS"],
        "android_developer": ["Kotlin", "Android"],
        "fullstack_engineer": ["JavaScript", "Backend"],
        "uiux_designer": ["UI Design", "UX Design"],
        "product_manager": ["Product Management"],
        "qa_engineer": ["Quality Assurance"],
        "technical_writer": ["Technical Writing", "Documentation"],
        "sales_representative": ["Sales", "CRM"],
        "hr_recruiter": ["Recruitment", "Talent Acquisition"],
        "hr_manager": ["Performance Management", "Employee Relations"],
    }

    # TRANSFERABLE SKILLS per role
    ROLE_TRANSFERABLE_SKILLS: Dict[str, List[str]] = {
        "flutter_developer": ["React Native", "Mobile", "Cross-Platform", "Dart", "Firebase", "Mobile UI"],
        "ios_developer": ["Flutter", "React Native", "Mobile", "Swift"],
        "android_developer": ["Flutter", "React Native", "Mobile", "Kotlin"],
        "mobile_developer": ["Flutter", "React Native", "Swift", "Kotlin", "Cross-Platform"],
        "frontend_engineer": ["React Native", "Mobile UI", "TypeScript"],
        "ai_engineer": ["Deep Learning", "NLP", "Data Science"],
        "backend_engineer": ["Microservices", "Database", "Cloud"],
        "uiux_designer": ["Figma", "Sketch", "Prototyping", "Wireframing", "Design Thinking",
                          "User Research", "Visual Design", "Interaction Design"],
        "product_manager": ["Product Analytics", "Jira", "Stakeholder Management",
                           "Market Research", "A/B Testing", "Data Analysis", "Agile"],
        "qa_engineer": ["Selenium", "Appium", "Playwright", "API Testing", "Manual Testing",
                       "Test Automation", "BDD", "Performance Testing"],
        "technical_writer": ["API Documentation", "Markdown", "Swagger/OpenAPI",
                            "Content Strategy", "Knowledge Base"],
        "sales_representative": ["Salesforce", "HubSpot", "Lead Generation",
                                "Pipeline Management", "Negotiation", "B2B Sales"],
        "hr_recruiter": ["Sourcing", "LinkedIn Recruiter", "Boolean Search",
                        "Employer Branding", "HRIS", "Greenhouse ATS"],
        "hr_manager": ["Talent Acquisition", "Learning & Development", "HRIS",
                      "Change Management", "HR Analytics", "Compensation & Benefits"],
    }

    # Keywords that identify role type from JD
    ROLE_DETECTION_KEYWORDS: Dict[str, List[str]] = {
        "flutter_developer": [
            "flutter", "dart", "flutter developer", "flutter engineer",
        ],
        "mobile_developer": [
            "mobile developer", "mobile engineer", "mobile app",
            "android developer", "ios developer", "cross-platform",
            "react native developer",
        ],
        "ios_developer": [
            "ios developer", "ios engineer", "swift developer", "swiftui",
        ],
        "android_developer": [
            "android developer", "android engineer", "kotlin developer",
        ],
        "uiux_designer": [
            "ui designer", "ux designer", "ui/ux", "ux/ui",
            "product designer", "visual designer", "interaction designer",
            "design system", "figma", "user experience designer",
            "user interface designer",
        ],
        "product_manager": [
            "product manager", "product owner", "pm", "product lead",
            "product management", "associate product manager",
            "senior product manager", "group product manager",
        ],
        "qa_engineer": [
            "qa engineer", "quality assurance", "test engineer",
            "sdet", "automation engineer", "test analyst",
            "quality engineer", "qa analyst", "qa lead",
        ],
        "technical_writer": [
            "technical writer", "documentation", "content developer",
            "api writer", "documentation engineer", "information developer",
        ],
        "sales_representative": [
            "sales", "account executive", "business development",
            "sdr", "bdr", "sales representative", "sales engineer",
            "account manager", "sales manager", "sales development",
        ],
        "hr_recruiter": [
            "recruiter", "talent acquisition", "sourcing",
            "recruitment", "hiring", "talent partner",
            "recruitment specialist", "headhunter",
        ],
        "hr_manager": [
            "hr manager", "human resources", "people operations",
            "hr business partner", "hrbp", "people manager",
            "hr director", "chief people officer",
        ],
        "ai_engineer": [
            "ai engineer", "artificial intelligence", "machine learning engineer",
            "ml engineer", "deep learning", "nlp engineer", "llm engineer",
            "generative ai", "computer vision engineer"
        ],
        "data_scientist": [
            "data scientist", "data science", "analytics", "statistical",
            "research scientist", "quantitative"
        ],
        "ml_engineer": [
            "ml engineer", "machine learning engineer", "mlops",
            "ml platform", "ml infrastructure"
        ],
        "frontend_engineer": [
            "frontend", "front-end", "front end", "ui developer",
            "react developer", "angular developer", "vue developer"
        ],
        "backend_engineer": [
            "backend", "back-end", "back end", "server-side",
            "api developer", "microservices"
        ],
        "fullstack_engineer": [
            "full stack", "fullstack", "full-stack"
        ],
        "devops_engineer": [
            "devops", "site reliability", "sre", "platform engineer",
            "infrastructure engineer", "cloud engineer"
        ],
        "data_engineer": [
            "data engineer", "data pipeline", "etl", "data platform",
            "analytics engineer"
        ],
    }

    def detect_role_type(self, jd_text: str) -> str:
        """Detect the role type from JD text for role-aware weighting"""
        jd_lower = jd_text.lower()

        role_scores = {}
        for role, keywords in self.ROLE_DETECTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in jd_lower)
            if score > 0:
                role_scores[role] = score

        if role_scores:
            return max(role_scores, key=role_scores.get)
        return "fullstack_engineer"  # Default

    def get_inferred_skills(self, explicit_skills: List[str]) -> List[str]:
        """
        Given explicit skills, infer additional implicit skills.
        E.g., LangChain -> LLM, Generative AI, RAG
        """
        inferred = set()
        for skill in explicit_skills:
            if skill in self.SKILL_GRAPH:
                inferred.update(self.SKILL_GRAPH[skill])
            # Also check case-insensitive
            for graph_skill, parents in self.SKILL_GRAPH.items():
                if skill.lower() == graph_skill.lower():
                    inferred.update(parents)
                    break

        # Remove skills already explicitly listed
        explicit_lower = set(s.lower() for s in explicit_skills)
        inferred = {s for s in inferred if s.lower() not in explicit_lower}

        return sorted(list(inferred))

    def get_role_weight_for_skill(self, skill: str, role_type: str) -> float:
        """
        Get the importance weight of a skill for a given role type.
        Returns 0.0-1.0 where 1.0 means critical for the role.
        """
        weights = self.ROLE_SKILL_WEIGHTS.get(role_type, {})

        # Direct match
        if skill in weights:
            return weights[skill]

        # Check if skill belongs to a weighted domain via graph
        if skill in self.SKILL_GRAPH:
            parent_domains = self.SKILL_GRAPH[skill]
            domain_weights = [weights.get(d, 0.5) for d in parent_domains]
            if domain_weights:
                return max(domain_weights)

        return 0.5  # Default neutral weight

    def calculate_role_aware_skill_score(self, matched_skills: List[str],
                                          missing_skills: List[str],
                                          role_type: str) -> float:
        """
        Calculate skill match score with role-aware weighting.
        Missing 'React' for an AI role barely matters.
        Missing 'Python' for an AI role matters a lot.
        """
        if not matched_skills and not missing_skills:
            return 0.5

        weighted_matched = sum(
            self.get_role_weight_for_skill(s, role_type) for s in matched_skills
        )
        weighted_missing = sum(
            self.get_role_weight_for_skill(s, role_type) for s in missing_skills
        )

        total_weight = weighted_matched + weighted_missing
        if total_weight == 0:
            return 0.5

        base_score = weighted_matched / total_weight

        # Apply transferability bonus
        transfer_bonus = self._calculate_transferability_bonus(matched_skills, role_type)
        base_score = min(1.0, base_score + transfer_bonus)

        return base_score

    def calculate_primary_skill_penalty(self, candidate_skills: List[str],
                                         role_type: str) -> float:
        """
        Calculate penalty for missing PRIMARY skills.
        If the JD's core framework is completely absent, apply hard penalty.
        Returns a multiplier (0.45 - 1.0). Lower = bigger penalty.
        """
        primary_skills = self.ROLE_PRIMARY_SKILLS.get(role_type, [])
        if not primary_skills:
            return 1.0  # No penalty if no primary skills defined

        candidate_lower = set(s.lower() for s in candidate_skills)
        # Also check inferred skills
        inferred = self.get_inferred_skills(candidate_skills)
        all_candidate = candidate_lower | set(s.lower() for s in inferred)

        # Count how many primary skills are present
        primary_matched = sum(
            1 for ps in primary_skills
            if ps.lower() in all_candidate
        )

        if primary_matched == 0:
            # NONE of the primary skills present — check transferable
            transferable = self.ROLE_TRANSFERABLE_SKILLS.get(role_type, [])
            transfer_matched = sum(
                1 for ts in transferable
                if ts.lower() in all_candidate
            )
            if transfer_matched >= 3:
                # Strong transferable background — moderate penalty
                return 0.60
            elif transfer_matched >= 1:
                # Some transferable skills — significant penalty
                return 0.50
            else:
                # No primary AND no transferable — very hard penalty
                return 0.40
        elif primary_matched < len(primary_skills):
            # Some primary skills present but not all
            ratio = primary_matched / len(primary_skills)
            return 0.70 + (ratio * 0.30)  # 0.70 to 1.0
        else:
            # All primary skills present
            return 1.0

    def _calculate_transferability_bonus(self, matched_skills: List[str],
                                          role_type: str) -> float:
        """
        Calculate bonus for having transferable/adjacent skills.
        E.g., React Native experience for a Flutter role gets a bonus.
        """
        transferable = self.ROLE_TRANSFERABLE_SKILLS.get(role_type, [])
        if not transferable:
            return 0.0

        matched_lower = set(s.lower() for s in matched_skills)
        transfer_count = sum(
            1 for ts in transferable
            if ts.lower() in matched_lower
        )

        # Bonus: up to 0.10 for having transferable skills
        if transfer_count >= 3:
            return 0.10
        elif transfer_count >= 2:
            return 0.06
        elif transfer_count >= 1:
            return 0.03
        return 0.0
