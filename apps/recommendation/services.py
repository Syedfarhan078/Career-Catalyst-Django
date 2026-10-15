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


def normalize_url(url):
    """
    Normalizes a repository or verification URL for stable comparison.
    Strips protocol, www, trailing slashes, and .git suffix.
    """
    if not url:
        return ""
    u = str(url).strip().lower()
    u = re.sub(r'^https?://', '', u)
    u = re.sub(r'^www\.', '', u)
    u = re.sub(r'\.git$', '', u)
    return u.rstrip('/')


def resolve_skill_alias(token):
    """
    Normalizes a skill token using the platform's canonical skill taxonomy aliases if available.
    """
    norm = normalize_token(token)
    if not norm:
        return ""
    try:
        from apps.ai_resume.nlp_engine import load_taxonomy
        taxonomy = load_taxonomy()
        aliases = taxonomy.get("aliases", {})
        if norm in aliases:
            return normalize_token(aliases[norm])
    except Exception:
        pass
    return norm


def extract_taxonomy_skills(text):
    """
    Splits comma/newline separated skills and resolves aliases via taxonomy.
    """
    if not text:
        return []
    cleaned = str(text).replace('\n', ',')
    skills = []
    for raw in cleaned.split(','):
        c = raw.strip()
        if c:
            alias = resolve_skill_alias(c)
            skills.append(alias if alias else normalize_token(c))
    return skills


def are_projects_duplicate(p1, p2):
    """
    Conservatively checks if two project records represent the same underlying achievement.
    Tier 1: Stable repository or live demo URL match.
    Tier 2: Conservative normalized title match with corroborating technology overlap or date match.
    Never merges generic titles with disjoint technologies.
    """
    if p1 is p2:
        return True

    # Tier 1: URL Matching
    git1 = normalize_url(getattr(p1, 'github_url', ''))
    git2 = normalize_url(getattr(p2, 'github_url', ''))
    if git1 and git2 and git1 == git2:
        return True

    demo1 = normalize_url(getattr(p1, 'live_demo_url', ''))
    demo2 = normalize_url(getattr(p2, 'live_demo_url', ''))
    if demo1 and demo2 and demo1 == demo2:
        return True

    # Tier 2: Title matching with corroborating context
    title1 = normalize_token(getattr(p1, 'title', ''))
    title2 = normalize_token(getattr(p2, 'title', ''))
    if not title1 or title1 != title2:
        return False

    # Title is identical: check technologies overlap
    tech1 = set(extract_taxonomy_skills(getattr(p1, 'technologies_used', '')))
    tech2 = set(extract_taxonomy_skills(getattr(p2, 'technologies_used', '')))
    if tech1 and tech2:
        shared = tech1 & tech2
        union = tech1 | tech2
        # Jaccard overlap >= 0.4 or at least 2 common non-trivial technologies
        if len(shared) / len(union) >= 0.4 or len(shared) >= 2:
            return True
        # If both specified technologies and have zero/very low overlap, they are different projects with a generic title!
        return False

    # If technologies are missing on one side, check start_date if available
    d1 = getattr(p1, 'start_date', None)
    d2 = getattr(p2, 'start_date', None)
    if d1 and d2 and d1.year == d2.year and d1.month == d2.month:
        return True

    # If one side is a simple title copy without contradictory tech, treat as match if description or title is specific (>10 chars)
    if not tech1 or not tech2:
        if len(title1) >= 12:
            return True

    return False


def are_certifications_duplicate(c1, c2):
    """
    Conservatively checks if two certification records represent the same credential.
    Tier 1: Stable credential ID or verification URL match.
    Tier 2: Conservative normalized name AND organization match.
    """
    if c1 is c2:
        return True

    # Tier 1: Stable credential ID or URL match
    id1 = (getattr(c1, 'credential_id', '') or '').strip().lower()
    id2 = (getattr(c2, 'credential_id', '') or '').strip().lower()
    if id1 and id2 and id1 == id2:
        return True

    url1 = normalize_url(getattr(c1, 'credential_url', ''))
    url2 = normalize_url(getattr(c2, 'credential_url', ''))
    if url1 and url2 and url1 == url2:
        return True

    # Tier 2: Name + Organization match
    name1 = normalize_token(getattr(c1, 'name', ''))
    name2 = normalize_token(getattr(c2, 'name', ''))
    org1 = normalize_token(getattr(c1, 'organization', ''))
    org2 = normalize_token(getattr(c2, 'organization', ''))

    if name1 and name2 and name1 == name2 and org1 and org2 and org1 == org2:
        # Check issue date if both present (must not contradict by > 365 days)
        d1 = getattr(c1, 'issue_date', None)
        d2 = getattr(c2, 'issue_date', None)
        if d1 and d2 and abs((d1 - d2).days) > 365:
            return False
        return True

    return False


