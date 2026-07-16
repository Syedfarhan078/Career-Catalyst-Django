from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import Resume, Education, Experience, Project, Skill, Certification
from .forms import ResumeForm, EducationForm, ExperienceForm, ProjectForm, SkillForm, CertificationForm

import io
from xhtml2pdf import pisa

@login_required
def resume_list(request):
    resumes = Resume.objects.filter(user=request.user).order_by('-updated_at')
    return render(request, 'resume/resume_list.html', {'resumes': resumes})

@login_required
def resume_create(request):
    if request.method == 'POST':
        form = ResumeForm(request.POST)
        if form.is_valid():
            resume = form.save(commit=False)
            resume.user = request.user
            resume.save()
            return redirect('resume:builder', pk=resume.pk)
    else:
        form = ResumeForm()
    return render(request, 'resume/resume_create.html', {'form': form})

@login_required
def resume_builder(request, pk):
    resume = get_object_or_404(Resume, pk=pk, user=request.user)
    
    # Pass forms to context so user can add items
    context = {
        'resume': resume,
        'resume_form': ResumeForm(instance=resume),
        'edu_form': EducationForm(),
        'exp_form': ExperienceForm(),
        'proj_form': ProjectForm(),
        'skill_form': SkillForm(),
        'cert_form': CertificationForm(),
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
        return JsonResponse({'success': True})
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
    return JsonResponse({'success': True})

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
