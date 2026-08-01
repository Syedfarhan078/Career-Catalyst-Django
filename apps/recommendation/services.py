import os
import json
import requests
from django.conf import settings
from apps.profiles.models import StudentProfile
from apps.resume.models import Resume
from apps.roadmaps.models import CareerPath, UserRoadmap
from .models import CareerAnalysis

def calculate_initial_readiness_score(user, profile):
    """
    Calculate an initial, rule-based career readiness score based on profile metrics.
    Max Score: 100
    """
    score = 0
    
    # 1. Academic Performance (CGPA) - Max 15 pts
    if profile and profile.cgpa:
        cgpa = float(profile.cgpa)
        if cgpa >= 9.0:
            score += 15
        elif cgpa >= 8.0:
            score += 12
        elif cgpa >= 7.0:
            score += 9
        else:
            score += 5
            
    # 2. Skills Count - Max 25 pts
    if profile and profile.skills:
        skills_raw = profile.skills.replace('\n', ',')
        skills_list = [s.strip() for s in skills_raw.split(',') if s.strip()]
        score += min(len(skills_list) * 2, 25)
        
    # 3. Projects, Experiences & Certifications from default resume - Max 50 pts
    default_resume = Resume.objects.filter(user=user, is_default=True).first()
    if not default_resume:
        default_resume = Resume.objects.filter(user=user).first()
        
    if default_resume:
        # Projects: 5 pts each (Max 20 pts)
        projects_count = default_resume.projects.count()
        score += min(projects_count * 5, 20)
        
        # Experiences: 10 pts each (Max 20 pts)
        experiences_count = default_resume.experiences.count()
        score += min(experiences_count * 10, 20)
        
        # Certifications: 5 pts each (Max 10 pts)
        certifications_count = default_resume.certifications.count()
        score += min(certifications_count * 5, 10)
        
    # 4. Roadmap Enrollments - Max 10 pts
    has_roadmaps = UserRoadmap.objects.filter(user=user).exists()
    if has_roadmaps:
        score += 10
        
    return min(score, 100)


