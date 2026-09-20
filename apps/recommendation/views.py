from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from apps.resume.models import Resume
from apps.ai_resume.models import ResumeAnalysis
from apps.profiles.models import StudentProfile
from apps.roadmaps.models import CareerPath, UserRoadmap, TopicProgress
from .models import CareerAnalysis
from .forms import CareerTargetForm
from .services import generate_career_recommendation, enroll_and_sync_roadmap

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

    # 2. Get the latest analysis with safe fallback
    try:
        analysis = CareerAnalysis.objects.filter(user=request.user).first()
    except Exception:
        analysis = None
    
    # Check if user has uploaded or created a resume safely
    try:
        latest_resume_analysis = ResumeAnalysis.objects.filter(user=request.user).order_by('-created_at').first()
    except Exception:
        latest_resume_analysis = None

    try:
        has_builder_resume = Resume.objects.filter(user=request.user).exists()
    except Exception:
        has_builder_resume = False

    user_has_resume = (latest_resume_analysis is not None) or has_builder_resume
    
    # Check Roadmap Enrollment & Auto-Sync Pre-calculations
    matched_career_path = None
    user_roadmap = None
    is_enrolled_in_path = False
    auto_synced_count = 0
    auto_starting_pct = 0
    next_active_week = 1
    
    if analysis:
        identifier = analysis.recommended_career.strip()
        matched_career_path = (
            CareerPath.objects.filter(name__iexact=identifier).first() or
            CareerPath.objects.filter(slug__iexact=identifier).first() or
            CareerPath.objects.filter(name__icontains=identifier).first() or
            CareerPath.objects.filter(is_active=True).first()
        )
        
        if matched_career_path:
            user_roadmap = UserRoadmap.objects.filter(
                user=request.user, 
                career_path=matched_career_path
            ).first()
            
            if user_roadmap and user_roadmap.is_active:
                is_enrolled_in_path = True
                # Find the next incomplete week
                milestones = matched_career_path.milestones.prefetch_related('topics').order_by('week_number')
                for ms in milestones:
                    ms_topic_ids = list(ms.topics.values_list('id', flat=True))
                    completed_in_ms = TopicProgress.objects.filter(
                        user_roadmap=user_roadmap,
                        topic_id__in=ms_topic_ids,
                        is_completed=True
                    ).count()
                    if completed_in_ms < len(ms_topic_ids):
                        next_active_week = ms.week_number
                        break
            else:
                # Count how many topics from analysis matched the student profile
                all_matched = []
                for step in (analysis.roadmap_json or []):
                    all_matched.extend(step.get('matched_topics', []))
                auto_synced_count = len(set(all_matched))
                total_topics = matched_career_path.total_topics()
                auto_starting_pct = round((auto_synced_count / total_topics) * 100) if total_topics > 0 else 0
                
                # Check which week they would jump to
                for step in (analysis.roadmap_json or []):
                    if step.get('coverage_pct', 0) < 100:
                        next_active_week = step.get('week', 1)
                        break

    context = {
        'analysis': analysis,
        'profile': profile,
        'form': CareerTargetForm(),
        'latest_resume_analysis': latest_resume_analysis,
        'user_has_resume': user_has_resume,
        'matched_career_path': matched_career_path,
        'user_roadmap': user_roadmap,
        'is_enrolled_in_path': is_enrolled_in_path,
        'auto_synced_count': auto_synced_count,
        'auto_starting_pct': auto_starting_pct,
        'next_active_week': next_active_week,
    }
    return render(request, 'recommendation/dashboard.html', context)


@login_required
@require_POST
def run_analysis(request):
    """
    Triggers/regenerates the hybrid recommendation analysis with company tier calibration.
    """
    form = CareerTargetForm(request.POST)
    target_role_name = None
    company_tier = 'general'
    
    if form.is_valid():
        career_path = form.cleaned_data.get('target_career')
        if career_path:
            target_role_name = career_path.name
        company_tier = form.cleaned_data.get('company_tier') or 'general'
    else:
        company_tier = request.POST.get('company_tier', 'general')
            
    try:
        tier_label = "Product & Startup" if company_tier == 'product' else ("Enterprise & IT Services" if company_tier == 'service' else "General Industry")
        messages.info(request, f"AI Recommendations Engine is analyzing your profile metrics for {tier_label} standards...")
        analysis = generate_career_recommendation(request.user, target_role_name, company_tier)
        messages.success(request, f"Analysis successfully calibrated for {tier_label} ({analysis.recommended_career})!")
    except Exception as e:
        messages.error(request, f"Recommendations Engine encountered an issue: {str(e)}")
        
    return redirect('recommendation:dashboard')



@login_required
@require_POST
def activate_roadmap_from_analysis(request, analysis_id):
    """
    1-Click Roadmap Activation & Auto-Sync:
    Enrolls user in the recommended roadmap and pre-completes matched skills.
    """
    analysis = get_object_or_404(CareerAnalysis, id=analysis_id, user=request.user)
    try:
        matched_topics = []
        for step in (analysis.roadmap_json or []):
            matched_topics.extend(step.get('matched_topics', []))
            
        sync_result = enroll_and_sync_roadmap(
            user=request.user,
            career_path_identifier=analysis.recommended_career,
            matched_topics_list=matched_topics
        )
        
        career_path = sync_result['career_path']
        synced_count = sync_result['synced_topics_count']
        progress_pct = sync_result['progress_percentage']
        next_week = sync_result['first_incomplete_week']
        
        if synced_count > 0:
            messages.success(
                request,
                f"🚀 Successfully activated your {career_path.name} roadmap! "
                f"We pre-completed {synced_count} topics based on your verified skills. "
                f"You're starting at {progress_pct}% progress on Week {next_week}!"
            )
        else:
            messages.success(
                request,
                f"🚀 Successfully activated your {career_path.name} roadmap! Jump into Week {next_week} below."
            )
        return redirect('roadmaps:path_detail', slug=career_path.slug)
    except Exception as e:
        messages.error(request, f"Could not activate roadmap: {str(e)}")
        return redirect('recommendation:dashboard')

