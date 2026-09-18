import os
import json
import requests
from django.conf import settings
from .pii_sanitizer import sanitize_resume_text

def get_groq_api_key():
    """Retrieve Groq API key from settings or environment."""
    try:
        return getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY', '')
    except Exception:
        return os.getenv('GROQ_API_KEY', '')

def get_gemini_api_key():
    """Retrieve Gemini API key from settings or environment."""
    try:
        return getattr(settings, 'GEMINI_API_KEY', None) or os.getenv('GEMINI_API_KEY', '')
    except Exception:
        return os.getenv('GEMINI_API_KEY', '')

GROQ_CANDIDATE_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

def enhance_with_ai(sanitized_text, target_role, job_description="", weak_bullets=None, missing_skills=None):
    """
    Optional semantic AI enhancement using Groq or Gemini free tier.
    Requires sanitized text only (Zero PII sent).
    Returns structured recommendations and bullet rewrites.
    """
    groq_key = get_groq_api_key()
    gemini_key = get_gemini_api_key()
    
    if not groq_key and not gemini_key:
        return {
            "ai_available": False,
            "status": "offline_mode",
            "message": "Local Deterministic Mode Active (No GROQ_API_KEY or GEMINI_API_KEY found). Add GROQ_API_KEY to .env for AI bullet point rewrites."
        }
        
    weak_bullets = weak_bullets or []
    missing_skills = missing_skills or []
    
    system_prompt = (
        "You are an expert technical resume coach and principal engineering recruiter. "
        "Review the candidate's anonymized bullet points and provide actionable, high-impact improvements. "
        "Never invent fake technical experiences or credentials; preserve the core facts while boosting clarity, strong action verbs, and quantifiable impact. "
        "Respond ONLY with valid JSON matching this exact structure:\n"
        "{\n"
        '  "role_alignment_insight": "2-3 concise sentences explaining how the candidate fits this target role and what specific technical gap to bridge.",\n'
        '  "bullet_rewrites": [\n'
        '    {\n'
        '      "original": "exact original bullet",\n'
        '      "improved": "rewritten high-impact bullet following the Google XYZ formula",\n'
        '      "rationale": "why this rewrite is more impactful for recruiters"\n'
        '    }\n'
        '  ],\n'
        '  "top_strengths": ["strength 1", "strength 2"],\n'
        '  "key_recommendations": ["recommendation 1", "recommendation 2"]\n'
        "}"
    )
    
    user_payload = {
        "target_role": target_role,
        "job_description_snippet": job_description[:800] if job_description else "N/A",
        "missing_skills_to_address": missing_skills[:6],
        "bullet_points_needing_improvement": weak_bullets[:5]
    }
    
    user_content = f"Target Role: {target_role}\nJob Details: {json.dumps(user_payload, indent=2)}\n\nAnonymized Resume Snippet:\n{sanitized_text[:1500]}"
    
    # 1. Try Groq API models
    if groq_key:
        for model_name in GROQ_CANDIDATE_MODELS:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    text_response = data['choices'][0]['message']['content']
                    parsed = json.loads(text_response)
                    parsed["ai_available"] = True
                    parsed["provider"] = f"Groq ({model_name})"
                    return parsed
                elif resp.status_code == 404:
                    # Model not available on this key, try next model
                    continue
            except Exception as e:
                print(f"Groq API model {model_name} notice: {e}")
                continue
                
    # 2. Try Gemini API as alternative
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": system_prompt + "\n\n" + user_content}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "responseMimeType": "application/json"
                }
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                text_response = data['candidates'][0]['content']['parts'][0]['text']
                parsed = json.loads(text_response)
                parsed["ai_available"] = True
                parsed["provider"] = "Google Gemini 1.5 Flash"
                return parsed
        except Exception as e:
            print(f"Gemini API request failed: {e}")
            
    # Fallback if calls failed or timed out
    return {
        "ai_available": False,
        "status": "offline_mode",
        "message": "AI API connection timed out or is unavailable. Local ATS deterministic report generated successfully."
    }
