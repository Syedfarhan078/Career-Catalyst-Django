# apps/core/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

def home_view(request): # Ensure this function name is 'home'
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/home.html')

from apps.roadmaps.models import UserRoadmap
from apps.resume.models import Resume
from apps.ai_resume.models import ResumeAnalysis

@login_required
def dashboard_view(request):
    # If the user doesn't have a profile completed yet, redirect them to complete it
    if not hasattr(request.user, 'studentprofile'):
        return redirect('profile_create')
        
    profile = request.user.studentprofile
    completion_percentage = profile.calculate_completion_percentage()
    
    # Adaptive Career Launch Plan
    # Step 1: Set target career goal
    target_career = (profile.career_goal or profile.preferred_domain or "").strip()
    step_1_completed = bool(target_career)
    
    # Step 2: Start career roadmap (enrolled in at least one active roadmap)
    active_enrollment = UserRoadmap.objects.filter(user=request.user, is_active=True).select_related('career_path').first()
    step_2_completed = active_enrollment is not None
    
    # Step 3: Benchmark resume (created a resume or run an ATS analysis)
    has_resume = Resume.objects.filter(user=request.user).exists()
    has_analysis = ResumeAnalysis.objects.filter(user=request.user).exists()
    step_3_completed = has_resume or has_analysis
    
    completed_steps_count = sum([1 for s in [step_1_completed, step_2_completed, step_3_completed] if s])
    all_steps_completed = (completed_steps_count == 3)
    
    launch_plan = {
        'step_1': {
            'completed': step_1_completed,
            'title': 'Set your target career',
            'value': target_career if step_1_completed else 'Tell us your target career goal to tailor your experience',
        },
        'step_2': {
            'completed': step_2_completed,
            'title': 'Start your career roadmap',
            'value': active_enrollment.career_path.name if step_2_completed else 'Follow a structured path toward your goal',
        },
        'step_3': {
            'completed': step_3_completed,
            'title': 'Benchmark your resume',
            'value': 'ATS benchmark completed' if step_3_completed else 'Upload your resume for an ATS analysis',
        },
        'completed_count': completed_steps_count,
        'total_count': 3,
        'all_completed': all_steps_completed,
    }
    
    context = {
        'profile': profile,
        'completion_percentage': completion_percentage,
        'launch_plan': launch_plan,
        'active_enrollment': active_enrollment,
    }
    return render(request, 'core/dashboard.html', context)