def get_unified_portfolio_diagnostics(user, default_resume=None):
    """
    Collects and deduplicates projects and certifications across:
    1. StudentProfile (permanent profile records)
    2. Default Resume (active document)
    3. Other user resumes (if present)
    
    Returns:
        (unique_projects_count: int, unique_certs_count: int, deduplicated_project_skills: list, deduplicated_cert_skills: list)
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return 0, 0, [], []

    unique_projects = []
    unique_certs = []

    # 1. Inspect StudentProfile records
    if hasattr(user, 'studentprofile'):
        try:
            for p in user.studentprofile.projects.all():
                if not any(are_projects_duplicate(p, existing) for existing in unique_projects):
                    unique_projects.append(p)
            for c in user.studentprofile.certifications.all():
                if not any(are_certifications_duplicate(c, existing) for existing in unique_certs):
                    unique_certs.append(c)
        except Exception:
            pass

    # 2. Inspect resumes (prioritize default resume)
    resumes_qs = user.resumes.all().order_by('-is_default', '-updated_at').prefetch_related('projects', 'certifications')
    for res in resumes_qs:
        for p in res.projects.all():
            if not any(are_projects_duplicate(p, existing) for existing in unique_projects):
                unique_projects.append(p)
        for c in res.certifications.all():
            if not any(are_certifications_duplicate(c, existing) for existing in unique_certs):
                unique_certs.append(c)

    project_skills = []
    for p in unique_projects:
        tech = getattr(p, 'technologies_used', None)
        if tech:
            project_skills.extend(extract_taxonomy_skills(tech))

    cert_skills = []
    for c in unique_certs:
        val = getattr(c, 'skills_validated', None)
        if val:
            cert_skills.extend(extract_taxonomy_skills(val))
        elif getattr(c, 'name', None):
            cert_skills.extend(extract_taxonomy_skills(c.name))

    return len(unique_projects), len(unique_certs), project_skills, cert_skills


def calculate_career_pillars(tier: str, skill_match_ratio: float, projects_count: int, 
                             experiences_count: int, certifications_count: int, 
                             is_enrolled: bool, cgpa_val: float) -> dict:
    """
    CANONICAL SCORING ENGINE:
    Preserves exact weights, tier criteria, and caps across all tiers.
    Shared by services.py (analysis generation) and views.py (dashboard pillar rendering).
    """
    if tier == 'product':
        max_skills, max_projects, max_academic, max_exp = 45, 30, 10, 15
        pillar_skills = round(skill_match_ratio * 45)
        pillar_projects = 30 if projects_count >= 3 else (22 if projects_count == 2 else (12 if projects_count == 1 else 0))
        pillar_academic = 10 if cgpa_val >= 8.5 else (8 if cgpa_val >= 7.5 else (6 if cgpa_val >= 6.5 else 4))
        p_exp = min(experiences_count * 6, 8)
        p_certs = min(certifications_count * 3, 4)
        p_enr = 3 if is_enrolled else 0
        pillar_exp = min(p_exp + p_certs + p_enr, 15)
        
    elif tier == 'service':
        max_skills, max_projects, max_academic, max_exp = 35, 20, 25, 20
        pillar_skills = round(skill_match_ratio * 35)
        pillar_projects = 20 if projects_count >= 2 else (14 if projects_count == 1 else 0)
        pillar_academic = 25 if cgpa_val >= 8.5 else (20 if cgpa_val >= 7.5 else (15 if cgpa_val >= 6.5 else 6))
        p_exp = min(experiences_count * 8, 10)
        p_certs = min(certifications_count * 6, 8)
        p_enr = 2 if is_enrolled else 0
        pillar_exp = min(p_exp + p_certs + p_enr, 20)
        
    else: # 'general'
        max_skills, max_projects, max_academic, max_exp = 40, 25, 15, 20
        pillar_skills = round(skill_match_ratio * 40)
        pillar_projects = 25 if projects_count >= 3 else (18 if projects_count == 2 else (10 if projects_count == 1 else 0))
        pillar_academic = 15 if cgpa_val >= 8.5 else (12 if cgpa_val >= 7.5 else (9 if cgpa_val >= 6.5 else 5))
        p_exp = min(experiences_count * 8, 10)
        p_certs = min(certifications_count * 4, 6)
        p_enr = 4 if is_enrolled else 0
        pillar_exp = min(p_exp + p_certs + p_enr, 20)

    total_score = min(pillar_skills + pillar_projects + pillar_academic + pillar_exp, 100)

    return {
        'pillar_skills': pillar_skills,
        'pillar_projects': pillar_projects,
        'pillar_academic': pillar_academic,
        'pillar_exp': pillar_exp,
        'p_exp': p_exp,
        'p_certs': p_certs,
        'p_enr': p_enr,
        'max_skills': max_skills,
        'max_projects': max_projects,
        'max_academic': max_academic,
        'max_exp': max_exp,
        'total_score': total_score,
    }


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
    Collects and normalizes all skill strings from profile, resume, and completed roadmap sources.
    Returns (raw_skills_list, normalized_tokens_set)
    """
    raw_skills = []
    
    # 1. Profile Skills (Manual / Self-Reported)
    if profile and profile.skills:
        clean_raw = profile.skills.replace('\n', ',')
        for s in clean_raw.split(','):
            clean_s = s.strip()
            if clean_s and clean_s not in raw_skills:
                raw_skills.append(clean_s)

    # 1b. Profile Projects & Certifications (Candidate-Reported Portfolio)
    if profile:
        try:
            for proj in profile.projects.all():
                if proj.technologies_used:
                    for t in proj.technologies_used.split(','):
                        clean_t = t.strip()
                        if clean_t and clean_t not in raw_skills:
                            raw_skills.append(clean_t)
            for cert in profile.certifications.all():
                if cert.skills_validated:
                    for s in cert.skills_validated.split(','):
                        clean_s = s.strip()
                        if clean_s and clean_s not in raw_skills:
                            raw_skills.append(clean_s)
                elif cert.name:
                    clean_name = cert.name.strip()
                    if clean_name and clean_name not in raw_skills:
                        raw_skills.append(clean_name)
        except Exception:
            pass
        
    # 2. Built Resume Skills
    if default_resume:
        for sk in default_resume.skills.all():
            if sk.name and sk.name not in raw_skills:
                raw_skills.append(sk.name)
        for proj in default_resume.projects.all():
            if proj.technologies_used:
                for t in proj.technologies_used.split(','):
                    clean_t = t.strip()
                    if clean_t and clean_t not in raw_skills:
                        raw_skills.append(clean_t)
        for cert in default_resume.certifications.all():
            if cert.name and cert.name not in raw_skills:
                raw_skills.append(cert.name)
                
    # 3. Uploaded ATS Scan Skills
    if latest_resume_analysis and latest_resume_analysis.raw_text:
        # Check for matching words in raw text
        pass

    # 4. Completed Roadmap Earned Skills
    if user and getattr(user, 'is_authenticated', False):
        try:
            from apps.roadmaps.services import get_user_earned_skills_set
            roadmap_earned_skills = get_user_earned_skills_set(user)
            for r_skill in roadmap_earned_skills:
                if r_skill and r_skill not in raw_skills:
                    raw_skills.append(r_skill)
        except Exception:
            pass

    normalized_tokens = set()
    for s in raw_skills:
        norm = normalize_token(s)
        if norm:
            normalized_tokens.add(norm)
            alias = resolve_skill_alias(norm)
            if alias:
                normalized_tokens.add(alias)
            # Add subwords for compound names
            for word in norm.split():
                if len(word) >= 3:
                    normalized_tokens.add(word)
                    alias_word = resolve_skill_alias(word)
                    if alias_word:
                        normalized_tokens.add(alias_word)

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


