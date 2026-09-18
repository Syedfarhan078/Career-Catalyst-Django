import re
from .models import ResumeAnalysis, MissingSkill, ImprovementSuggestion
from .parser import segment_resume_sections, extract_bullet_points
from .nlp_engine import extract_skills_from_text, compute_tfidf_similarity, get_role_benchmark
from .xyz_evaluator import evaluate_achievement_strength
from .pii_sanitizer import sanitize_resume_text
from .ai_service import enhance_with_ai

def analyze_resume_data(text, target_role, user, resume=None, uploaded_file=None, job_description="", trigger_ai=False):
    """
    Coordinates the 5-layer Hybrid ATS Resume Analysis:
    Layer 1: Structured parsing & section segmentation
    Layer 2: Local skill taxonomy extraction & TF-IDF similarity
    Layer 3: Google XYZ achievement formula evaluator
    Layer 4: PII Sanitization
    Layer 5: Optional Semantic AI (Gemini / Groq)
    """
    text = text.strip()
    job_description = (job_description or "").strip()
    
    # --- LAYER 1: Structured Section Parsing & Bullet Extraction ---
    segmented = segment_resume_sections(text)
    sections = segmented["sections"]
    presence = segmented["presence"]
    bullets = extract_bullet_points(text)
    
    # --- LAYER 2: Skill Extraction & Taxonomy Matching ---
    skills_data = extract_skills_from_text(text)
    found_skills_list = skills_data["skills"]
    found_skills_set = set(s.lower() for s in found_skills_list)
    skills_by_category = skills_data["by_category"]
    
    role_bench = get_role_benchmark(target_role)
    required_skills = role_bench.get("required_skills", [])
    recommended_skills = role_bench.get("recommended_skills", [])
    role_keywords = role_bench.get("keywords", [])
    
    # If user provided a custom Job Description, extract skills and keywords directly from it too
    if job_description:
        jd_skills_data = extract_skills_from_text(job_description)
        jd_extracted_skills = jd_skills_data.get("skills", [])
        if jd_extracted_skills:
            required_skills = jd_extracted_skills
            
    # Calculate Skill Coverage
    matched_req_skills = [s for s in required_skills if s.lower() in found_skills_set]
    missing_req_skills = [s for s in required_skills if s.lower() not in found_skills_set]
    
    total_req = len(required_skills)
    skill_coverage_score = int(round((len(matched_req_skills) / total_req) * 100)) if total_req > 0 else 70
    
    # Calculate TF-IDF JD Match Score
    if job_description:
        jd_match_score, matching_kws = compute_tfidf_similarity(text, job_description)
    else:
        # Benchmark document generated from role taxonomy
        role_doc = f"{target_role}. Core skills: {' '.join(required_skills)}. Recommended: {' '.join(recommended_skills)}. Domain concepts: {' '.join(role_keywords)}"
        jd_match_score, matching_kws = compute_tfidf_similarity(text, role_doc)
        
    # Calculate Keyword Coverage
    benchmark_kws = list(set(role_keywords + matching_kws))
    matched_kws = [kw for kw in benchmark_kws if kw.lower() in text.lower()]
    total_kws_count = len(benchmark_kws)
    keyword_coverage_score = int(round((len(matched_kws) / total_kws_count) * 100)) if total_kws_count > 0 else 65
    
    # --- LAYER 3: Resume Completeness & Formatting ---
    # 5 sections (15 pts each = 75 pts) + contact info (25 pts)
    email_found = bool(re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text))
    phone_found = bool(re.search(r'(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}', text))
    links_found = any(k in text.lower() for k in ['linkedin.com', 'github.com', 'portfolio', 'http'])
    
    section_pts = sum(15 for sec in ["education", "experience", "projects", "skills", "certifications"] if presence.get(sec, False))
    contact_pts = (10 if email_found else 0) + (10 if phone_found else 0) + (5 if links_found else 0)
    completeness_score = min(100, section_pts + contact_pts)
    
    # --- LAYER 3: Google XYZ Achievement Evaluator ---
    xyz_results = evaluate_achievement_strength(bullets)
    achievement_score = xyz_results["achievement_score"]
    bullet_reviews = xyz_results["bullet_reviews"]
    
    # --- Overall Composite ATS Score ---
    overall_score = int(round(
        (jd_match_score * 0.25) +
        (skill_coverage_score * 0.25) +
        (keyword_coverage_score * 0.20) +
        (completeness_score * 0.15) +
        (achievement_score * 0.15)
    ))
    overall_score = max(5, min(100, overall_score))
    
    # --- LAYER 4: PII Sanitization ---
    pii_data = sanitize_resume_text(text)
    sanitized_text = pii_data["sanitized_text"]
    
    # Identify weak bullets needing improvement
    weak_bullets = [b["bullet"] for b in bullet_reviews if b["score"] < 60]
    
    # --- LAYER 5: Optional AI Enhancement ---
    ai_results = {}
    ai_enhanced = False
    if trigger_ai:
        ai_resp = enhance_with_ai(
            sanitized_text=sanitized_text,
            target_role=target_role,
            job_description=job_description,
            weak_bullets=weak_bullets,
            missing_skills=missing_req_skills
        )
        if ai_resp.get("ai_available", False):
            ai_results = ai_resp
            ai_enhanced = True
            
    # Structured Data Payload for Frontend
    structured_data = {
        "presence": presence,
        "contact_info": {
            "email": email_found,
            "phone": phone_found,
            "links": links_found
        },
        "found_skills": found_skills_list,
        "skills_by_category": skills_by_category,
        "matched_required_skills": matched_req_skills,
        "missing_required_skills": missing_req_skills,
        "recommended_skills": [s for s in recommended_skills if s.lower() not in found_skills_set],
        "matching_keywords": matching_kws[:15],
        "bullet_reviews": bullet_reviews,
        "strong_verbs_count": xyz_results["strong_verbs_count"],
        "quantified_bullets_count": xyz_results["quantified_bullets_count"],
        "total_bullets_count": xyz_results["total_bullets"],
        "word_count": len(text.split())
    }
    
    # Create / Update ResumeAnalysis Record
    analysis = ResumeAnalysis.objects.create(
        user=user,
        resume=resume,
        uploaded_file=uploaded_file,
        raw_text=text,
        target_role=target_role,
        job_description=job_description,
        jd_match_score=jd_match_score,
        skill_coverage_score=skill_coverage_score,
        keyword_coverage_score=keyword_coverage_score,
        completeness_score=completeness_score,
        achievement_score=achievement_score,
        overall_score=overall_score,
        ats_score=overall_score,
        grammar_score=achievement_score,
        keyword_score=keyword_coverage_score,
        skill_score=skill_coverage_score,
        structured_data=structured_data,
        pii_summary=pii_data["redaction_types"],
        ai_enhanced=ai_enhanced,
        ai_feedback=ai_results,
        feedback=f"Analyzed resume for '{target_role}'. Matched {len(matched_req_skills)}/{len(required_skills)} core skills, {len(matching_kws)} domain keywords, and evaluated {len(bullet_reviews)} achievement bullet points."
    )
    
    # Save Missing Skills
    for s in missing_req_skills[:10]:
        MissingSkill.objects.create(
            analysis=analysis,
            skill_name=s.capitalize(),
            importance="High" if s in required_skills[:4] else "Medium",
            recommendation=f"Add demonstrated experience or projects utilizing '{s.capitalize()}' to align with {target_role} expectations."
        )
        
    # Save Structured Improvement Suggestions
    if not email_found or not phone_found:
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Content",
            priority="High",
            description="Ensure both a professional email and phone number are clearly visible at the top of your resume."
        )
        
    if not presence.get("projects", False):
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Projects",
            priority="High",
            description="Add a dedicated 'Projects' section featuring 2-3 end-to-end technical applications."
        )
        
    if not presence.get("experience", False):
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Experience",
            priority="Medium",
            description="Include an internships, work experience, or open-source contributor section."
        )
        
    if xyz_results["quantified_bullets_count"] < (xyz_results["total_bullets"] / 2):
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Impact",
            priority="High",
            description="Quantify more accomplishment bullet points using measurable outcomes (e.g. '% improvements', 'latency reduced', 'number of users served')."
        )
        
    if missing_req_skills:
        missing_preview = ", ".join([s.capitalize() for s in missing_req_skills[:4]])
        ImprovementSuggestion.objects.create(
            analysis=analysis,
            category="Skills",
            priority="High",
            description=f"Incorporate missing core technical skills for this role: {missing_preview}."
        )
        
    return analysis
