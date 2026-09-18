import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from .models import JobApplication
from .forms import JobApplicationForm
from .services import parse_job_url, generate_follow_up_email


@login_required
def kanban_view(request):
    """
    Main interactive Kanban CRM dashboard for tracking job & internship applications.
    """
    applications_qs = JobApplication.objects.filter(user=request.user)
    
    # Search & Filters
    search_query = request.GET.get('q', '').strip()
    job_type_filter = request.GET.get('job_type', '').strip()
    
    if search_query:
        applications_qs = applications_qs.filter(
            company_name__icontains=search_query
        ) | applications_qs.filter(
            role_title__icontains=search_query
        ) | applications_qs.filter(
            location__icontains=search_query
        ) | applications_qs.filter(
            notes__icontains=search_query
        )
        
    if job_type_filter:
        applications_qs = applications_qs.filter(job_type=job_type_filter)
        
    all_apps = list(applications_qs)
    
    # Metric Calculations
    total_apps = len(all_apps)
    interviews_count = sum(1 for a in all_apps if a.status == 'interview')
    offers_count = sum(1 for a in all_apps if a.status == 'offer')
    assessments_count = sum(1 for a in all_apps if a.status == 'assessment')
    
    # Responses are candidates who reached assessment, interview, or offer
    responses_count = assessments_count + interviews_count + offers_count
    response_rate = round((responses_count / total_apps * 100), 1) if total_apps > 0 else 0
    
    follow_up_needed_count = sum(1 for a in all_apps if a.needs_follow_up)
    ghosted_count = sum(1 for a in all_apps if a.is_ghosted)
    
    # Column Grouping
    column_definitions = [
        {'id': 'bookmarked', 'title': 'Bookmarked', 'icon': 'bi-bookmark', 'badge': 'secondary'},
        {'id': 'applied', 'title': 'Applied', 'icon': 'bi-send', 'badge': 'primary'},
        {'id': 'referral_requested', 'title': 'Referral Requested', 'icon': 'bi-people', 'badge': 'info'},
        {'id': 'assessment', 'title': 'Assessment / OA', 'icon': 'bi-code-slash', 'badge': 'warning'},
        {'id': 'interview', 'title': 'Interview', 'icon': 'bi-chat-dots', 'badge': 'primary'},
        {'id': 'offer', 'title': 'Offer Received', 'icon': 'bi-trophy-fill', 'badge': 'success'},
        {'id': 'rejected', 'title': 'Rejected / Closed', 'icon': 'bi-x-circle', 'badge': 'danger'},
    ]
    
    columns = []
    for col_def in column_definitions:
        col_apps = [a for a in all_apps if a.status == col_def['id']]
        columns.append({
            'id': col_def['id'],
            'title': col_def['title'],
            'icon': col_def['icon'],
            'badge': col_def['badge'],
            'count': len(col_apps),
            'applications': col_apps
        })
        
    form = JobApplicationForm()
    
    context = {
        'columns': columns,
        'form': form,
        'total_apps': total_apps,
        'response_rate': response_rate,
        'interviews_count': interviews_count,
        'offers_count': offers_count,
        'follow_up_needed_count': follow_up_needed_count,
        'ghosted_count': ghosted_count,
        'search_query': search_query,
        'job_type_filter': job_type_filter,
        'job_type_choices': JobApplication.JOB_TYPE_CHOICES,
        'status_choices': JobApplication.STATUS_CHOICES,
    }
    
    return render(request, 'tracker/kanban.html', context)


@login_required
@require_POST
def add_application(request):
    """
    Handles standard and 10-Second Quick-Add application creation.
    """
    form = JobApplicationForm(request.POST)
    if form.is_valid():
        application = form.save(commit=False)
        application.user = request.user
        application.save()
        messages.success(request, f"Added {application.role_title} at {application.company_name} to your board!")
    else:
        error_msgs = ", ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
        messages.error(request, f"Could not add application: {error_msgs}")
        
    return redirect('tracker:kanban')


@login_required
def edit_application(request, pk):
    """
    Edit an existing job application. Returns JSON data for AJAX modal or redirects on POST.
    """
    application = get_object_or_404(JobApplication, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = JobApplicationForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {application.company_name} application.")
            return redirect('tracker:kanban')
        else:
            messages.error(request, "Please correct the errors in the form.")
            return redirect('tracker:kanban')
            
    # GET request via AJAX - returns JSON for populating edit modal
    return JsonResponse({
        'id': application.id,
        'company_name': application.company_name,
        'role_title': application.role_title,
        'job_type': application.job_type,
        'status': application.status,
        'job_url': application.job_url or '',
        'location': application.location or '',
        'salary_or_stipend': application.salary_or_stipend or '',
        'applied_date': application.applied_date.strftime('%Y-%m-%d') if application.applied_date else '',
        'interview_date': application.interview_date.strftime('%Y-%m-%dT%H:%M') if application.interview_date else '',
        'contact_person': application.contact_person or '',
        'notes': application.notes or '',
    })


@login_required
@require_POST
def delete_application(request, pk):
    """
    Delete an application entry.
    """
    application = get_object_or_404(JobApplication, pk=pk, user=request.user)
    company = application.company_name
    role = application.role_title
    application.delete()
    messages.success(request, f"Removed {role} at {company} from your board.")
    return redirect('tracker:kanban')


@login_required
@require_POST
def api_update_status(request, pk):
    """
    AJAX endpoint for drag-and-drop Kanban updates.
    """
    application = get_object_or_404(JobApplication, pk=pk, user=request.user)
    
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST
        
    new_status = data.get('status')
    valid_statuses = [choice[0] for choice in JobApplication.STATUS_CHOICES]
    
    if not new_status or new_status not in valid_statuses:
        return JsonResponse({'success': False, 'error': 'Invalid status choice'}, status=400)
        
    old_status = application.status
    application.status = new_status
    
    # If moving to interview and no interview date yet, touch last_contact_date
    if new_status == 'interview' and old_status != 'interview':
        application.last_contact_date = timezone.now().date()
        
    application.save()
    
    return JsonResponse({
        'success': True,
        'pk': application.id,
        'status': application.status,
        'status_display': application.get_status_display(),
        'is_offer': application.status == 'offer',
        'needs_follow_up': application.needs_follow_up,
        'is_ghosted': application.is_ghosted
    })


@login_required
def api_parse_url(request):
    """
    AJAX helper to parse pasted job URLs and auto-extract company/platform metadata.
    """
    url_to_parse = request.GET.get('url', '').strip() or request.POST.get('url', '').strip()
    result = parse_job_url(url_to_parse)
    return JsonResponse(result)


@login_required
def api_generate_followup(request, pk):
    """
    AJAX helper to generate a 1-click tailored follow-up email draft with mailto link.
    """
    application = get_object_or_404(JobApplication, pk=pk, user=request.user)
    data = generate_follow_up_email(application, request.user)
    return JsonResponse(data)
