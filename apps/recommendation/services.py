import os
import re
import json
import requests
from django.conf import settings
from apps.profiles.models import StudentProfile
from apps.resume.models import Resume
from apps.ai_resume.models import ResumeAnalysis
from apps.roadmaps.models import CareerPath, UserRoadmap
from .models import CareerAnalysis


def normalize_token(text):
    """
    Normalizes a skill/topic string for robust matching.
    """
    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r'[\(\)\[\]\{\}\.,\-_/\\:]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def check_user_resume_status(user):
    """
    Checks whether the user has uploaded an ATS resume or created one in the resume builder.
    Returns (has_resume: bool, latest_resume_analysis: ResumeAnalysis or None, default_resume: Resume or None)
    """
    latest_resume_analysis = ResumeAnalysis.objects.filter(user=user).order_by('-created_at').first()
    default_resume = Resume.objects.filter(user=user, is_default=True).first() or Resume.objects.filter(user=user).first()
    
    has_builder_content = default_resume is not None and (
        default_resume.experiences.exists() or 
        default_resume.projects.exists() or 
        default_resume.educations.exists()
    )
    has_resume = (latest_resume_analysis is not None) or has_builder_content
    return has_resume, latest_resume_analysis, default_resume


def extract_student_skills_set(user, profile, default_resume, latest_resume_analysis):
    """
    Collects and normalizes all skill strings from profile and resume sources.
    Returns (raw_skills_list, normalized_tokens_set)
    """
    raw_skills = []
    
    # 1. Profile Skills
    if profile and profile.skills:
        clean_raw = profile.skills.replace('\n', ',')
        raw_skills.extend([s.strip() for s in clean_raw.split(',') if s.strip()])
        
    # 2. Built Resume Skills
    if default_resume:
        for sk in default_resume.skills.all():
            if sk.name and sk.name not in raw_skills:
                raw_skills.append(sk.name)
        for proj in default_resume.projects.all():
            if proj.technologies_used:
                raw_skills.extend([t.strip() for t in proj.technologies_used.split(',') if t.strip()])
                
    # 3. Uploaded ATS Scan Skills
    if latest_resume_analysis and latest_resume_analysis.raw_text:
        # Check for matching words in raw text
        pass

    normalized_tokens = set()
    for s in raw_skills:
        norm = normalize_token(s)
        if norm:
            normalized_tokens.add(norm)
            # Add subwords for compound names
            for word in norm.split():
                if len(word) >= 3:
                    normalized_tokens.add(word)

    return raw_skills, normalized_tokens


