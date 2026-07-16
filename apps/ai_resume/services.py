import re
from .models import ResumeAnalysis, MissingSkill, ImprovementSuggestion

ROLE_DATABASES = {
    "software engineer": {
        "keywords": ["git", "sql", "react", "html", "css", "docker", "django", "spring boot", "node.js", "databases", "aws", "apis", "ci/cd", "agile", "javascript", "java", "python", "c++"],
        "skills": ["python", "java", "javascript", "c++", "git", "sql", "react", "html", "css", "docker", "django", "aws", "node.js"],
        "certifications": ["aws certified developer", "google cloud associate", "oracle certified java professional"]
    },
    "data scientist": {
        "keywords": ["pandas", "numpy", "scikit-learn", "machine learning", "statistics", "data visualization", "tableau", "powerbi", "jupyter", "tensorflow", "pytorch", "deep learning", "r", "python", "sql", "big data"],
        "skills": ["python", "r", "sql", "pandas", "numpy", "scikit-learn", "machine learning", "statistics", "tableau", "tensorflow", "pytorch"],
        "certifications": ["google professional data engineer", "microsoft certified: power bi data analyst", "certified analytics professional"]
    },
    "product manager": {
        "keywords": ["product roadmap", "agile", "scrum", "user stories", "market research", "analytics", "jira", "leadership", "communication", "product strategy", "sql", "ab testing", "stakeholder management", "metrics"],
        "skills": ["product roadmap", "agile", "scrum", "jira", "leadership", "communication", "product strategy", "sql"],
        "certifications": ["certified scrum product owner (cspo)", "pragmatic institute certification", "pmp"]
    },
    "ml engineer": {
        "keywords": ["pytorch", "tensorflow", "keras", "deep learning", "machine learning", "scikit-learn", "sql", "docker", "kubernetes", "aws", "pandas", "numpy", "git", "nlp", "computer vision", "python", "mlops"],
        "skills": ["python", "pytorch", "tensorflow", "deep learning", "machine learning", "scikit-learn", "sql", "docker", "kubernetes", "aws", "mlops"],
        "certifications": ["tensorflow developer certificate", "aws certified machine learning", "google cloud ml engineer"]
    },
    "default": {
        "keywords": ["communication", "teamwork", "problem solving", "leadership", "time management", "project management", "excel", "git", "sql", "python", "microsoft office"],
        "skills": ["communication", "teamwork", "problem solving", "leadership", "git", "sql", "excel"],
        "certifications": ["project management professional (pmp)", "scrum master"]
    }
}

