import re

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)

# Support international, US, and common phone formats with spaces, dashes, dots, and parentheses
PHONE_REGEX = re.compile(
    r'(?:(?:\+|00)\d{1,3}[\s.-]?)?'  # Optional international prefix (+1, +91, 0044, etc.)
    r'(?:\(?\d{2,5}\)?[\s.-]?)?'      # Optional area/STD code
    r'\b\d{3,5}[\s.-]?\d{4,5}\b',    # Main number digits
    re.IGNORECASE
)

# Support linkedin URLs with or without http/https/www
LINKEDIN_REGEX = re.compile(r'(?:https?:\/\/)?(?:www\.)?linkedin\.com\/(?:in|pub|profile)\/[\w\-\/]+', re.IGNORECASE)

# Support github URLs with or without http/https/www
GITHUB_REGEX = re.compile(r'(?:https?:\/\/)?(?:www\.)?github\.com\/[\w\-\/]+', re.IGNORECASE)

# Generic web URLs and portfolio links (prevent matching degree abbreviations like B.Tech)
URL_REGEX = re.compile(r'(?:https?:\/\/|www\.)[^\s,;]+|\b[a-zA-Z0-9_\-]+\.(?:github\.io|gitlab\.io|vercel\.app|netlify\.app)\b[^\s,;]*', re.IGNORECASE)

# Physical Address & Location Patterns (US city/state/zip, street addresses, Indian pincodes)
LOCATION_PATTERNS = [
    re.compile(r'\b\d{1,5}\s+[A-Za-z0-9\.,\s]{2,30}\s+(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Drive|Dr\.?|Lane|Ln\.?|Court|Ct\.?|Way|Suite|Apt|Apartment)\b', re.IGNORECASE),
    re.compile(r'\b[A-Z][a-zA-Z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b'), # e.g. Austin, TX 78701
    re.compile(r'\b[A-Za-z\s]+,\s*[A-Za-z\s]+\s*-\s*\d{6}\b'),         # e.g. Bangalore, Karnataka - 560001
    re.compile(r'\b(?:Pin|Postal|Zip)\s*(?:Code)?[:\s\-]*\d{5,6}\b', re.IGNORECASE),
]

# Targeted Institution Patterns (strictly single line, no newlines)
INSTITUTION_PATTERNS = [
    re.compile(r'\b(?:University\s+of\s+[A-Za-z ]+|[A-Z][a-zA-Z ]{1,35}\s+(?:University|College|Institute\s+of\s+Technology|Polytechnic|Academy))\b'),
]

def sanitize_resume_text(raw_text):
    """
    Scrubs all Personally Identifiable Information (PII) before external AI processing.
    Replaces sensitive elements with anonymous structured tokens.
    """
    if not raw_text:
        return {
            "sanitized_text": "",
            "redacted_count": 0,
            "redaction_types": {}
        }
        
    sanitized = raw_text
    redaction_counts = {
        "candidate_name": 0,
        "email": 0,
        "phone": 0,
        "linkedin": 0,
        "github": 0,
        "urls": 0,
        "location": 0,
        "institutions": 0
    }
    
    # 1. Redact Candidate Name (Usually the first non-empty header line)
    lines = sanitized.split('\n')
    for idx, line in enumerate(lines):
        clean_l = line.strip()
        if clean_l and len(clean_l.split()) <= 4 and not any(kw in clean_l.lower() for kw in ['resume', 'curriculum', 'page', 'summary', 'developer', 'engineer', 'analyst', 'manager', 'profile', 'contact', 'education', 'experience']):
            lines[idx] = "[CANDIDATE_NAME]"
            redaction_counts["candidate_name"] += 1
            break
    sanitized = "\n".join(lines)
    
    # 2. Redact Email (before URLs/general regex)
    emails_found = len(EMAIL_REGEX.findall(sanitized))
    if emails_found:
        sanitized = EMAIL_REGEX.sub('[EMAIL_REDACTED]', sanitized)
        redaction_counts["email"] = emails_found
        
    # 3. Redact Specific Profile Links (LinkedIn, GitHub)
    linkedin_found = len(LINKEDIN_REGEX.findall(sanitized))
    if linkedin_found:
        sanitized = LINKEDIN_REGEX.sub('[LINKEDIN_URL]', sanitized)
        redaction_counts["linkedin"] = linkedin_found
        
    github_found = len(GITHUB_REGEX.findall(sanitized))
    if github_found:
        sanitized = GITHUB_REGEX.sub('[GITHUB_URL]', sanitized)
        redaction_counts["github"] = github_found
        
    # 4. Redact Generic URLs & Portfolios
    urls_found = len(URL_REGEX.findall(sanitized))
    if urls_found:
        sanitized = URL_REGEX.sub('[LINK_REDACTED]', sanitized)
        redaction_counts["urls"] = urls_found
        
    # 5. Redact Locations / Addresses
    for loc_pat in LOCATION_PATTERNS:
        loc_matches = len(loc_pat.findall(sanitized))
        if loc_matches:
            sanitized = loc_pat.sub('[LOCATION_REDACTED]', sanitized)
            redaction_counts["location"] += loc_matches

    # 6. Redact Phone Numbers
    phones_found = len(PHONE_REGEX.findall(sanitized))
    if phones_found:
        sanitized = PHONE_REGEX.sub('[PHONE_REDACTED]', sanitized)
        redaction_counts["phone"] = phones_found
        
    # 7. Redact Institutions
    for pat in INSTITUTION_PATTERNS:
        inst_matches = len(pat.findall(sanitized))
        if inst_matches:
            sanitized = pat.sub('[INSTITUTION_REDACTED]', sanitized)
            redaction_counts["institutions"] += inst_matches
            
    total_redacted = sum(redaction_counts.values())
    
    return {
        "sanitized_text": sanitized,
        "redacted_count": total_redacted,
        "redaction_types": {k: v for k, v in redaction_counts.items() if v > 0}
    }
