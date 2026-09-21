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

def _calculate_pillars(analysis, user, profile, matched_career_path, user_roadmap):
    if not analysis:
        return None
    
    tier = analysis.target_company_tier or 'general'
    
    # Calculate matched topics ratio
    total_path_topics = matched_career_path.total_topics() if matched_career_path else 0
    all_matched = []
    for step in (analysis.roadmap_json or []):
        all_matched.extend(step.get('matched_topics', []))
    matched_count = len(set(all_matched))
    skill_match_ratio = (matched_count / total_path_topics) if total_path_topics > 0 else 0.0
    
    # Check default resume
    default_resume = Resume.objects.filter(user=user, is_default=True).first() or Resume.objects.filter(user=user).first()
    projects_count = default_resume.projects.count() if default_resume else 0
    experiences_count = default_resume.experiences.count() if default_resume else 0
    certifications_count = default_resume.certifications.count() if default_resume else 0
    is_enrolled = bool(user_roadmap and user_roadmap.is_active)
    
    cgpa_val = 0.0
    if profile and profile.cgpa:
        try:
            cgpa_val = float(profile.cgpa)
        except (ValueError, TypeError):
            cgpa_val = 6.0

    if tier == 'product':
        max_skills, max_projects, max_academic, max_exp = 45, 30, 10, 15
        pillar_skills = round(skill_match_ratio * 45)
        if projects_count >= 3:
            pillar_projects = 30
        elif projects_count == 2:
            pillar_projects = 22
        elif projects_count == 1:
            pillar_projects = 12
        else:
            pillar_projects = 0
            
        if cgpa_val >= 8.5:
            pillar_academic = 10
        elif cgpa_val >= 7.5:
            pillar_academic = 8
        elif cgpa_val >= 6.5:
            pillar_academic = 6
        else:
            pillar_academic = 4
            
        p_exp = min(experiences_count * 6, 8)
        p_certs = min(certifications_count * 3, 4)
        p_enr = 3 if is_enrolled else 0
        pillar_exp = min(p_exp + p_certs + p_enr, 15)
        
    elif tier == 'service':
        max_skills, max_projects, max_academic, max_exp = 35, 20, 25, 20
        pillar_skills = round(skill_match_ratio * 35)
        if projects_count >= 2:
            pillar_projects = 20
        elif projects_count == 1:
            pillar_projects = 14
        else:
            pillar_projects = 0
            
        if cgpa_val >= 8.5:
            pillar_academic = 25
        elif cgpa_val >= 7.5:
            pillar_academic = 20
        elif cgpa_val >= 6.5:
            pillar_academic = 15
        else:
            pillar_academic = 6
            
        p_exp = min(experiences_count * 8, 10)
        p_certs = min(certifications_count * 6, 8)
        p_enr = 2 if is_enrolled else 0
        pillar_exp = min(p_exp + p_certs + p_enr, 20)
        
    else:
        max_skills, max_projects, max_academic, max_exp = 40, 25, 15, 20
        pillar_skills = round(skill_match_ratio * 40)
        if projects_count >= 3:
            pillar_projects = 25
        elif projects_count == 2:
            pillar_projects = 18
        elif projects_count == 1:
            pillar_projects = 10
        else:
            pillar_projects = 0
            
        if cgpa_val >= 8.5:
            pillar_academic = 15
        elif cgpa_val >= 7.5:
            pillar_academic = 12
        elif cgpa_val >= 6.5:
            pillar_academic = 9
        else:
            pillar_academic = 5
            
        p_exp = min(experiences_count * 8, 10)
        p_certs = min(certifications_count * 4, 6)
        p_enr = 4 if is_enrolled else 0
        pillar_exp = min(p_exp + p_certs + p_enr, 20)

    return [
        {
            'name': 'Core Technical Skills',
            'icon': 'bi-code-slash',
            'score': pillar_skills,
            'max': max_skills,
            'pct': round((pillar_skills / max_skills) * 100) if max_skills else 0,
            'metric_label': f"{matched_count}/{total_path_topics} Topics Matched" if total_path_topics else f"{matched_count} Topics",
            'badge': 'Primary Weight' if tier == 'product' else 'Foundational'
        },
        {
            'name': 'Applied Projects',
            'icon': 'bi-folder-check',
            'score': pillar_projects,
            'max': max_projects,
            'pct': round((pillar_projects / max_projects) * 100) if max_projects else 0,
            'metric_label': f"{projects_count} Project{'s' if projects_count != 1 else ''} Documented",
            'badge': 'High Priority' if tier == 'product' else 'Supporting'
        },
        {
            'name': 'Academic Benchmark',
            'icon': 'bi-mortarboard',
            'score': pillar_academic,
            'max': max_academic,
            'pct': round((pillar_academic / max_academic) * 100) if max_academic else 0,
            'metric_label': f"CGPA: {cgpa_val:.1f}" if cgpa_val > 0 else "CGPA Recorded",
            'badge': 'Strict Cutoff' if tier == 'service' else 'Baseline'
        },
        {
            'name': 'Experience & Certs',
            'icon': 'bi-award',
            'score': pillar_exp,
            'max': max_exp,
            'pct': round((pillar_exp / max_exp) * 100) if max_exp else 0,
            'metric_label': f"{experiences_count} Exp · {certifications_count} Cert{'s' if certifications_count != 1 else ''}",
            'badge': 'Track Active' if is_enrolled else 'Credentials'
        }
    ]


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

    # Compute sidebar user initials and target career
    first_initial = (request.user.first_name[:1] if request.user.first_name else request.user.username[:1]).upper()
    last_initial = (request.user.last_name[:1] if request.user.last_name else "").upper()
    user_initials = f"{first_initial}{last_initial}" if last_initial else (request.user.username[:2].upper())
    target_career = profile.career_goal.strip() if (profile and profile.career_goal) else ""

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
    is_path_completed = False
    auto_synced_count = 0
    auto_starting_pct = 0
    next_active_week = 1
    role_skill_match_pct = 0
    
    if analysis:
        identifier = analysis.recommended_career.strip()
        matched_career_path = (
            CareerPath.objects.filter(name__iexact=identifier).first() or
            CareerPath.objects.filter(slug__iexact=identifier).first() or
            CareerPath.objects.filter(name__icontains=identifier).first() or
            CareerPath.objects.filter(is_active=True).first()
        )
        
        # Calculate matched topics count and role skill match percentage
        total_path_topics = matched_career_path.total_topics() if matched_career_path else 0
        all_matched = []
        for step in (analysis.roadmap_json or []):
            all_matched.extend(step.get('matched_topics', []))
        auto_synced_count = len(set(all_matched))
        role_skill_match_pct = round((auto_synced_count / total_path_topics) * 100) if total_path_topics > 0 else 0

        if matched_career_path:
            user_roadmap = UserRoadmap.objects.filter(
                user=request.user, 
                career_path=matched_career_path
            ).first()
            
            if user_roadmap and user_roadmap.is_active:
                is_enrolled_in_path = True
                progress_pct = user_roadmap.progress_percentage()

                # Find the next incomplete week with a single query (avoid N+1)
                completed_topic_ids = set(
                    TopicProgress.objects.filter(
                        user_roadmap=user_roadmap,
                        is_completed=True
                    ).values_list('topic_id', flat=True)
                )
                milestones = matched_career_path.milestones.prefetch_related('topics').order_by('week_number')
                first_incomplete_week = None
                for ms in milestones:
                    ms_topics = ms.topics.all()
                    if not ms_topics:
                        continue
                    completed_count = sum(1 for t in ms_topics if t.id in completed_topic_ids)
                    if completed_count < len(ms_topics):
                        first_incomplete_week = ms.week_number
                        break

                if progress_pct >= 100 or (milestones.exists() and first_incomplete_week is None):
                    is_path_completed = True
                    next_active_week = None
                else:
                    is_path_completed = False
                    next_active_week = first_incomplete_week or 1
            else:
                auto_starting_pct = round((auto_synced_count / total_path_topics) * 100) if total_path_topics > 0 else 0
                
                # Check which week they would jump to
                next_active_week = 1
                for step in (analysis.roadmap_json or []):
                    if step.get('coverage_pct', 0) < 100:
                        next_active_week = step.get('week', 1)
                        break

    pillars = _calculate_pillars(analysis, request.user, profile, matched_career_path, user_roadmap)

    context = {
        'analysis': analysis,
        'profile': profile,
        'form': CareerTargetForm(),
        'latest_resume_analysis': latest_resume_analysis,
        'user_has_resume': user_has_resume,
        'matched_career_path': matched_career_path,
        'user_roadmap': user_roadmap,
        'is_enrolled_in_path': is_enrolled_in_path,
        'is_path_completed': is_path_completed,
        'auto_synced_count': auto_synced_count,
        'auto_starting_pct': auto_starting_pct,
        'next_active_week': next_active_week,
        'role_skill_match_pct': role_skill_match_pct,
        'user_initials': user_initials,
        'target_career': target_career,
        'pillars': pillars,
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

