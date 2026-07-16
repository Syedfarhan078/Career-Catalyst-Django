from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView
from django.urls import reverse_lazy
from django.contrib import messages

from .models import ResumeAnalysis, MissingSkill, ImprovementSuggestion
from .forms import ResumeAnalysisForm
from .parser import parse_resume_file
from .services import analyze_resume_data

def resume_to_text(resume):
    """
    Serialize an internally built resume into a text representation for analysis.
    """
    text = f"{resume.user.first_name} {resume.user.last_name}\n"
    text += f"Email: {resume.user.email}\n"
    
    # Try to grab additional details from student profile if available
    try:
        profile = resume.user.profile
        if profile.phone_number:
            text += f"Phone: {profile.phone_number}\n"
        if profile.linkedin:
            text += f"LinkedIn: {profile.linkedin}\n"
        if profile.github:
            text += f"GitHub: {profile.github}\n"
    except AttributeError:
        pass
        
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
        return ResumeAnalysis.objects.filter(user=self.request.user)

@method_decorator(login_required, name='dispatch')
class AnalyzeResumeView(CreateView):
    model = ResumeAnalysis
    form_class = ResumeAnalysisForm
    template_name = 'ai_resume/analyze.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        analysis_form = form.save(commit=False)
        analysis_form.user = self.request.user
        
        resume = form.cleaned_data.get('resume')
        uploaded_file = form.cleaned_data.get('uploaded_file')
        target_role = form.cleaned_data.get('target_role')
        
        raw_text = ""
        
        try:
            if resume:
                raw_text = resume_to_text(resume)
            elif uploaded_file:
                raw_text = parse_resume_file(uploaded_file)
            else:
                messages.error(self.request, "Invalid input. Please provide a resume.")
                return self.form_invalid(form)
                
            if not raw_text.strip():
                messages.error(self.request, "The parsed resume text is empty. Ensure the file is not empty or image-based.")
                return self.form_invalid(form)
            
            # Analyze using our local rule-based service
            analysis = analyze_resume_data(
                text=raw_text,
                target_role=target_role,
                user=self.request.user,
                resume=resume,
                uploaded_file=uploaded_file
            )
            
            messages.success(self.request, "Resume analyzed successfully!")
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
        # Enforce security: users can only view their own analyses
        return ResumeAnalysis.objects.filter(user=self.request.user)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Stagger improvement recommendations by priority
        context['high_suggestions'] = self.object.suggestions.filter(priority='High')
        context['medium_suggestions'] = self.object.suggestions.filter(priority='Medium')
        context['low_suggestions'] = self.object.suggestions.filter(priority='Low')
        return context
