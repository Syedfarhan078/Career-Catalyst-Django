from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import Resume, Education, Experience, Project, Skill, Certification
from .forms import ResumeForm, EducationForm, ExperienceForm, ProjectForm, SkillForm, CertificationForm
from apps.ai_resume.models import ResumeAnalysis

import io
from xhtml2pdf import pisa

@login_required
def resume_list(request):
    resumes = Resume.objects.filter(user=request.user).order_by('-is_default', '-updated_at')
    default_resume = resumes.filter(is_default=True).first() or resumes.first()
    other_resumes = [r for r in resumes if r.pk != (default_resume.pk if default_resume else None)]
    
    # ATS Scanner overview & recent history
    try:
        latest_analysis = ResumeAnalysis.objects.filter(user=request.user).select_related('resume').order_by('-created_at').first()
        recent_analyses = ResumeAnalysis.objects.filter(user=request.user).select_related('resume').order_by('-created_at')[:5]
        total_analyses_count = ResumeAnalysis.objects.filter(user=request.user).count()
    except Exception:
        latest_analysis = None
        recent_analyses = []
        total_analyses_count = 0
        
    profile = getattr(request.user, 'studentprofile', None)
    first_initial = (request.user.first_name[:1] if request.user.first_name else request.user.username[:1]).upper()
    last_initial = (request.user.last_name[:1] if request.user.last_name else "").upper()
    user_initials = f"{first_initial}{last_initial}" if last_initial else (request.user.username[:2].upper())
    target_career = profile.career_goal.strip() if (profile and profile.career_goal) else ""

    context = {
        'resumes': resumes,
        'default_resume': default_resume,
        'other_resumes': other_resumes,
        'latest_analysis': latest_analysis,
        'recent_analyses': recent_analyses,
        'total_analyses_count': total_analyses_count,
        'profile': profile,
        'user_initials': user_initials,
        'target_career': target_career,
    }
    return render(request, 'resume/resume_list.html', context)

@login_required
def resume_create(request):
    profile = getattr(request.user, 'studentprofile', None)
    first_initial = (request.user.first_name[:1] if request.user.first_name else request.user.username[:1]).upper()
    last_initial = (request.user.last_name[:1] if request.user.last_name else "").upper()
    user_initials = f"{first_initial}{last_initial}" if last_initial else (request.user.username[:2].upper())
    target_career = profile.career_goal.strip() if (profile and profile.career_goal) else ""

    if request.method == 'POST':
        form = ResumeForm(request.POST)
        if form.is_valid():
            resume = form.save(commit=False)
            resume.user = request.user
            resume.save()
            return redirect('resume:builder', pk=resume.pk)
    else:
        form = ResumeForm()
    return render(request, 'resume/resume_create.html', {
        'form': form,
        'profile': profile,
        'user_initials': user_initials,
        'target_career': target_career,
    })

