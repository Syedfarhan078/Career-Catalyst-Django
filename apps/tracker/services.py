import urllib.parse
import re


def parse_job_url(url_string):
    """
    Auto-detects company name and source platform from pasted job URLs.
    """
    if not url_string:
        return {"company_name": "", "platform": "Direct Company Page"}
        
    try:
        parsed = urllib.parse.urlparse(url_string)
        netloc = parsed.netloc.lower()
        path = parsed.path.strip('/')
        path_parts = path.split('/') if path else []
        
        # 1. Greenhouse (e.g. boards.greenhouse.io/zepto/jobs/123)
        if 'greenhouse.io' in netloc:
            if len(path_parts) >= 1:
                company = path_parts[0].replace('-', ' ').title()
                return {"company_name": company, "platform": "Greenhouse"}
                
        # 2. Lever (e.g. jobs.lever.co/stripe/abc-123)
        if 'lever.co' in netloc:
            if len(path_parts) >= 1:
                company = path_parts[0].replace('-', ' ').title()
                return {"company_name": company, "platform": "Lever"}
                
        # 3. Wellfound / AngelList (e.g. wellfound.com/company/swiggy/jobs)
        if 'wellfound.com' in netloc or 'angel.co' in netloc:
            if 'company' in path_parts:
                idx = path_parts.index('company')
                if idx + 1 < len(path_parts):
                    company = path_parts[idx + 1].replace('-', ' ').title()
                    return {"company_name": company, "platform": "Wellfound"}
                    
        # 4. LinkedIn (e.g. linkedin.com/jobs/view/...)
        if 'linkedin.com' in netloc:
            return {"company_name": "", "platform": "LinkedIn"}
            
        # 5. Internshala
        if 'internshala.com' in netloc:
            return {"company_name": "", "platform": "Internshala"}
            
        # 6. Generic domain extraction (e.g. careers.microsoft.com or airbnb.com/careers)
        domain_parts = netloc.split('.')
        filtered_parts = [p for p in domain_parts if p not in ['www', 'careers', 'jobs', 'boards', 'com', 'in', 'co', 'io', 'org', 'ai', 'tech', 'app']]
        if filtered_parts:
            company = filtered_parts[0].replace('-', ' ').title()
            return {"company_name": company, "platform": "Direct Career Page"}
            
    except Exception:
        pass
        
    return {"company_name": "", "platform": "Job Board"}


def generate_follow_up_email(application, user):
    """
    Generates a polite, highly effective follow-up email template tailored to the student and company.
    """
    student_name = f"{user.first_name} {user.last_name}".strip() or user.username
    company = application.company_name
    role = application.role_title
    days = application.days_since_applied
    
    # Check top skills if student has profile
    skills_mention = "my technical background and hands-on projects"
    if hasattr(user, 'studentprofile') and user.studentprofile.skills:
        clean_skills = [s.strip() for s in user.studentprofile.skills.replace('\n', ',').split(',') if s.strip()]
        if clean_skills:
            skills_mention = f"my practical skills in {', '.join(clean_skills[:2])}"

    if days >= 10:
        time_phrase = f"{days} days ago"
        tone_intro = "I hope you are having a productive week."
    elif days >= 5:
        time_phrase = f"{days} days ago"
        tone_intro = "I hope this email finds you well."
    else:
        time_phrase = "recently"
        tone_intro = "I hope your week is going well."

    subject = f"Following up: Application for {role} at {company} — {student_name}"
    
    body = (
        f"Hi {company} Hiring Team,\n\n"
        f"{tone_intro}\n\n"
        f"I submitted my application for the {role} position {time_phrase} and wanted to reiterate my enthusiasm for joining {company}.\n\n"
        f"Given {skills_mention}, I am confident I can make an immediate, positive impact on your engineering initiatives. I would welcome the opportunity to discuss how my background aligns with your current team goals.\n\n"
        f"Please let me know if you need any additional portfolio samples, code repositories, or reference materials.\n\n"
        f"Thank you for your time and consideration.\n\n"
        f"Best regards,\n"
        f"{student_name}\n"
    )
    
    # URL-encoded mailto link
    encoded_subject = urllib.parse.quote(subject)
    encoded_body = urllib.parse.quote(body)
    mailto_url = f"mailto:?subject={encoded_subject}&body={encoded_body}"
    
    return {
        "subject": subject,
        "body": body,
        "mailto_url": mailto_url,
        "company": company,
        "role": role,
        "days": days
    }
