from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages

from .models import ResumeAnalysis, MissingSkill, ImprovementSuggestion
from .forms import ResumeAnalysisForm
from .parser import parse_resume_file
from .services import analyze_resume_data
from .ai_service import enhance_with_ai
from .pii_sanitizer import sanitize_resume_text
from apps.resume.models import Resume

def resume_to_text(resume):
    """
    Serialize an internally built resume into a text representation for analysis.
    """
    text = f"{resume.user.first_name} {resume.user.last_name}\n"
    text += f"Email: {resume.user.email}\n"
    
    # Safely retrieve user's student profile for contact details
    profile = getattr(resume.user, 'studentprofile', None)
    if profile:
        if profile.phone_number:
            text += f"Phone: {profile.phone_number}\n"
        if profile.linkedin:
            text += f"LinkedIn: {profile.linkedin}\n"
        if profile.github:
            text += f"GitHub: {profile.github}\n"
        
    text += "\nEDUCATION\n"
    for edu in resume.educations.all():
        text += f"{edu.degree} in {edu.branch} - {edu.college} ({edu.start_year} - {edu.end_year})\n"
        if edu.cgpa:
            text += f"CGPA: {edu.cgpa}\n"
            
    text += "\nEXPERIENCE\n"
    for exp in resume.experiences.all():
        text += f"{exp.position} - {exp.company} ({exp.start_date} to {exp.end_date})\n"
        text += f"{exp.description}\n"
        
    text += "\nPROJECTS\n"
    for proj in resume.projects.all():
        text += f"{proj.title} - Tech: {proj.technologies_used}\n"
        text += f"{proj.description}\n"
        
    text += "\nSKILLS\n"
    skills = [s.name for s in resume.skills.all()]
    text += ", ".join(skills) + "\n"
    
    text += "\nCERTIFICATIONS\n"
    for cert in resume.certifications.all():
        text += f"{cert.name} - {cert.organization}\n"
        
    return text

@method_decorator(login_required, name='dispatch')
class AnalysisHistoryView(ListView):
    model = ResumeAnalysis
    template_name = 'ai_resume/history.html'
    context_object_name = 'analyses'

    def get_queryset(self):
        return ResumeAnalysis.objects.filter(user=self.request.user).select_related('resume').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'studentprofile', None)
        first_initial = (self.request.user.first_name[:1] if self.request.user.first_name else self.request.user.username[:1]).upper()
        last_initial = (self.request.user.last_name[:1] if self.request.user.last_name else "").upper()
        context['user_initials'] = f"{first_initial}{last_initial}" if last_initial else (self.request.user.username[:2].upper())
        context['target_career'] = profile.career_goal.strip() if (profile and profile.career_goal) else ""
        context['profile'] = profile
        return context

@method_decorator(login_required, name='dispatch')
class AnalyzeResumeView(CreateView):
    model = ResumeAnalysis
    form_class = ResumeAnalysisForm
    template_name = 'ai_resume/analyze.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'studentprofile', None)
        first_initial = (self.request.user.first_name[:1] if self.request.user.first_name else self.request.user.username[:1]).upper()
        last_initial = (self.request.user.last_name[:1] if self.request.user.last_name else "").upper()
        context['user_initials'] = f"{first_initial}{last_initial}" if last_initial else (self.request.user.username[:2].upper())
        context['target_career'] = profile.career_goal.strip() if (profile and profile.career_goal) else ""
        context['profile'] = profile
        context['user_resumes'] = Resume.objects.filter(user=self.request.user).order_by('-updated_at')
        return context

    def form_valid(self, form):
        resume = form.cleaned_data.get('resume')
        uploaded_file = form.cleaned_data.get('uploaded_file')
        raw_text_input = form.cleaned_data.get('raw_text_input', '')
        target_role = form.cleaned_data.get('target_role')
        job_description = form.cleaned_data.get('job_description', '')
        trigger_ai = bool(self.request.POST.get('trigger_ai'))
        
        raw_text = ""
        try:
            if raw_text_input and len(raw_text_input.strip()) > 10:
                raw_text = raw_text_input.strip()
            elif uploaded_file:
                raw_text = parse_resume_file(uploaded_file)
            elif resume:
                raw_text = resume_to_text(resume)
            else:
                messages.error(self.request, "Please provide a resume by uploading a file, selecting a saved resume, or pasting text.")
                return self.form_invalid(form)
                
            if not raw_text or len(raw_text.strip()) < 15:
                messages.error(self.request, "The parsed resume text is empty or contains only unreadable image data. If your PDF is a flat image or scanned document, please paste your resume text directly into the 'Paste Resume Text' box below.")
                return self.form_invalid(form)
            
            # Run the 5-layer Hybrid ATS Analysis
            analysis = analyze_resume_data(
                text=raw_text,
                target_role=target_role,
                user=self.request.user,
                resume=resume,
                uploaded_file=uploaded_file,
                job_description=job_description,
                trigger_ai=trigger_ai
            )
            
            messages.success(self.request, "Resume analyzed successfully with transparent ATS metrics!")
            return redirect('ai_resume:detail', pk=analysis.pk)
            
        except Exception as e:
            messages.error(self.request, f"Error analyzing resume: {str(e)}")
            return self.form_invalid(form)

