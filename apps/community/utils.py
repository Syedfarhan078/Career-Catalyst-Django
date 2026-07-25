import logging
from django.contrib import messages

logger = logging.getLogger(__name__)

def simulate_notification(user, subject, message):
    """
    Simulates sending an email or in-app push notification by writing to server logs
    and terminal output, satisfying the notification specification locally without external APIs.
    """
    alert_text = f"[NOTIFICATION ALERT] To: {user.username} ({user.email}) | Subject: {subject} | Body: {message}"
    print(alert_text)
    logger.info(alert_text)


def calculate_mentor_match_score(student_profile, mentor_profile):
    """
    Calculates a match percentage score (0-100) between a student and a mentor based on:
    - 40% Skill Match
    - 30% Domain Match
    - 20% Experience Match
    - 10% Rating Match
    """
    # 1. Skill Match (40% Weight)
    student_skills = student_profile.get_skills_list if student_profile else []
    mentor_skills = mentor_profile.get_skills_list()
    
    if not student_skills:
        # Default to neutral if student has no listed skills
        skill_score = 100.0
    else:
        matched_skills = 0
        mentor_skills_lower = [s.lower() for s in mentor_skills]
        for skill in student_skills:
            if skill.lower() in mentor_skills_lower:
                matched_skills += 1
        skill_score = (matched_skills / len(student_skills)) * 100.0
    
    # 2. Domain Match (30% Weight)
    student_domain = student_profile.preferred_domain.strip().lower() if student_profile and student_profile.preferred_domain else ""
    mentor_domains = [d.lower() for d in mentor_profile.get_domains_list()]
    
    if not student_domain:
        domain_score = 100.0
    elif student_domain in mentor_domains:
        domain_score = 100.0
    else:
        # Check partial substring match
        domain_score = 0.0
        for md in mentor_domains:
            if student_domain in md or md in student_domain:
                domain_score = 50.0
                break

    # 3. Experience Match (20% Weight)
    exp = mentor_profile.experience_years
    if exp >= 10:
        exp_score = 100.0
    elif exp >= 6:
        exp_score = 90.0
    elif exp >= 3:
        exp_score = 70.0
    else:
        exp_score = 40.0

    # 4. Rating Match (10% Weight)
    rating = float(mentor_profile.rating)
    rating_score = (rating / 5.0) * 100.0

    # Calculate overall weighted score
    overall_score = (0.40 * skill_score) + (0.30 * domain_score) + (0.20 * exp_score) + (0.10 * rating_score)
    return round(overall_score, 1)
