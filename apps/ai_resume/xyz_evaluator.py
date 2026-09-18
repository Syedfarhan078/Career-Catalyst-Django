import re
from .nlp_engine import extract_skills_from_text

STRONG_ACTION_VERBS = {
    "architected", "engineered", "spearheaded", "built", "designed", "developed", "implemented",
    "optimized", "orchestrated", "streamlined", "reduced", "scaled", "accelerated", "automated",
    "benchmarked", "refactored", "integrated", "deployed", "led", "mentored", "authored", "formulated",
    "launched", "solved", "enhanced", "boosted", "standardized", "centralized", "containerized",
    "constructed", "devised", "established", "executed", "generated", "maximized", "minimized",
    "modernized", "pioneered", "re-engineered", "restructured", "transformed", "upgraded", "delivered",
    "migrated", "published", "secured", "configured", "maintained", "audited", "decreased", "increased"
}

WEAK_ACTION_VERBS = {
    "worked", "worked on", "helped", "helped with", "responsible for", "assisted", "assisted with",
    "handled", "did", "looked after", "participated", "participated in", "involved in", "contributed to",
    "tried", "tasked with", "assigned to", "made", "used", "utilized", "saw", "learned"
}

METRIC_PATTERNS = [
    r'\b\d+(\.\d+)?%',                                   # 45%, 99.9%
    r'\b\d+x\b',                                         # 10x, 2x
    r'(\$|₹|€|£)\s*\d+([,\.]\d+)?\s*(k|m|b|thousand|million|crore|lakh)?', # $50K, ₹10 Lakh
    r'\b\d+[\+]?\s*(users|clients|customers|requests|qps|rpm|records|endpoints|features|bugs|services|nodes|servers|models|pipelines|datasets)\b',
    r'\b(reduced|cut|saved|decreased)\b[^\.\,]{1,30}\b(\d+|half|latency|time|cost|downtime)',
    r'\b(increased|boosted|improved|accelerated)\b[^\.\,]{1,30}\b(\d+|throughput|speed|accuracy|retention|efficiency)'
]

def evaluate_bullet_point(bullet_text):
    """
    Evaluates a single resume bullet point against the Google XYZ formula:
    Accomplished [X], as measured by [Y], by doing [Z].
    """
    cleaned = bullet_text.strip()
    words = cleaned.split()
    first_two = " ".join(words[:2]).lower()
    first_word = words[0].lower().rstrip('ed').rstrip('s') if words else ""
    first_word_raw = words[0].lower().rstrip(':,.-') if words else ""
    
    # 1. Action Verb Evaluation
    verb_found = None
    verb_strength = "missing"
    
    if first_two in WEAK_ACTION_VERBS or first_word_raw in WEAK_ACTION_VERBS:
        verb_found = first_two if first_two in WEAK_ACTION_VERBS else first_word_raw
        verb_strength = "weak"
    elif first_word_raw in STRONG_ACTION_VERBS or any(w.lower() in STRONG_ACTION_VERBS for w in words[:3]):
        # Check first 3 words for strong verb
        for w in words[:3]:
            w_clean = w.lower().rstrip(':,.-')
            if w_clean in STRONG_ACTION_VERBS:
                verb_found = w_clean
                verb_strength = "strong"
                break
    else:
        # Check if first word is a verb in English past tense
        if first_word_raw.endswith('ed') or first_word_raw.endswith('ing'):
            verb_found = first_word_raw
            verb_strength = "moderate"
            
    # 2. Metric & Quantification Check
    metric_found = False
    metric_snippet = None
    for pat in METRIC_PATTERNS:
        match = re.search(pat, cleaned, re.IGNORECASE)
        if match:
            metric_found = True
            metric_snippet = match.group(0)
            break
            
    # 3. Technologies Check
    skills_data = extract_skills_from_text(cleaned)
    techs_found = skills_data.get("skills", [])
    has_tech = len(techs_found) > 0
    
    # 4. Score this bullet (0 - 100)
    score = 0
    if verb_strength == "strong":
        score += 35
    elif verb_strength == "moderate":
        score += 20
    elif verb_strength == "weak":
        score += 10
        
    if metric_found:
        score += 40
    if has_tech:
        score += 25
        
    score = min(100, score)
    
    # Feedback synthesis
    feedback_notes = []
    if verb_strength == "weak":
        feedback_notes.append(f"Replace passive verb '{verb_found}' with an assertive action verb (e.g., 'Engineered', 'Optimized', 'Orchestrated').")
    elif verb_strength == "missing":
        feedback_notes.append("Start with a powerful action verb in the past tense.")
        
    if not metric_found:
        feedback_notes.append("Add quantifiable metric or business outcome (e.g. 'reduced latency by 30%', 'serving 1,000+ users').")
        
    if not has_tech:
        feedback_notes.append("Explicitly state the tools or tech stack used to accomplish this task.")
        
    return {
        "bullet": cleaned,
        "score": score,
        "verb_strength": verb_strength,
        "verb": verb_found,
        "has_metric": metric_found,
        "metric_snippet": metric_snippet,
        "has_tech": has_tech,
        "techs": techs_found,
        "feedback": " ".join(feedback_notes) if feedback_notes else "Strong impact statement following the XYZ formula."
    }

def evaluate_achievement_strength(bullet_points):
    """
    Evaluates a collection of resume bullet points.
    Returns overall achievement strength score and detailed per-bullet breakdown.
    """
    if not bullet_points:
        return {
            "achievement_score": 0,
            "strong_bullets_count": 0,
            "quantified_bullets_count": 0,
            "total_bullets": 0,
            "bullet_reviews": []
        }
        
    bullet_reviews = []
    total_score = 0
    strong_verbs_count = 0
    quantified_count = 0
    
    for b in bullet_points:
        eval_result = evaluate_bullet_point(b)
        bullet_reviews.append(eval_result)
        total_score += eval_result["score"]
        if eval_result["verb_strength"] == "strong":
            strong_verbs_count += 1
        if eval_result["has_metric"]:
            quantified_count += 1
            
    num_bullets = len(bullet_points)
    avg_score = int(round(total_score / num_bullets)) if num_bullets > 0 else 0
    
    return {
        "achievement_score": avg_score,
        "strong_verbs_count": strong_verbs_count,
        "quantified_bullets_count": quantified_count,
        "total_bullets": num_bullets,
        "bullet_reviews": bullet_reviews
    }