def analyze_resume_data(text, target_role, user, resume=None, uploaded_file=None):
    """
    Perform local rule-based analysis of the resume text against the target role.
    """
    text_lower = text.lower()
    role_key = target_role.lower().strip()
    
    # Select database or default
    db = ROLE_DATABASES.get(role_key)
    if not db:
        # Try substring matching
        found_db = False
        for k in ROLE_DATABASES.keys():
            if k in role_key or role_key in k:
                db = ROLE_DATABASES[k]
                found_db = True
                break
        if not found_db:
            db = ROLE_DATABASES["default"]

    # 1. Completeness Score (Check section headings)
    sections_checked = {
        "Education": any(h in text_lower for h in ["education", "academic", "university", "college", "degree"]),
        "Experience": any(h in text_lower for h in ["experience", "employment", "work history", "professional history", "career"]),
        "Projects": any(h in text_lower for h in ["projects", "personal projects", "portfolio"]),
        "Skills": any(h in text_lower for h in ["skills", "technical skills", "expertise", "competencies"]),
        "Certifications": any(h in text_lower for h in ["certifications", "certificates", "credentials", "awards"])
    }
    completeness_count = sum(1 for present in sections_checked.values() if present)
    completeness_score_100 = int((completeness_count / 5) * 100)

    # 2. Formatting Score (Check contact info & formatting)
    email_found = bool(re.search(r'[\w\.-]+@[\w\.-]+', text))
    phone_found = bool(re.search(r'\+?\d[\d -]{8,}\d', text))
    linkedin_found = "linkedin.com" in text_lower
    github_found = "github.com" in text_lower
    
    formatting_criteria = [email_found, phone_found, linkedin_found, github_found]
    formatting_score_100 = int((sum(1 for c in formatting_criteria if c) / 4) * 100)

    # 3. Keyword Score
    keywords_found = [kw for kw in db["keywords"] if kw in text_lower]
    total_kws = len(db["keywords"])
    keyword_score_100 = int((len(keywords_found) / total_kws) * 100) if total_kws > 0 else 0

    # 4. Skill Score
    skills_found = [s for s in db["skills"] if s in text_lower]
    # Reward finding 5 or more matching skills
    skill_score_100 = min(100, int((len(skills_found) / 5) * 100))

    # 5. Readability Score (based on text density and word count)
    words = text.split()
    word_count = len(words)
    if 300 <= word_count <= 800:
        readability_score_100 = 100
    elif 150 <= word_count < 300 or 800 < word_count <= 1200:
        readability_score_100 = 75
    elif 50 <= word_count < 150 or 1200 < word_count <= 1800:
        readability_score_100 = 50
    else:
        readability_score_100 = 25

    # Overall Score (Average of all subscores)
    overall_score = int(
        (completeness_score_100 + formatting_score_100 + keyword_score_100 + skill_score_100 + readability_score_100) / 5
    )

    # Create analysis record
    analysis = ResumeAnalysis.objects.create(
        user=user,
        resume=resume,
        uploaded_file=uploaded_file,
        raw_text=text,
        target_role=target_role,
        overall_score=overall_score,
        ats_score=overall_score, # Mapping overall score to ATS
        grammar_score=readability_score_100, # Mapping Readability to Grammar
        keyword_score=keyword_score_100,
        skill_score=skill_score_100,
        feedback=f"Analyzed resume text for role '{target_role}'. Checked {completeness_count}/5 major sections, found {len(keywords_found)} matching keywords and {len(skills_found)} skills. Readability checked against word count of {word_count}."
    )

    # Save Missing Skills
    missing_skills = [s for s in db["skills"] if s not in skills_found]
    for s in missing_skills:
        MissingSkill.objects.create(
            analysis=analysis,
            skill_name=s.capitalize(),
            importance="High" if s in db["skills"][:4] else "Medium",
            recommendation=f"Integrate technical skill '{s.capitalize()}' in your skills section or descriptions."
        )

    # Save Improvement Suggestions
    # Formatting suggestions
    if not email_found:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Content",
            priority="High",
            description="Add an email address to your header so recruiters can contact you."
        )
    if not phone_found:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Content",
            priority="High",
            description="Add a professional phone number to the contact header."
        )
    if not linkedin_found:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Content",
            priority="Medium",
            description="Include your LinkedIn profile link to improve online credibility."
        )
    if not github_found:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Projects",
            priority="Medium",
            description="Add your GitHub profile link to showcase your source code directly to hiring managers."
        )

    # Section suggestions
    if not sections_checked["Projects"]:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Projects",
            priority="High",
            description="Add a dedicated 'Projects' section describing 2-3 technical achievements and technologies used."
        )
    if not sections_checked["Experience"]:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Experience",
            priority="High",
            description="Include a work experience or internship history section detailing your past roles."
        )
    if not sections_checked["Certifications"]:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Education",
            priority="Low",
            description="Consider adding a certifications section containing relevant online courses/credentials."
        )

    # Keyword / Readability suggestions
    if len(keywords_found) < (total_kws / 2):
        missing_kws = [kw for kw in db["keywords"] if kw not in keywords_found][:5]
        missing_kw_str = ", ".join([k.upper() for k in missing_kws])
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Skills",
            priority="High",
            description=f"Your resume lacks vital keywords for this role. Try incorporating: {missing_kw_str}."
        )

    if word_count < 300:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Content",
            priority="Medium",
            description=f"Your resume is too short ({word_count} words). Expand on your projects and work history details."
        )
    elif word_count > 1000:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Content",
            priority="Medium",
            description=f"Your resume is a bit long ({word_count} words). Condense descriptions to fit within 1-2 pages."
        )

    return analysis