def build_fallback_analysis(user, profile, initial_score, target_role_name=None):
    """
    Fallback rule-based hybrid builder if the LLM connection fails or is unavailable.
    """
    # 1. Match target role from database
    paths = CareerPath.objects.filter(is_active=True)
    matched_path = None
    
    user_goal = (target_role_name or (profile.career_goal if profile else "")).lower()
    
    if user_goal:
        # Try finding a path matching goal string
        for path in paths:
            if path.name.lower() in user_goal or user_goal in path.name.lower():
                matched_path = path
                break
                
    if not matched_path:
        matched_path = paths.first() or CareerPath.objects.create(
            name="Software Engineer", 
            slug="software-engineer", 
            description="Software Engineering Path"
        )
        
    # 2. Extract roadmap details
    milestones = matched_path.milestones.prefetch_related('topics').all()
    roadmap_steps = []
    learning_resources = []
    
    role_skills = []
    for ms in milestones:
        step_topics = []
        for topic in ms.topics.all():
            role_skills.append(topic.title)
            step_topics.append(topic.title)
            if topic.resource_url:
                learning_resources.append({
                    "title": topic.title,
                    "type": topic.resource_type,
                    "url": topic.resource_url
                })
        
        roadmap_steps.append({
            "week": ms.week_number,
            "title": ms.title,
            "level": ms.level,
            "topics": step_topics
        })
        
    # 3. Calculate missing skills gaps
    profile_skills_lower = []
    if profile and profile.skills:
        skills_raw = profile.skills.lower().replace('\n', ',')
        profile_skills_lower = [s.strip() for s in skills_raw.split(',') if s.strip()]
        
    missing_skills = []
    for skill in role_skills:
        skill_lower = skill.lower()
        if not any(ps in skill_lower or skill_lower in ps for ps in profile_skills_lower):
            if skill not in missing_skills:
                missing_skills.append(skill)
                
    if not missing_skills:
        missing_skills = ["Advanced Backend Architectures", "Docker & Kubernetes Deployment"]
        
    # 4. Generate ATS resume suggestions
    ats_score = int(initial_score * 0.9) if initial_score > 0 else 60
    resume_suggestions = [
        "Include metrics and quantities in your experience descriptions.",
        "Add missing technical skills directly to your skills section.",
        "Ensure your layout matches standard one-page single-column formats."
    ]
    
    confidence = 80 if profile_skills_lower else 50
    strengths = ["Strong core language fundamentals", "Good academic standing and CGPA"]
    weaknesses = ["Lack of hands-on deployment/DevOps experience", "Missing industry-recognized certifications"]
    
    certifications = [f"AWS Certified Cloud Practitioner", f"Google Professional {matched_path.name}"]
    projects = [f"Scale-tested serverless backend implementation", f"Data analysis dashboard tool"]
    interview_topics = ["Data Structures & Algorithms", "System Design & Caching Layers", "Behavioral STAR Scenarios"]
    
    feedback = (
        f"You show promising foundations for a {matched_path.name} trajectory. "
        f"To progress, focus on completing the missing technical skills and building a capstone portfolio project."
    )
    
    # 5. Internships & Placement
    internship = "Ready" if initial_score >= 65 else "Almost Ready"
    placement = "Ready" if initial_score >= 80 else "Need Preparation"
    
    thirty_day = [
        f"Enroll in the {matched_path.name} roadmap.",
        f"Add the skills {', '.join(missing_skills[:3])} to your practice queue."
    ]
    ninety_day = [
        "Complete a mid-sized portfolio project using your target stack.",
        "Apply to junior/internship postings on the Career Catalyst platform."
    ]
    
    motivational = f"Great effort! Keep pursuing your goals in {matched_path.name} and stay consistent!"
    
    if not learning_resources:
        learning_resources = [
            {"title": "Python Language Tutorial", "type": "Documentation", "url": "https://docs.python.org/3/tutorial/"},
            {"title": "Git SCM Documentations", "type": "Documentation", "url": "https://git-scm.com/doc"},
            {"title": "Django Quick Start Tutorial", "type": "Documentation", "url": "https://docs.djangoproject.com/en/stable/intro/tutorial01/"},
            {"title": "Docker Container Tutorial", "type": "Course", "url": "https://docs.docker.com/get-started/"},
            {"title": "SQL Database Basics", "type": "Article", "url": "https://www.w3schools.com/sql/"}
        ]

    return {
        "career_readiness_score": initial_score,
        "recommended_career": matched_path.name,
        "confidence_score": confidence,
        "overall_feedback": feedback,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "missing_skills": missing_skills,
        "recommended_certifications": certifications,
        "recommended_projects": projects,
        "interview_topics": interview_topics,
        "roadmap_json": roadmap_steps,
        "learning_resources_json": learning_resources[:6],
        "ats_resume_score": ats_score,
        "resume_suggestions": resume_suggestions,
        "internship_readiness": internship,
        "placement_readiness": placement,
        "thirty_day_plan": thirty_day,
        "ninety_day_plan": ninety_day,
        "motivational_message": motivational
    }