@login_required
def resume_builder(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    profile = getattr(request.user, 'studentprofile', None)
    first_initial = (request.user.first_name[:1] if request.user.first_name else request.user.username[:1]).upper()
    last_initial = (request.user.last_name[:1] if request.user.last_name else "").upper()
    user_initials = f"{first_initial}{last_initial}" if last_initial else (request.user.username[:2].upper())
    target_career = profile.career_goal.strip() if (profile and profile.career_goal) else ""

    # Pass forms to context so user can add items
    context = {
        'resume': resume,
        'resume_form': ResumeForm(instance=resume),
        'edu_form': EducationForm(),
        'exp_form': ExperienceForm(),
        'proj_form': ProjectForm(),
        'skill_form': SkillForm(),
        'cert_form': CertificationForm(),
        'profile': profile,
        'user_initials': user_initials,
        'target_career': target_career,
    }
    return render(request, 'resume/builder.html', context)

@login_required
@xframe_options_sameorigin
def resume_preview(request, pk):
    """
    Renders the resume template as raw HTML. This is used in the iframe for live preview.
    """
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    try:
        profile = request.user.studentprofile
    except:
        profile = None
    
    context = {
        'resume': resume,
        'user': request.user,
        'profile': profile,
        'is_preview': True
    }
    
    template_name = f'resume/templates/{resume.template}.html'
    return render(request, template_name, context)

@login_required
def resume_download_pdf(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    try:
        profile = request.user.studentprofile
    except:
        profile = None

    template_name = f'resume/templates/{resume.template}.html'
    html_string = render_to_string(template_name, {
        'resume': resume, 
        'user': request.user, 
        'profile': profile,
        'is_pdf': True
    })

    # Convert HTML to PDF using xhtml2pdf
    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(html_string, dest=buffer)

    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html_string + '</pre>')
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"{request.user.username}_{resume.title.replace(' ', '_')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# AJAX Endpoints for builder

from apps.profiles.models import StudentProfile

def get_section_items(resume, section):
    if section == 'education':
        return [{'pk': x.pk, 'title': x.degree, 'subtitle': x.college} for x in resume.educations.all()]
    elif section == 'experience':
        return [{'pk': x.pk, 'title': x.position, 'subtitle': x.company} for x in resume.experiences.all()]
    elif section == 'project':
        return [{'pk': x.pk, 'title': x.title} for x in resume.projects.all()]
    elif section == 'skill':
        return [{'pk': x.pk, 'title': x.name} for x in resume.skills.all()]
    elif section == 'certification':
        return [{'pk': x.pk, 'title': x.name, 'subtitle': x.organization} for x in resume.certifications.all()]
    return []

@login_required
@require_POST
def add_section(request, pk, section):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    
    form_classes = {
        'education': EducationForm,
        'experience': ExperienceForm,
        'project': ProjectForm,
        'skill': SkillForm,
        'certification': CertificationForm,
    }
    
    if section not in form_classes:
        return JsonResponse({'success': False, 'error': 'Invalid section'})
        
    form = form_classes[section](request.POST)
    if form.is_valid():
        instance = form.save(commit=False)
        instance.resume = resume
        instance.save()
        return JsonResponse({'success': True, 'items': get_section_items(resume, section)})
    else:
        return JsonResponse({'success': False, 'errors': form.errors})

@login_required
@require_POST
def delete_section(request, pk, section, item_id):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    
    model_classes = {
        'education': Education,
        'experience': Experience,
        'project': Project,
        'skill': Skill,
        'certification': Certification,
    }
    
    if section not in model_classes:
        return JsonResponse({'success': False, 'error': 'Invalid section'})
        
    item = get_object_or_404(model_classes[section], pk=item_id, resume=resume)
    item.delete()
    return JsonResponse({'success': True, 'items': get_section_items(resume, section)})

@login_required
@require_POST
def update_resume_settings(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    form = ResumeForm(request.POST, instance=resume)
    if form.is_valid():
        form.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'errors': form.errors})

@login_required
@require_POST
def delete_resume(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    resume.delete()
    return redirect('resume:list')

@login_required
@require_POST
def import_profile_data(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student Profile not found. Please create one first.'})

    imported_edu = False
    imported_skills_count = 0

    # 1. Import Education
    if profile.college and profile.degree and not resume.educations.exists():
        Education.objects.create(
            resume=resume,
            college=profile.college,
            degree=profile.degree,
            branch=profile.branch or "General",
            cgpa=profile.cgpa or 0.0,
            start_year=2022,
            end_year=profile.graduation_year or 2026
        )
        imported_edu = True

    # 2. Import Skills
    if profile.skills:
        skills_raw = profile.skills.replace('\n', ',')
        skills_list = [s.strip() for s in skills_raw.split(',') if s.strip()]
        for s_name in skills_list:
            if not resume.skills.filter(name__iexact=s_name).exists():
                Skill.objects.create(resume=resume, name=s_name)
                imported_skills_count += 1

    return JsonResponse({
        'success': True,
        'educations': get_section_items(resume, 'education'),
        'skills': get_section_items(resume, 'skill'),
        'imported_edu': imported_edu,
        'imported_skills_count': imported_skills_count
    })
