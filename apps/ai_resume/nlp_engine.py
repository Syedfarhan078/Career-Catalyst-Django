import os
import re
import json
import math
from collections import Counter

# Standard English & JD boilerplate stop words
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can't",
    "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having",
    "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his",
    "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of",
    "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's",
    "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're",
    "you've", "your", "yours", "yourself", "yourselves", "will", "shall", "may", "might", "must", "can",
    # Job Description Boilerplate Stopwords
    "seeking", "skilled", "skills", "experience", "experienced", "years", "knowledge", "ability",
    "proficient", "proficiency", "strong", "understanding", "responsible", "qualifications",
    "requirements", "responsibilities", "preferred", "plus", "work", "working", "role", "job",
    "candidate", "ideal", "opportunity", "looking", "looking for", "including", "familiarity",
    "good", "excellent", "proven", "track record", "hands on", "hands-on", "demonstrated"
}

_TAXONOMY_CACHE = None

def load_taxonomy():
    """Load skill taxonomy JSON file with caching."""
    global _TAXONOMY_CACHE
    if _TAXONOMY_CACHE is not None:
        return _TAXONOMY_CACHE

    json_path = os.path.join(os.path.dirname(__file__), 'data', 'skills_taxonomy.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            _TAXONOMY_CACHE = json.load(f)
    except Exception as e:
        print(f"Error loading skill taxonomy: {e}")
        _TAXONOMY_CACHE = {"categories": {}, "aliases": {}, "roles": {}}
    return _TAXONOMY_CACHE

def tokenize_text(text, remove_stopwords=True):
    """
    Clean and tokenize text into words.
    Preserves programming tokens like c++, c#, .net, etc.
    """
    if not text:
        return []
    
    # Normalize special tokens
    normalized = text.lower()
    normalized = re.sub(r'c\+\+', 'cpp_token', normalized)
    normalized = re.sub(r'c\#', 'csharp_token', normalized)
    normalized = re.sub(r'\.net', 'dotnet_token', normalized)
    normalized = re.sub(r'node\.js', 'nodejs_token', normalized)
    normalized = re.sub(r'next\.js', 'nextjs_token', normalized)
    normalized = re.sub(r'vue\.js', 'vuejs_token', normalized)
    
    # Replace non-alphanumeric (except underscores and hyphens)
    cleaned = re.sub(r'[^a-z0-9_\-\s]', ' ', normalized)
    tokens = cleaned.split()
    
    restored = []
    for t in tokens:
        if t == 'cpp_token':
            restored.append('c++')
        elif t == 'csharp_token':
            restored.append('c#')
        elif t == 'dotnet_token':
            restored.append('.net')
        elif t == 'nodejs_token':
            restored.append('node.js')
        elif t == 'nextjs_token':
            restored.append('next.js')
        elif t == 'vuejs_token':
            restored.append('vue.js')
        else:
            if remove_stopwords and t in STOP_WORDS:
                continue
            if len(t) > 1 or t in ['c', 'r']:
                restored.append(t)
                
    return restored

def extract_skills_from_text(text):
    """
    Extract canonical technical & soft skills from text using taxonomy.
    Handles aliases and multi-word phrases.
    """
    taxonomy = load_taxonomy()
    categories = taxonomy.get("categories", {})
    aliases = taxonomy.get("aliases", {})
    
    text_lower = " " + text.lower() + " "
    clean_search_text = re.sub(r'[\r\n\t,;:()/]', ' ', text_lower)
    clean_search_text = re.sub(r'\s+', ' ', clean_search_text)
    
    found_skills = set()
    category_matches = {cat: [] for cat in categories}
    
    # 1. Match canonical skills
    for cat_name, skill_list in categories.items():
        for skill in skill_list:
            pattern = r'(?<![a-zA-Z0-9_\-])' + re.escape(skill) + r'(?![a-zA-Z0-9_\-])'
            if re.search(pattern, clean_search_text):
                found_skills.add(skill)
                category_matches[cat_name].append(skill)
                
    # 2. Match aliases and map to canonical
    for alias, canonical in aliases.items():
        pattern = r'(?<![a-zA-Z0-9_\-])' + re.escape(alias) + r'(?![a-zA-Z0-9_\-])'
        if re.search(pattern, clean_search_text):
            found_skills.add(canonical)
            for cat_name, skill_list in categories.items():
                if canonical in skill_list and canonical not in category_matches[cat_name]:
                    category_matches[cat_name].append(canonical)
                    
    return {
        "skills": sorted(list(found_skills)),
        "by_category": {k: sorted(v) for k, v in category_matches.items() if v}
    }

def compute_tfidf_similarity(doc1_text, doc2_text):
    """
    Compute mathematical TF-IDF relevance and Cosine Similarity.
    doc1: Resume text
    doc2: Job Description or Role Benchmark text
    Returns: similarity score in percentage (0 - 100) and top matching keywords.
    """
    if not doc1_text or not doc2_text:
        return 0, []
        
    tokens1 = tokenize_text(doc1_text)
    tokens2 = tokenize_text(doc2_text)
    
    if not tokens1 or not tokens2:
        return 0, []
        
    vocab = sorted(list(set(tokens1 + tokens2)))
    if not vocab:
        return 0, []
        
    tf1 = Counter(tokens1)
    tf2 = Counter(tokens2)
    
    len1 = len(tokens1)
    len2 = len(tokens2)
    
    df = {}
    for term in vocab:
        df_count = (1 if term in tf1 else 0) + (1 if term in tf2 else 0)
        df[term] = df_count
        
    vec1 = []
    vec2 = []
    top_matches = []
    
    for term in vocab:
        idf = math.log((1 + 2) / (1 + df[term])) + 1.0
        w1 = (tf1.get(term, 0) / len1) * idf
        w2 = (tf2.get(term, 0) / len2) * idf
        vec1.append(w1)
        vec2.append(w2)
        
        if w1 > 0 and w2 > 0:
            top_matches.append((term, w1 * w2))
            
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    
    cosine_sim = dot_product / (norm1 * norm2) if (norm1 > 0 and norm2 > 0) else 0.0
    
    # Calculate direct keyword coverage of doc2 (the JD requirements)
    jd_unique_terms = set(tokens2)
    resume_terms = set(tokens1)
    matched_jd_terms = [t for t in jd_unique_terms if t in resume_terms]
    term_coverage = len(matched_jd_terms) / len(jd_unique_terms) if jd_unique_terms else 0.0
    
    # Practical ATS match score blend: 30% cosine + 70% direct substantive keyword coverage
    blended_score = (0.30 * cosine_sim + 0.70 * term_coverage) * 100
    score_100 = min(100, max(0, int(round(blended_score))))
    
    top_matches.sort(key=lambda x: x[1], reverse=True)
    matching_keywords = [t[0] for t in top_matches[:25]]
    
    return score_100, matching_keywords

def get_role_benchmark(target_role):
    """Retrieve required skills and keywords for a target role from taxonomy."""
    taxonomy = load_taxonomy()
    roles = taxonomy.get("roles", {})
    
    role_key = target_role.lower().strip()
    if role_key in roles:
        return roles[role_key]
        
    for k, data in roles.items():
        if k in role_key or role_key in k:
            return data
            
    return roles.get("default", {
        "required_skills": ["python", "sql", "git", "communication"],
        "recommended_skills": ["docker", "rest api", "unit testing"],
        "keywords": ["development", "collaboration", "problem solving"]
    })