def generate_career_recommendation(user, target_role_name=None):
    """
    Collects profile details and database roadmaps, runs hybrid Groq API prompts,
    and returns a saved CareerAnalysis database object.
    """
    try:
        profile = user.studentprofile
    except StudentProfile.DoesNotExist:
        raise ValueError("Profile incomplete. Please fill out your profile details first.")
        
    initial_score = calculate_initial_readiness_score(user, profile)
    
    # 1. Fetch available career paths and database data
    paths = CareerPath.objects.filter(is_active=True)
    paths_list = []
    
    for path in paths:
        milestones_list = []
        for ms in path.milestones.all():
            topics = [t.title for t in ms.topics.all()]
            milestones_list.append(f"Week {ms.week_number} ({ms.title}): topics={topics}")
            
        paths_list.append({
            "name": path.name,
            "description": path.description,
            "difficulty": path.difficulty,
            "milestones": milestones_list
        })
        
    # 2. Build prompt context payload
    student_data = {
        "name": f"{user.first_name} {user.last_name}",
        "college": profile.college,
        "degree": profile.degree,
        "branch": profile.branch,
        "cgpa": str(profile.cgpa) if profile.cgpa else "N/A",
        "current_skills": profile.skills,
        "target_goal": target_role_name or profile.career_goal,
        "calculated_readiness_score": initial_score
    }
    
    # Check if a custom Groq API Key is available
    api_key = os.getenv("GROQ_API_KEY")
    analysis_data = None
    
    if api_key:
        try:
            prompt = (
                f"You are an expert AI Career Coach. Compare this student profile with our existing database paths.\n\n"
                f"Student profile:\n{json.dumps(student_data, indent=2)}\n\n"
                f"Available roles and roadmap milestones in our system:\n{json.dumps(paths_list, indent=2)}\n\n"
                f"Instructions:\n"
                f"1. Choose the best matching career path from the available system roles.\n"
                f"2. Compare student skills with role milestones to identify missing skills.\n"
                f"3. Refine the readiness score based on their projects/skills.\n"
                f"4. Output STRICT JSON ONLY matching the following schema:\n"
                f"{{\n"
                f"  \"career_readiness_score\": int,\n"
                f"  \"recommended_career\": \"string (MUST match one of our available role names!)\",\n"
                f"  \"confidence_score\": int,\n"
                f"  \"overall_feedback\": \"string\",\n"
                f"  \"strengths\": [\"string\"],\n"
                f"  \"weaknesses\": [\"string\"],\n"
                f"  \"missing_skills\": [\"string\"],\n"
                f"  \"recommended_certifications\": [\"string\"],\n"
                f"  \"recommended_projects\": [\"string\"],\n"
                f"  \"interview_topics\": [\"string\"],\n"
                f"  \"roadmap_json\": [weekly steps matching milestones],\n"
                f"  \"learning_resources_json\": [list of dicts with title, type, url],\n"
                f"  \"ats_resume_score\": int,\n"
                f"  \"resume_suggestions\": [\"string\"],\n"
                f"  \"internship_readiness\": \"string\",\n"
                f"  \"placement_readiness\": \"string\",\n"
                f"  \"thirty_day_plan\": [\"string\"],\n"
                f"  \"ninety_day_plan\": [\"string\"],\n"
                f"  \"motivational_message\": \"string\"\n"
                f"}}\n"
                f"Do not output markdown code blocks or conversational text. Output raw JSON format only."
            )
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a career recommendations service. You always respond in raw JSON format strictly matching the schema."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3
            }
            
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=12
            )
            
            if response.status_code == 200:
                result_json = response.json()
                raw_content = result_json["choices"][0]["message"]["content"]
                analysis_data = json.loads(raw_content)
        except Exception as e:
            # Logs the exception to console and lets fallback handle it
            print("Groq API completion failed:", e)
            
    if not analysis_data:
        # Fallback to smart rule-based local parser
        analysis_data = build_fallback_analysis(user, profile, initial_score, target_role_name)
        
    # Save the analysis data to the database
    analysis = CareerAnalysis.objects.create(
        user=user,
        career_readiness_score=analysis_data.get("career_readiness_score", initial_score),
        recommended_career=analysis_data.get("recommended_career", "Software Engineer"),
        confidence_score=analysis_data.get("confidence_score", 70),
        overall_feedback=analysis_data.get("overall_feedback", "Overall feedback details."),
        strengths=analysis_data.get("strengths", []),
        weaknesses=analysis_data.get("weaknesses", []),
        missing_skills=analysis_data.get("missing_skills", []),
        recommended_certifications=analysis_data.get("recommended_certifications", []),
        recommended_projects=analysis_data.get("recommended_projects", []),
        interview_topics=analysis_data.get("interview_topics", []),
        roadmap_json=analysis_data.get("roadmap_json", []),
        learning_resources_json=analysis_data.get("learning_resources_json", []),
        ats_resume_score=analysis_data.get("ats_resume_score", 70),
        resume_suggestions=analysis_data.get("resume_suggestions", []),
        internship_readiness=analysis_data.get("internship_readiness", "Almost Ready"),
        placement_readiness=analysis_data.get("placement_readiness", "Need Preparation"),
        thirty_day_plan=analysis_data.get("thirty_day_plan", []),
        ninety_day_plan=analysis_data.get("ninety_day_plan", []),
        motivational_message=analysis_data.get("motivational_message", "Stay focused!")
    )
    
    return analysis