def evaluate_student_against_path(user, profile, career_path, has_resume, latest_resume_analysis, default_resume, company_tier='general'):
    """
    Performs deterministic, ground-truth evaluation of a student profile against a CareerPath,
    calibrated by the target company hiring tier (Product vs Service vs General).
    """
    raw_skills, student_tokens = extract_student_skills_set(user, profile, default_resume, latest_resume_analysis)
    
    # Query user's completed topic IDs to treat them as authoritative ground truth
    user_completed_topic_ids = set()
    if user and getattr(user, 'is_authenticated', False):
        from apps.roadmaps.models import TopicProgress
        user_completed_topic_ids = set(
            TopicProgress.objects.filter(
                user_roadmap__user=user,
                is_completed=True
            ).values_list('topic_id', flat=True)
        )
    
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
            
            is_matched = False
            if topic.id in user_completed_topic_ids:
                is_matched = True
            elif getattr(topic, 'skills_taught', None):
                from apps.roadmaps.services import get_topic_skills
                for t_skill in get_topic_skills(topic):
                    t_norm = normalize_token(t_skill)
                    if t_norm and t_norm in student_tokens:
                        is_matched = True
                        break
            
            if not is_matched:
                is_matched = topic_matches_skills(topic.title, student_tokens, raw_skills)
            
            if is_matched:
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
            clean_radar_name = clean_radar_name[:17] + '...'
        radar_dimensions.append({
            "name": clean_radar_name,
            "user_score": user_radar_score,
            "target_score": 10
        })

    if len(radar_dimensions) > 6:
        step_interval = len(radar_dimensions) // 6
        selected_radar = [radar_dimensions[i] for i in range(0, len(radar_dimensions), max(1, step_interval))][:6]
    else:
        selected_radar = radar_dimensions

    if not selected_radar:
        selected_radar = [
            {"name": "Fundamentals", "user_score": 0.0, "target_score": 10},
            {"name": "Core Principles", "user_score": 0.0, "target_score": 10},
            {"name": "Tooling & Frameworks", "user_score": 0.0, "target_score": 10},
            {"name": "Practical Execution", "user_score": 0.0, "target_score": 10},
            {"name": "Advanced Mastery", "user_score": 0.0, "target_score": 10}
        ]

    # --- TIER-CALIBRATED SCORING ENGINE ---
    skill_match_ratio = (total_matched_topics / total_path_topics) if total_path_topics > 0 else 0.0
    projects_count, certifications_count, _, _ = get_unified_portfolio_diagnostics(user, default_resume)
    experiences_count = default_resume.experiences.count() if default_resume else 0
    is_enrolled = UserRoadmap.objects.filter(user=user, career_path=career_path).exists()
    
    cgpa_val = 0.0
    if profile and profile.cgpa:
        try:
            cgpa_val = float(profile.cgpa)
        except (ValueError, TypeError):
            cgpa_val = 6.0

    pillars = calculate_career_pillars(
        tier=company_tier,
        skill_match_ratio=skill_match_ratio,
        projects_count=projects_count,
        experiences_count=experiences_count,
        certifications_count=certifications_count,
        is_enrolled=is_enrolled,
        cgpa_val=cgpa_val
    )
    pillar_skills = pillars['pillar_skills']
    pillar_projects = pillars['pillar_projects']
    pillar_academic = pillars['pillar_academic']
    pillar_experience_total = pillars['pillar_exp']
    career_readiness_score = pillars['total_score']

    
    # Calculate Role Alignment Confidence
    confidence_score = round((skill_match_ratio * 70) + ((career_readiness_score / 100) * 30))
    confidence_score = max(min(confidence_score, 100), 5)

    # Readiness Category
    if career_readiness_score >= 68:
        internship_readiness = "Ready"
    elif career_readiness_score >= 42:
        internship_readiness = "Almost Ready"
    else:
        internship_readiness = "Need Preparation"

    if career_readiness_score >= 76:
        placement_readiness = "Ready"
    elif career_readiness_score >= 54:
        placement_readiness = "Almost Ready"
    else:
        placement_readiness = "Need Preparation"

    # --- TIER-SPECIFIC STRENGTHS & GROWTH AREAS ---
    strengths = []
    weaknesses = []
    
    if company_tier == 'product':
        if projects_count >= 2:
            strengths.append(f"Strong practical portfolio with {projects_count} documented technical projects")
        if matched_skills:
            strengths.append(f"Demonstrated proficiency in {len(matched_skills)} core {career_path.name} tools & technologies")
        if not strengths:
            strengths.append(f"Clear goal orientation targeting high-impact {career_path.name} engineering")
            
        if projects_count < 2:
            weaknesses.append("Product Tier Gap: Need at least 2 full-stack/capstone deployed projects with live URLs")
        if missing_skills:
            weaknesses.append(f"Advanced Stack Gap: Missing {len(missing_skills)} target concepts (e.g. {', '.join(missing_skills[:3])})")
        weaknesses.append("System Design & Problem Solving: Practice scalable architecture and timed coding challenges")
        
        interview_topics = [
            "Data Structures, Algorithms & LeetCode Coding Patterns",
            "Low-Level & High-Level System Design (Scalability, Caching, DB Sharding)",
            "Live Technical Problem Solving & Behavioral STAR Framework"
        ]
        thirty_day_plan = [
            f"Build and deploy an end-to-end {career_path.name} capstone project with Docker & CI/CD.",
            "Solve 30+ medium-level Data Structures & Algorithm challenges.",
            "Master system design principles: caching, database indexing, and REST APIs."
        ]
        ninety_day_plan = [
            "Contribute to an open-source project or publish a production-grade live web app.",
            "Complete 3 full-length proctored mock technical interviews in the Sandbox.",
            "Target early-stage tech startups and top product company job postings."
        ]
        
    elif company_tier == 'service':
        if cgpa_val >= 7.0:
            strengths.append(f"Strong academic eligibility with a {cgpa_val} CGPA (comfortably above campus cutoffs)")
        if matched_skills:
            strengths.append(f"Foundational understanding of {', '.join(matched_skills[:3])}")
        if not strengths:
            strengths.append("Verified student profile enrolled in university degree")
            
        if cgpa_val < 6.5:
            weaknesses.append(f"Academic Filter: {cgpa_val} CGPA is below some enterprise 65% campus cutoff filters")
        if missing_skills:
            weaknesses.append(f"Core CS Syllabus: Ensure mastery of {', '.join(missing_skills[:3])}")
        weaknesses.append("Aptitude & Communication: Prepare for quantitative aptitude and logical reasoning rounds")
        
        interview_topics = [
            "Core CS Fundamentals (OOPs 4 Pillars, DBMS SQL Normalization, OS)",
            "Quantitative, Verbal & Logical Aptitude Assessments",
            "Technical HR, Group Discussion & Professional Communication"
        ]
        thirty_day_plan = [
            f"Master core OOPs, DBMS SQL queries, and basic {career_path.name} fundamentals.",
            "Practice 50+ quantitative and logical aptitude practice tests.",
            "Ensure standard single-column ATS resume formatting."
        ]
        ninety_day_plan = [
            "Complete a recognized industry certification in your core programming language.",
            "Practice mock HR communication rounds and technical interview questions.",
            "Apply to mass-hiring enterprise drives (TCS NQT, Infosys InfyTQ, Accenture, Wipro)."
        ]
        
    else:
        if matched_skills:
            strengths.append(f"Demonstrated proficiency in {len(matched_skills)} {career_path.name} topics: {', '.join(matched_skills[:3])}")
        if cgpa_val >= 7.5:
            strengths.append(f"Solid academic track record ({cgpa_val} CGPA)")
        if projects_count > 0:
            strengths.append(f"{projects_count} portfolio project(s) documented")
        if not strengths:
            strengths.append(f"Goal-oriented progress targeting {career_path.name}")
            
        if missing_skills:
            weaknesses.append(f"Syllabus Gap: Missing {len(missing_skills)} key {career_path.name} topics ({', '.join(missing_skills[:3])})")
        if projects_count == 0:
            weaknesses.append("Portfolio Gap: Build practical role-specific projects")
        if not weaknesses:
            weaknesses.append("Refine technical interview readiness and portfolio polish")
            
        interview_topics = [
            f"{career_path.name} Core Methodologies & Best Practices",
            "Problem Solving & Architecture Fundamentals",
            "Behavioral & Practical Execution Scenarios"
        ]
        thirty_day_plan = [
            f"Enroll in the {career_path.name} roadmap and complete Weeks 1 to 4.",
            f"Master core topics: {', '.join(missing_skills[:3]) if missing_skills else 'Fundamentals'}.",
            "Set up a dedicated GitHub repository for role projects."
        ]
        ninety_day_plan = [
            f"Build a comprehensive portfolio project applying {career_path.name} best practices.",
            "Achieve an 80%+ ATS resume score and begin active applications.",
            "Participate in proctored coding assessments on the platform."
        ]

    # ATS Resume Score
    if has_resume and latest_resume_analysis and latest_resume_analysis.ats_score:
        ats_score = latest_resume_analysis.ats_score
    elif has_resume and default_resume:
        ats_score = min((projects_count * 15) + (experiences_count * 20) + (certifications_count * 10) + 40, 95)
    else:
        ats_score = None

    if has_resume and latest_resume_analysis:
        resume_suggestions = [s.description for s in latest_resume_analysis.suggestions.all()[:3]]
    elif has_resume:
        resume_suggestions = [
            f"Tailor project descriptions to highlight {career_path.name} tools and outcomes.",
            "Include quantifiable metrics (e.g. percentage improvements, user counts, latency drops).",
            "Ensure standard single-column formatting for optimal ATS scanner parsing."
        ]
    else:
        resume_suggestions = [
            f"Upload your resume to the ATS Analyzer to compare keyword matches against {career_path.name}.",
            "Structure your resume with standard sections: Education, Projects, Skills, and Experience.",
            f"Include relevant keywords from the {career_path.name} roadmap in your skills section."
        ]

    tier_label = "Product & Startup" if company_tier == 'product' else ("Enterprise Services" if company_tier == 'service' else "General Industry")
    feedback = f"Calibrated for {tier_label} hiring standards: You currently show a {career_readiness_score}% readiness score for {career_path.name}."
    motivational_message = f"Stay focused! Tailoring your preparation to {tier_label} requirements maximizes your conversion rate."

    recommended_certifications = [
        f"Certified {career_path.name} Practitioner",
        f"Cloud & Systems Specialist ({career_path.name})"
    ]
    recommended_projects = [
        f"Full-lifecycle capstone project demonstrating {career_path.name} core competencies",
        f"Production implementation using {', '.join(missing_skills[:2]) if missing_skills else 'target stack'}"
    ]

    return {
        "career_readiness_score": career_readiness_score,
        "recommended_career": career_path.name,
        "target_company_tier": company_tier,
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


def generate_career_recommendation(user, target_role_name=None, company_tier='general'):
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

    # 2. Evaluate mathematically against the matched path (Truth Grounding with Tier Calibration)
    evaluated = evaluate_student_against_path(
        user=user,
        profile=profile,
        career_path=matched_path,
        has_resume=has_resume,
        latest_resume_analysis=latest_resume_analysis,
        default_resume=default_resume,
        company_tier=company_tier
    )
    
    # 3. Optional AI Synthesis via Groq LLM (Ground truth scores are locked)
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            prompt_context = {
                "student_name": f"{user.first_name} {user.last_name}",
                "target_role": matched_path.name,
                "target_company_tier": company_tier,
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
                f"You are an expert AI Career Coach. Review the following verified student assessment data for {matched_path.name}, "
                f"specifically calibrated for the hiring tier: {company_tier.upper()} COMPANIES.\n"
                f"{json.dumps(prompt_context, indent=2)}\n\n"
                f"Instructions:\n"
                f"1. Generate personalized, actionable advice tailored strictly to {matched_path.name} and {company_tier} company requirements.\n"
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
            
            groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            response = None
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
                
                try:
                    response = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=5
                    )
                    if response.status_code == 200:
                        break
                    # If invalid API key, no need to retry other models
                    if response.status_code in (401, 403):
                        break
                except requests.RequestException:
                    continue
            
            if response and response.status_code == 200:
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
        target_company_tier=evaluated.get("target_company_tier", company_tier),
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



def enroll_and_sync_roadmap(user, career_path_identifier, matched_topics_list=None):
    """
    Enrolls the user in a CareerPath and automatically pre-completes
    any topics that match their verified skills from their profile/resume.
    """
    from django.utils import timezone
    from apps.roadmaps.models import CareerPath, Topic, UserRoadmap, TopicProgress
    
    if isinstance(career_path_identifier, CareerPath):
        career_path = career_path_identifier
    elif isinstance(career_path_identifier, int):
        career_path = CareerPath.objects.get(id=career_path_identifier)
    else:
        identifier_str = str(career_path_identifier).strip()
        career_path = (
            CareerPath.objects.filter(slug__iexact=identifier_str).first() or
            CareerPath.objects.filter(name__iexact=identifier_str).first() or
            CareerPath.objects.filter(name__icontains=identifier_str).first() or
            CareerPath.objects.filter(is_active=True).first()
        )
    
    if not career_path:
        raise ValueError("Target career pathway not found.")

    # 1. Get or create UserRoadmap enrollment
    user_roadmap, created = UserRoadmap.objects.get_or_create(
        user=user,
        career_path=career_path,
        defaults={"is_active": True}
    )
    if not user_roadmap.is_active:
        user_roadmap.is_active = True
        user_roadmap.save()

    # 2. Gather student skill tokens
    try:
        profile = user.studentprofile
    except Exception:
        profile = None
        
    has_resume, latest_resume_analysis, default_resume = check_user_resume_status(user)
    raw_skills, student_tokens = extract_student_skills_set(user, profile, default_resume, latest_resume_analysis)
    
    if matched_topics_list:
        raw_skills.extend(list(matched_topics_list))
        for t in matched_topics_list:
            norm_t = normalize_token(t)
            if norm_t:
                student_tokens.add(norm_t)

    # 3. Process all topics for this roadmap
    all_topics = Topic.objects.filter(milestone__career_path=career_path).select_related('milestone')
    synced_topics_count = 0

    for topic in all_topics:
        is_matched = False
        if matched_topics_list and topic.title in matched_topics_list:
            is_matched = True
        elif getattr(topic, 'skills_taught', None):
            from apps.roadmaps.services import get_topic_skills
            for t_skill in get_topic_skills(topic):
                t_norm = normalize_token(t_skill)
                if t_norm and t_norm in student_tokens:
                    is_matched = True
                    break
        if not is_matched and topic_matches_skills(topic.title, student_tokens, raw_skills):
            is_matched = True

        progress_obj, prog_created = TopicProgress.objects.get_or_create(
            user_roadmap=user_roadmap,
            topic=topic,
            defaults={
                "is_completed": is_matched,
                "completed_at": timezone.now() if is_matched else None
            }
        )

        if not prog_created and is_matched and not progress_obj.is_completed:
            progress_obj.is_completed = True
            progress_obj.completed_at = timezone.now()
            progress_obj.save()
            synced_topics_count += 1
        elif prog_created and is_matched:
            synced_topics_count += 1

    # 4. Find first incomplete milestone week
    milestones = career_path.milestones.prefetch_related('topics').order_by('week_number')
    first_incomplete_week = 1
    first_incomplete_title = ""

    for ms in milestones:
        ms_topic_ids = list(ms.topics.values_list('id', flat=True))
        completed_in_ms = TopicProgress.objects.filter(
            user_roadmap=user_roadmap,
            topic_id__in=ms_topic_ids,
            is_completed=True
        ).count()
        if completed_in_ms < len(ms_topic_ids):
            first_incomplete_week = ms.week_number
            first_incomplete_title = ms.title
            break

    return {
        "user_roadmap": user_roadmap,
        "career_path": career_path,
        "synced_topics_count": synced_topics_count,
        "progress_percentage": user_roadmap.progress_percentage(),
        "completed_count": user_roadmap.completed_count(),
        "total_topics": career_path.total_topics(),
        "first_incomplete_week": first_incomplete_week,
        "first_incomplete_title": first_incomplete_title
    }

