from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from apps.profiles.models import StudentProfile
from .models import CareerAnalysis
from .forms import CareerTargetForm
from .services import generate_career_recommendation

@login_required
def career_dashboard(request):
    """
    Renders the Career Guidance and Recommendation Dashboard.
    If no analysis has been run, shows an introductory landing state.
    """
    # 1. Check if user profile is completed
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        messages.warning(request, "Please create and complete your Student Profile details before analyzing your career.")
        return redirect('profile_create')
        
    # Check basic profile requirement: must have skills and a college defined
    if not profile.skills or not profile.college:
        messages.warning(request, "Your profile is missing details (e.g. skills, college info). Please update it to get accurate recommendations.")
        return redirect('profile_edit')

    # 2. Get the latest analysis
    analysis = CareerAnalysis.objects.filter(user=request.user).first()
    
    context = {
        'analysis': analysis,
        'profile': profile,
        'form': CareerTargetForm()
    }
    return render(request, 'recommendation/dashboard.html', context)


@login_required
@require_POST
def run_analysis(request):
    """
    Triggers/regenerates the hybrid recommendation analysis.
    """
    form = CareerTargetForm(request.POST)
    target_role_name = None
    
    if form.is_valid():
        career_path = form.cleaned_data.get('target_career')
        if career_path:
            target_role_name = career_path.name
            
    try:
        messages.info(request, "AI Recommendations Engine is analyzing your profile metrics...")
        analysis = generate_career_recommendation(request.user, target_role_name)
        messages.success(request, f"Career analysis successfully generated for the role: {analysis.recommended_career}!")
    except Exception as e:
        messages.error(request, f"Recommendations Engine encountered an issue: {str(e)}")
        
    return redirect('recommendation:dashboard')