@method_decorator(login_required, name='dispatch')
class AnalysisDetailView(DetailView):
    model = ResumeAnalysis
    template_name = 'ai_resume/detail.html'
    context_object_name = 'analysis'

    def get_queryset(self):
        return ResumeAnalysis.objects.filter(user=self.request.user).select_related('resume')
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        analysis = self.object
        
        # Consolidate suggestions queries into a single query grouped in memory
        all_suggestions = list(analysis.suggestions.all())
        context['all_suggestions'] = all_suggestions
        context['high_suggestions'] = [s for s in all_suggestions if s.priority == 'High']
        context['medium_suggestions'] = [s for s in all_suggestions if s.priority == 'Medium']
        context['low_suggestions'] = [s for s in all_suggestions if s.priority == 'Low']
        context['user_resume'] = analysis.resume or Resume.objects.filter(user=self.request.user).first()
        
        data = analysis.structured_data or {}
        context['bullet_reviews'] = data.get('bullet_reviews', [])
        context['found_skills'] = data.get('found_skills', [])
        context['matched_skills'] = data.get('matched_required_skills', [])
        context['missing_skills'] = data.get('missing_required_skills', [])
        context['recommended_skills'] = data.get('recommended_skills', [])
        context['matching_keywords'] = data.get('matching_keywords', [])
        context['contact_info'] = data.get('contact_info', {})
        context['presence'] = data.get('presence', {})
        context['ai_feedback'] = analysis.ai_feedback or {}
        context['pii_summary'] = analysis.pii_summary or {}
        
        profile = getattr(self.request.user, 'studentprofile', None)
        first_initial = (self.request.user.first_name[:1] if self.request.user.first_name else self.request.user.username[:1]).upper()
        last_initial = (self.request.user.last_name[:1] if self.request.user.last_name else "").upper()
        context['user_initials'] = f"{first_initial}{last_initial}" if last_initial else (self.request.user.username[:2].upper())
        context['target_career'] = profile.career_goal.strip() if (profile and profile.career_goal) else ""
        context['profile'] = profile
        
        return context

@login_required
@require_POST
def api_enhance_ai(request, pk):
    """
    AJAX endpoint: Enhances an existing analysis with the PII-Sanitized AI layer on-demand.
    """
    analysis = get_object_or_404(ResumeAnalysis, pk=pk, user=request.user)
    
    data = analysis.structured_data or {}
    bullet_reviews = data.get('bullet_reviews', [])
    weak_bullets = [b["bullet"] for b in bullet_reviews if b.get("score", 100) < 60]
    missing_skills = data.get('missing_required_skills', [])
    
    pii_data = sanitize_resume_text(analysis.raw_text)
    sanitized_text = pii_data["sanitized_text"]
    
    ai_resp = enhance_with_ai(
        sanitized_text=sanitized_text,
        target_role=analysis.target_role,
        job_description=analysis.job_description,
        weak_bullets=weak_bullets,
        missing_skills=missing_skills
    )
    
    if ai_resp.get("ai_available", False):
        analysis.ai_enhanced = True
        analysis.ai_feedback = ai_resp
        analysis.save(update_fields=['ai_enhanced', 'ai_feedback'])
        return JsonResponse({"status": "success", "ai_feedback": ai_resp})
    else:
        return JsonResponse({
            "status": "offline",
            "message": ai_resp.get("message", "AI provider is not configured. Local deterministic ATS report is active.")
        })