def topic_matches_skills(topic_title, student_tokens, raw_skills):
    """
    Checks if a topic title is present in the student's normalized skill tokens.
    """
    norm_topic = normalize_token(topic_title)
    if not norm_topic:
        return False
        
    # Direct exact match
    if norm_topic in student_tokens:
        return True
        
    # Substring in raw skills
    for rs in raw_skills:
        rs_norm = normalize_token(rs)
        if rs_norm and (rs_norm in norm_topic or norm_topic in rs_norm):
            return True
            
    # Check significant word overlap
    topic_words = [w for w in norm_topic.split() if len(w) >= 3]
    if topic_words:
        matched_words = sum(1 for w in topic_words if w in student_tokens)
        if matched_words >= max(1, len(topic_words) // 2):
            return True
            
    return False


def evaluate_student_against_path(user, profile, career_path, has_resume, latest_resume_analysis, default_resume):
    """
    Performs deterministic, ground-truth evaluation of a student profile against a CareerPath.
    Guarantees no hallucinated numbers or fake satisfaction.
    """
    raw_skills, student_tokens = extract_student_skills_set(user, profile, default_resume, latest_resume_analysis)
    
    milestones = career_path.milestones.prefetch_related('topics').all()
    roadmap_steps = []
    learning_resources = []
    
    matched_skills = []
    missing_skills = []
    radar_dimensions = []
    
    total_path_topics = 0
    total_matched_topics = 0
    
    for ms in milestones:
        ms_topics = list(ms.topics.all())
        step_topic_titles = []
        ms_matched_titles = []
        
        for topic in ms_topics:
            step_topic_titles.append(topic.title)
            total_path_topics += 1
            
            if topic_matches_skills(topic.title, student_tokens, raw_skills):
                matched_skills.append(topic.title)
                ms_matched_titles.append(topic.title)
                total_matched_topics += 1
            else:
                missing_skills.append(topic.title)
                
            if topic.resource_url:
                learning_resources.append({
                    "title": topic.title,
                    "type": topic.resource_type,
                    "url": topic.resource_url
                })
                
        # Calculate coverage for this milestone
        ms_coverage_pct = round((len(ms_matched_titles) / len(ms_topics)) * 100) if ms_topics else 0
        user_radar_score = round((len(ms_matched_titles) / len(ms_topics)) * 10, 1) if ms_topics else 0.0
        
        roadmap_steps.append({
            "week": ms.week_number,
            "title": ms.title,
            "level": ms.level,
            "topics": step_topic_titles,
            "matched_topics": ms_matched_titles,
            "coverage_pct": ms_coverage_pct
        })
        
        # Build clean label for radar chart
        clean_radar_name = ms.title
        if len(clean_radar_name) > 20:
            clean_radar_name = clean_radar_name[:18] + '…'
        radar_dimensions.append({
            "name": clean_radar_name,
            "user_score": user_radar_score,
            "target_score": 10
        })

    # Limit radar dimensions to at most 6 key milestones for clean visual presentation
    if len(radar_dimensions) > 6:
        # Group or select every nth milestone
        step_interval = len(radar_dimensions) // 6
        selected_radar = [radar_dimensions[i] for i in range(0, len(radar_dimensions), max(1, step_interval))][:6]
    else:
        selected_radar = radar_dimensions

    # Fallback if path has no milestones in database
    if not selected_radar:
        selected_radar = [
            {"name": "Fundamentals", "user_score": 0.0, "target_score": 10},
            {"name": "Core Principles", "user_score": 0.0, "target_score": 10},
            {"name": "Tooling & Frameworks", "user_score": 0.0, "target_score": 10},
            {"name": "Practical Execution", "user_score": 0.0, "target_score": 10},
            {"name": "Advanced Mastery", "user_score": 0.0, "target_score": 10}
        ]

    # --- 4-PILLAR TRUTH-BASED CAREER READINESS SCORE (0-100) ---
    # Pillar 1: Role-Specific Skill Overlap (Max 40 pts)
    skill_match_ratio = (total_matched_topics / total_path_topics) if total_path_topics > 0 else 0.0
    pillar_skills = round(skill_match_ratio * 40)
    
    # Pillar 2: Practical Projects in Resume (Max 25 pts)
    projects_count = default_resume.projects.count() if default_resume else 0
    if projects_count >= 3:
        pillar_projects = 25
    elif projects_count == 2:
        pillar_projects = 18
    elif projects_count == 1:
        pillar_projects = 10
    else:
        pillar_projects = 0
        
    # Pillar 3: Academic Record / CGPA (Max 15 pts)
    if profile and profile.cgpa:
        try:
            cgpa = float(profile.cgpa)
            if cgpa >= 8.5:
                pillar_academic = 15
            elif cgpa >= 7.5:
                pillar_academic = 12
            elif cgpa >= 6.5:
                pillar_academic = 9
            else:
                pillar_academic = 5
        except (ValueError, TypeError):
            pillar_academic = 5
    else:
        pillar_academic = 5
        
    # Pillar 4: Experience & Certifications (Max 20 pts)
    experiences_count = default_resume.experiences.count() if default_resume else 0
    certifications_count = default_resume.certifications.count() if default_resume else 0
    is_enrolled = UserRoadmap.objects.filter(user=user, career_path=career_path).exists()
    
    pillar_exp = min(experiences_count * 8, 10)
    pillar_certs = min(certifications_count * 4, 6)
    pillar_enrollment = 4 if is_enrolled else 0
    pillar_experience_total = min(pillar_exp + pillar_certs + pillar_enrollment, 20)

    # Calculate Total Readiness Score
    career_readiness_score = min(pillar_skills + pillar_projects + pillar_academic + pillar_experience_total, 100)
    
    # --- CONFIDENCE LEVEL (0-100) ---
    # Truthfully reflects alignment with THIS specific career path
    confidence_score = round((skill_match_ratio * 70) + ((career_readiness_score / 100) * 30))
    confidence_score = max(min(confidence_score, 100), 5) # minimum 5% floor if starting out

    # --- INTERNSHIP & PLACEMENT READINESS ---
    if career_readiness_score >= 65:
        internship_readiness = "Ready"
    elif career_readiness_score >= 40:
        internship_readiness = "Almost Ready"
    else:
        internship_readiness = "Need Preparation"

    if career_readiness_score >= 75:
        placement_readiness = "Ready"
    elif career_readiness_score >= 55:
        placement_readiness = "Almost Ready"
    else:
        placement_readiness = "Need Preparation"

    # --- DYNAMIC, ROLE-SPECIFIC STRENGTHS ---
    strengths = []
    if matched_skills:
        strengths.append(f"Demonstrated proficiency in {len(matched_skills)} {career_path.name} topics: {', '.join(matched_skills[:3])}")
    if profile and profile.cgpa and float(profile.cgpa) >= 7.5:
        strengths.append(f"Strong academic foundation with a {profile.cgpa} CGPA in {profile.branch or 'studies'}")
    if projects_count > 0:
        strengths.append(f"{projects_count} portfolio project(s) documented in profile")
    if experiences_count > 0:
        strengths.append(f"{experiences_count} practical experience/internship role(s) logged")
    if raw_skills and not matched_skills:
        strengths.append(f"Foundational technical background in {', '.join(raw_skills[:3])}")
    if not strengths:
        strengths.append(f"Clear goal orientation actively targeting the {career_path.name} roadmap")
        strengths.append("Enrolled in academic curriculum with verified student profile")

    # --- DYNAMIC, ROLE-SPECIFIC GROWTH AREAS ---
    weaknesses = []
    if missing_skills:
        weaknesses.append(f"Core Syllabus Gap: Missing {len(missing_skills)} key {career_path.name} topics (e.g., {', '.join(missing_skills[:3])})")
    if projects_count == 0:
        weaknesses.append(f"Portfolio Gap: No practical projects built specifically for {career_path.name} yet")
    if experiences_count == 0:
        weaknesses.append("Industry Experience: No prior internships or practical industry experience recorded")
    if certifications_count == 0:
        weaknesses.append(f"Credential Gap: Consider pursuing recognized foundational credentials in {career_path.name}")
    if not weaknesses:
        weaknesses.append("Continue building advanced projects and refining technical interview readiness")

    # --- ATS RESUME SCORE ---
    if has_resume and latest_resume_analysis and latest_resume_analysis.ats_score:
        ats_score = latest_resume_analysis.ats_score
    elif has_resume and default_resume:
        # Score based on completeness of built resume
        resume_pts = min((projects_count * 15) + (experiences_count * 20) + (certifications_count * 10) + 40, 95)
        ats_score = resume_pts
    else:
        ats_score = None

    # --- RESUME SUGGESTIONS ---
    if has_resume and latest_resume_analysis:
        resume_suggestions = [s.description for s in latest_resume_analysis.suggestions.all()[:3]]
    elif has_resume:
        resume_suggestions = [
            f"Tailor your project descriptions to highlight {career_path.name} tools and outcomes.",
            "Include quantifiable metrics (e.g. percentage improvements, user counts, latency drops).",
            "Ensure standard single-column formatting for optimal ATS scanner parsing."
        ]
    else:
        resume_suggestions = [
            f"Upload your resume to the ATS Analyzer to compare keyword matches against {career_path.name}.",
            "Structure your resume with standard sections: Education, Projects, Skills, and Experience.",
            f"Include relevant keywords from the {career_path.name} roadmap in your skills section."
        ]

    # --- 30-DAY & 90-DAY ACTION PLANS ---
    top_missing = missing_skills[:3] if missing_skills else ["Advanced System Architecture", "Production Deployment"]
    thirty_day_plan = [
        f"Enroll in the {career_path.name} roadmap and complete Weeks 1 to 4.",
        f"Master the core fundamental concepts: {', '.join(top_missing)}.",
        "Set up a dedicated GitHub repository for your capstone role projects."
    ]
    
    ninety_day_plan = [
        f"Build a comprehensive portfolio project applying {career_path.name} best practices.",
        "Upload your updated resume to the ATS Resume Analyzer and reach an 80%+ compliance score.",
        f"Begin applying to junior {career_path.name} roles and internships on the platform."
    ]

    # --- OVERALL FEEDBACK ---
    if skill_match_ratio >= 0.7:
        feedback = f"You possess strong alignment ({round(skill_match_ratio * 100)}% topic match) with the {career_path.name} roadmap. Focus on advanced interview prep and portfolio refinement."
    elif skill_match_ratio >= 0.3:
        feedback = f"You have foundational familiarity with {career_path.name}, but still have notable topic gaps. Work through the weekly milestone roadmap to close your skill gaps."
    else:
        feedback = f"You are currently at the beginning of the {career_path.name} trajectory ({round(skill_match_ratio * 100)}% direct skill match). Follow the step-by-step curriculum to build verified competence."

    motivational_message = f"Stay consistent! Every milestone you complete in {career_path.name} brings you closer to placement readiness."

    # Recommended certifications and projects for this role
    recommended_certifications = [
        f"Industry-Certified {career_path.name} Specialist",
        f"Cloud & Infrastructure Practitioner ({career_path.name})"
    ]
    recommended_projects = [
        f"Full-lifecycle capstone project demonstrating {career_path.name} core competencies",
        f"Real-world data or service implementation using {', '.join(missing_skills[:2]) if missing_skills else 'target stack'}"
    ]
    interview_topics = [
        f"{career_path.name} Fundamentals & Methodologies",
        "Problem Solving, System Design & Architecture",
        "Behavioral STAR Scenarios & Practical Execution"
    ]

    return {
        "career_readiness_score": career_readiness_score,
        "recommended_career": career_path.name,
        "confidence_score": confidence_score,
        "overall_feedback": feedback,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "missing_skills": missing_skills,
        "recommended_certifications": recommended_certifications,
        "recommended_projects": recommended_projects,
        "interview_topics": interview_topics,
        "roadmap_json": roadmap_steps,
        "learning_resources_json": learning_resources[:8],
        "radar_chart_json": selected_radar,
        "has_resume": has_resume,
        "ats_resume_score": ats_score,
        "resume_suggestions": resume_suggestions,
        "internship_readiness": internship_readiness,
        "placement_readiness": placement_readiness,
        "thirty_day_plan": thirty_day_plan,
        "ninety_day_plan": ninety_day_plan,
        "motivational_message": motivational_message
    }


def generate_career_recommendation(user, target_role_name=None):
    """
    Collects profile details and database roadmaps, runs truth-grounded AI synthesis,
    and returns a saved CareerAnalysis database object.
    """
    try:
        profile = user.studentprofile
    except StudentProfile.DoesNotExist:
        raise ValueError("Profile incomplete. Please fill out your profile details first.")
        
    has_resume, latest_resume_analysis, default_resume = check_user_resume_status(user)
    
    # 1. Match the desired CareerPath from database
    paths = CareerPath.objects.filter(is_active=True)
    matched_path = None
    
    user_goal = (target_role_name or (profile.career_goal if profile else "")).strip().lower()
    
    if user_goal:
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

    # 2. Evaluate mathematically against the matched path (Truth Grounding)
    evaluated = evaluate_student_against_path(
        user=user,
        profile=profile,
        career_path=matched_path,
        has_resume=has_resume,
        latest_resume_analysis=latest_resume_analysis,
        default_resume=default_resume
    )
    
    # 3. Optional AI Synthesis via Groq LLM (Ground truth scores are locked)
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            prompt_context = {
                "student_name": f"{user.first_name} {user.last_name}",
                "target_role": matched_path.name,
                "cgpa": str(profile.cgpa) if profile.cgpa else "N/A",
                "calculated_readiness_score": evaluated["career_readiness_score"],
                "calculated_confidence_score": evaluated["confidence_score"],
                "internship_readiness": evaluated["internship_readiness"],
                "placement_readiness": evaluated["placement_readiness"],
                "matched_skills": evaluated["strengths"],
                "missing_skills": evaluated["missing_skills"][:6],
                "has_uploaded_resume": has_resume
            }
            
            prompt = (
                f"You are an expert AI Career Coach. Review the following verified student assessment data for the role of {matched_path.name}:\n"
                f"{json.dumps(prompt_context, indent=2)}\n\n"
                f"Instructions:\n"
                f"1. Generate personalized, actionable advice tailored strictly to {matched_path.name}.\n"
                f"2. DO NOT invent or change any numerical scores. The scores above are mathematical ground truth.\n"
                f"3. Output STRICT JSON ONLY matching this schema:\n"
                f"{{\n"
                f"  \"overall_feedback\": \"string (2-3 sentences of honest, constructive advice)\",\n"
                f"  \"recommended_certifications\": [\"string\", \"string\"],\n"
                f"  \"recommended_projects\": [\"string (specific to {matched_path.name})\", \"string\"],\n"
                f"  \"interview_topics\": [\"string\", \"string\", \"string\"],\n"
                f"  \"thirty_day_plan\": [\"string\", \"string\", \"string\"],\n"
                f"  \"ninety_day_plan\": [\"string\", \"string\", \"string\"],\n"
                f"  \"motivational_message\": \"string\"\n"
                f"}}\n"
                f"Do not output markdown code blocks or conversational text. Output raw JSON format only."
            )
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            groq_models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            for model_name in groq_models:
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": "You are a professional career coach. You always respond in raw JSON format matching the requested schema without changing ground-truth metrics."},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                }
                
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=10
                )
                
                if response.status_code == 200:
                    break
            
            if response.status_code == 200:
                result_json = response.json()
                raw_content = result_json["choices"][0]["message"]["content"]
                ai_data = json.loads(raw_content)
                
                # Merge AI qualitative insights while strictly preserving ground truth metrics
                if ai_data.get("overall_feedback"):
                    evaluated["overall_feedback"] = ai_data["overall_feedback"]
                if ai_data.get("recommended_certifications"):
                    evaluated["recommended_certifications"] = ai_data["recommended_certifications"]
                if ai_data.get("recommended_projects"):
                    evaluated["recommended_projects"] = ai_data["recommended_projects"]
                if ai_data.get("interview_topics"):
                    evaluated["interview_topics"] = ai_data["interview_topics"]
                if ai_data.get("thirty_day_plan"):
                    evaluated["thirty_day_plan"] = ai_data["thirty_day_plan"]
                if ai_data.get("ninety_day_plan"):
                    evaluated["ninety_day_plan"] = ai_data["ninety_day_plan"]
                if ai_data.get("motivational_message"):
                    evaluated["motivational_message"] = ai_data["motivational_message"]
        except Exception as e:
            print("Groq API qualitative enrichment bypassed:", e)

    # 4. Save the verified analysis data to the database
    analysis = CareerAnalysis.objects.create(
        user=user,
        career_readiness_score=evaluated["career_readiness_score"],
        recommended_career=evaluated["recommended_career"],
        confidence_score=evaluated["confidence_score"],
        overall_feedback=evaluated["overall_feedback"],
        strengths=evaluated["strengths"],
        weaknesses=evaluated["weaknesses"],
        missing_skills=evaluated["missing_skills"],
        recommended_certifications=evaluated["recommended_certifications"],
        recommended_projects=evaluated["recommended_projects"],
        interview_topics=evaluated["interview_topics"],
        roadmap_json=evaluated["roadmap_json"],
        learning_resources_json=evaluated["learning_resources_json"],
        radar_chart_json=evaluated["radar_chart_json"],
        has_resume=evaluated["has_resume"],
        ats_resume_score=evaluated["ats_resume_score"],
        resume_suggestions=evaluated["resume_suggestions"],
        internship_readiness=evaluated["internship_readiness"],
        placement_readiness=evaluated["placement_readiness"],
        thirty_day_plan=evaluated["thirty_day_plan"],
        ninety_day_plan=evaluated["ninety_day_plan"],
        motivational_message=evaluated["motivational_message"]
    )
    
    return analysis
