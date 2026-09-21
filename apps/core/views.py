from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.roadmaps.models import UserRoadmap, TopicProgress
from apps.resume.models import Resume
from apps.ai_resume.models import ResumeAnalysis
from apps.tracker.models import JobApplication
from apps.recommendation.models import CareerAnalysis
from apps.interviews.models import UserAttempt


def home_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/home.html')


@login_required
def dashboard_view(request):
    # If the user doesn't have a profile completed yet, redirect them to complete it
    if not hasattr(request.user, 'studentprofile'):
        return redirect('profile_create')
        
    profile = request.user.studentprofile
    completion_percentage = profile.calculate_completion_percentage()
    
    # Target career goal
    target_career = (profile.career_goal or profile.preferred_domain or "").strip()
    step_1_completed = bool(target_career)
    
    # Active roadmap enrollment — prioritize matching target career
    enrollments = UserRoadmap.objects.filter(user=request.user, is_active=True).select_related('career_path')
    active_enrollment = None
    different_from_target = False

    if target_career:
        active_enrollment = enrollments.filter(career_path__name__iexact=target_career).first()
        if not active_enrollment:
            active_enrollment = enrollments.filter(career_path__name__icontains=target_career).first()
        if not active_enrollment and profile.preferred_domain:
            active_enrollment = enrollments.filter(career_path__name__icontains=profile.preferred_domain).first()

    # Fallback: if no roadmap directly matches the target goal, pick the most recently started active roadmap
    if not active_enrollment and enrollments.exists():
        active_enrollment = enrollments.order_by('-started_at', '-id').first()
        if target_career and active_enrollment:
            # The user explicitly chose or enrolled in a different roadmap
            different_from_target = (active_enrollment.career_path.name.strip().lower() != target_career.lower())

    step_2_completed = active_enrollment is not None
    
    # Resume status
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

    # Job Tracker Metrics & Pipeline
    applications = list(JobApplication.objects.filter(user=request.user))
    total_apps_count = len(applications)
    interview_apps_count = sum(1 for a in applications if a.status == 'interview')
    offer_apps_count = sum(1 for a in applications if a.status == 'offer')
    applied_apps_count = sum(1 for a in applications if a.status == 'applied')
    assessment_apps_count = sum(1 for a in applications if a.status == 'assessment')
    
    followup_due_apps = [a for a in applications if a.needs_follow_up]
    followup_due_count = len(followup_due_apps)
    
    now = timezone.now()
    upcoming_interviews = [a for a in applications if a.interview_date and a.interview_date >= now]
    upcoming_interviews.sort(key=lambda x: x.interview_date)
    
    # Latest Resume Analysis
    latest_analysis = ResumeAnalysis.objects.filter(user=request.user).order_by('-created_at').first()
    
    # Skills List
    skills_list = [s.strip() for s in (profile.skills or '').replace('\n', ',').split(',') if s.strip()]

    # Career Analysis (Readiness)
    career_analysis = CareerAnalysis.objects.filter(user=request.user).order_by('-created_at').first()

    # Interview attempts
    has_interview_attempt = UserAttempt.objects.filter(user=request.user).exists()
    interview_attempts_count = UserAttempt.objects.filter(user=request.user).count()

    # Detailed Roadmap Progress & First Incomplete Topic
    current_milestone = None
    current_topic = None
    milestone_completed_topics = 0
    milestone_total_topics = 0
    roadmap_progress = 0
    roadmap_completed_count = 0
    roadmap_total_topics = 0

    if active_enrollment:
        roadmap_progress = active_enrollment.progress_percentage()
        roadmap_completed_count = active_enrollment.completed_count()
        roadmap_total_topics = active_enrollment.career_path.total_topics()
        
        incomplete_prog = TopicProgress.objects.filter(
            user_roadmap=active_enrollment,
            is_completed=False
        ).select_related('topic', 'topic__milestone').order_by('topic__milestone__order', 'topic__milestone__week_number', 'topic__order').first()

        if incomplete_prog:
            current_milestone = incomplete_prog.topic.milestone
            current_topic = incomplete_prog.topic
            milestone_total_topics = current_milestone.topics.count()
            milestone_completed_topics = TopicProgress.objects.filter(
                user_roadmap=active_enrollment,
                topic__milestone=current_milestone,
                is_completed=True
            ).count()

    # Dynamic Time-based Greeting
    hour = timezone.localtime().hour
    if hour < 12:
        greeting_time = "Good morning"
    elif hour < 17:
        greeting_time = "Good afternoon"
    else:
        greeting_time = "Good evening"

    # User Initials for Avatar Fallback
    first_initial = (request.user.first_name[:1] if request.user.first_name else request.user.username[:1]).upper()
    last_initial = (request.user.last_name[:1] if request.user.last_name else "").upper()
    user_initials = f"{first_initial}{last_initial}" if last_initial else (request.user.username[:2].upper())

    # Deterministic "Your Next Step" Selection
    next_step = {}
    if not target_career:
        next_step = {
            'state': 'no_goal',
            'category': 'Target Role',
            'title': 'Choose your target career track',
            'subtitle': 'Select your engineering goal to personalize roadmap syllabus, skill benchmarks, and resume scans.',
            'progress': 0,
            'why': 'Defining your target role is the primary anchor for curriculum milestones and evaluation criteria.',
            'cta_text': 'Set career goal',
            'cta_url': '/profiles/edit/',
            'icon': 'bi-bullseye',
        }
    elif not active_enrollment:
        next_step = {
            'state': 'no_roadmap',
            'category': 'Career Roadmap',
            'title': f'Enroll in a structured roadmap for {target_career}',
            'subtitle': f'Choose your curated 12-week learning path aligned with {target_career}.',
            'progress': 0,
            'why': 'A structured syllabus keeps your weekly preparation focused on high-yield interview topics and project milestones.',
            'cta_text': 'Explore roadmaps',
            'cta_url': '/roadmaps/',
            'icon': 'bi-map',
        }
    elif current_topic:
        track_category = f"{active_enrollment.career_path.name} · Week {current_milestone.week_number}"
        if different_from_target:
            track_category = f"{active_enrollment.career_path.name} (Active Track) · Week {current_milestone.week_number}"
        next_step = {
            'state': 'topic_continue',
            'category': track_category,
            'title': f'Complete {current_topic.title}',
            'subtitle': f'Milestone: {current_milestone.title}',
            'progress': roadmap_progress,
            'why': f'Master {current_topic.title} to progress towards completing week {current_milestone.week_number} of {active_enrollment.career_path.name}.',
            'cta_text': 'Continue learning',
            'cta_url': f'/roadmaps/{active_enrollment.career_path.slug}/',
            'icon': 'bi-play-circle-fill',
        }
    elif not has_resume:
        next_step = {
            'state': 'build_resume',
            'category': 'Resume',
            'title': 'Build your technical resume',
            'subtitle': 'Create an ATS-friendly single-column resume with your verified skills and academic details.',
            'progress': 60,
            'why': 'Having a structured resume is essential before starting company applications and ATS keyword matching.',
            'cta_text': 'Build resume',
            'cta_url': '/resume/',
            'icon': 'bi-file-earmark-text',
        }
    elif not latest_analysis:
        next_step = {
            'state': 'scan_resume',
            'category': 'ATS Analysis',
            'title': 'Benchmark your resume against industry ATS',
            'subtitle': f'Run an ATS keyword and formatting analysis tailored to {target_career}.',
            'why': 'Detect missing industry keywords and format errors before submitting applications to recruiter portals.',
            'progress': 75,
            'cta_text': 'Scan resume',
            'cta_url': '/ai-resume/analyze/',
            'icon': 'bi-shield-check',
        }
    elif not has_interview_attempt:
        next_step = {
            'state': 'interview_practice',
            'category': 'Interview Prep',
            'title': 'Start technical mock practice & MCQs',
            'subtitle': 'Practice timed computer science fundamentals and domain coding challenges.',
            'why': 'Technical assessment rounds are the initial filter for campus placements and off-campus roles.',
            'progress': 85,
            'cta_text': 'Start practice',
            'cta_url': '/interviews/',
            'icon': 'bi-mortarboard',
        }
    else:
        next_step = {
            'state': 'track_pipeline',
            'category': 'Job CRM',
            'title': 'Review your job application pipeline',
            'subtitle': f'{total_apps_count} application{"s" if total_apps_count != 1 else ""} tracked · {interview_apps_count} interview stage',
            'progress': 95,
            'why': 'Consistent tracking and scheduled follow-ups keep your recruitment pipeline moving forward.',
            'cta_text': 'Open Job Tracker',
            'cta_url': '/tracker/',
            'icon': 'bi-kanban',
        }

    # "Your Career Journey" - 6 Semantically Accurate Stages
    # Stage 1: Target Role
    if target_career:
        role_status = 'complete'
        role_status_text = 'Complete'
    else:
        role_status = 'current'
        role_status_text = 'Current'

    # Stage 2: Profile Setup
    if completion_percentage == 100:
        profile_status = 'complete'
        profile_status_text = 'Complete'
    elif completion_percentage > 0:
        profile_status = 'in-progress'
        profile_status_text = 'In Progress'
    elif target_career:
        profile_status = 'current'
        profile_status_text = 'Current'
    else:
        profile_status = 'not-started'
        profile_status_text = 'Not Started'

    # Stage 3: Technical Skills
    if len(skills_list) >= 8 and (active_enrollment and roadmap_progress == 100):
        skills_status = 'complete'
        skills_status_text = 'Complete'
    elif len(skills_list) > 0:
        skills_status = 'in-progress'
        skills_status_text = 'In Progress'
    elif completion_percentage > 0:
        skills_status = 'current'
        skills_status_text = 'Current'
    else:
        skills_status = 'not-started'
        skills_status_text = 'Not Started'

    # Stage 4: Career Roadmap
    if active_enrollment and roadmap_progress == 100:
        roadmap_status = 'complete'
        roadmap_status_text = 'Complete'
    elif active_enrollment and roadmap_progress > 0:
        roadmap_status = 'in-progress'
        roadmap_status_text = 'In Progress'
    elif active_enrollment:
        roadmap_status = 'current'
        roadmap_status_text = 'In Progress'
    elif len(skills_list) > 0:
        roadmap_status = 'current'
        roadmap_status_text = 'Current'
    else:
        roadmap_status = 'not-started'
        roadmap_status_text = 'Not Started'

    # Stage 5: Resume & ATS
    if latest_analysis and latest_analysis.ats_score and latest_analysis.ats_score >= 80:
        resume_status = 'complete'
        resume_status_text = 'Complete'
    elif latest_analysis:
        resume_status = 'in-progress'
        resume_status_text = 'In Progress'
    elif has_resume:
        resume_status = 'in-progress'
        resume_status_text = 'In Progress'
    elif active_enrollment:
        resume_status = 'current'
        resume_status_text = 'Current'
    else:
        resume_status = 'not-started'
        resume_status_text = 'Not Started'

    # Stage 6: Interview Prep
    if has_interview_attempt and interview_attempts_count >= 5:
        interview_status = 'complete'
        interview_status_text = 'Complete'
    elif has_interview_attempt:
        interview_status = 'in-progress'
        interview_status_text = 'In Progress'
    elif latest_analysis or has_resume:
        interview_status = 'current'
        interview_status_text = 'Current'
    else:
        interview_status = 'not-started'
        interview_status_text = 'Not Started'

    career_journey = [
        {
            'id': 'role',
            'title': 'Target Role',
            'detail': target_career if target_career else 'Set your target career',
            'status': role_status,
            'status_text': role_status_text,
            'url': '/profiles/edit/',
        },
        {
            'id': 'profile',
            'title': 'Profile Setup',
            'detail': f"{completion_percentage}% completed" if completion_percentage else 'Add academic details',
            'status': profile_status,
            'status_text': profile_status_text,
            'url': '/profiles/edit/',
        },
        {
            'id': 'skills',
            'title': 'Technical Skills',
            'detail': f"{len(skills_list)} skill{'s' if len(skills_list) != 1 else ''} added" if skills_list else 'Add technical skills',
            'status': skills_status,
            'status_text': skills_status_text,
            'url': '/profiles/edit/',
        },
        {
            'id': 'roadmap',
            'title': 'Career Roadmap',
            'detail': f"{active_enrollment.career_path.name} ({roadmap_progress}%)" if active_enrollment else 'Enroll in 12-week path',
            'status': roadmap_status,
            'status_text': roadmap_status_text,
            'url': f"/roadmaps/{active_enrollment.career_path.slug}/" if active_enrollment else '/roadmaps/',
        },
        {
            'id': 'resume',
            'title': 'Resume & ATS',
            'detail': f"ATS Score: {latest_analysis.ats_score}%" if (latest_analysis and latest_analysis.ats_score) else ('Resume created' if has_resume else 'Upload & scan resume'),
            'status': resume_status,
            'status_text': resume_status_text,
            'url': '/ai-resume/history/' if latest_analysis else ('/ai-resume/analyze/' if has_resume else '/resume/'),
        },
        {
            'id': 'interview',
            'title': 'Interview Prep',
            'detail': f"{interview_attempts_count} practice session{'s' if interview_attempts_count != 1 else ''}" if has_interview_attempt else 'MCQs & assessments',
            'status': interview_status,
            'status_text': interview_status_text,
            'url': '/interviews/',
        },
    ]

    # "Recommended for You" - 3 to 4 focused recommendations
    recommendations = []
    
    if active_enrollment and current_topic:
        recommendations.append({
            'badge': 'Roadmap',
            'title': f'Continue {current_topic.title}',
            'subtitle': f'Week {current_milestone.week_number} · {current_milestone.title}',
            'action_text': 'Continue learning',
            'action_url': f'/roadmaps/{active_enrollment.career_path.slug}/',
            'icon': 'bi-map',
        })
    elif not active_enrollment:
        recommendations.append({
            'badge': 'Roadmap',
            'title': f'Explore {target_career or "Engineering"} Roadmaps',
            'subtitle': 'Structured 12-week milestones with curated resources',
            'action_text': 'Explore roadmaps',
            'action_url': '/roadmaps/',
            'icon': 'bi-compass',
        })

    if not latest_analysis:
        recommendations.append({
            'badge': 'Resume',
            'title': 'Benchmark resume with ATS Analyzer',
            'subtitle': 'Identify missing industry keywords and format errors',
            'action_text': 'Scan resume',
            'action_url': '/ai-resume/analyze/' if has_resume else '/resume/',
            'icon': 'bi-file-earmark-check',
        })
    else:
        recommendations.append({
            'badge': 'Resume',
            'title': f'Review ATS score ({latest_analysis.ats_score}%)',
            'subtitle': 'Check keyword coverage and suggested improvements',
            'action_text': 'View ATS report',
            'action_url': '/ai-resume/history/',
            'icon': 'bi-file-earmark-text',
        })

    if not has_interview_attempt:
        recommendations.append({
            'badge': 'Interview',
            'title': 'Practice technical MCQs & assessments',
            'subtitle': 'Prepare for timed campus screening rounds',
            'action_text': 'Start practice',
            'action_url': '/interviews/',
            'icon': 'bi-mortarboard',
        })
    else:
        recommendations.append({
            'badge': 'Interview',
            'title': 'Take a mock technical interview',
            'subtitle': 'Continue practicing coding and domain challenges',
            'action_text': 'Practice more',
            'action_url': '/interviews/',
            'icon': 'bi-mortarboard',
        })

    recommendations.append({
        'badge': 'Guidance',
        'title': 'Calibrate company hiring tier',
        'subtitle': 'Evaluate profile readiness for Product vs Service-based cutoffs',
        'action_text': 'Check readiness',
        'action_url': '/recommendation/',
        'icon': 'bi-sliders',
    })

    # Limit to 3-4 recommendations
    recommendations = recommendations[:4]

    # Readiness breakdown dictionary
    readiness_data = {
        'has_analysis': bool(career_analysis),
        'score': career_analysis.career_readiness_score if career_analysis else 0,
        'profile_metric': f"{completion_percentage}%",
        'skills_metric': f"{career_analysis.confidence_score}%" if (career_analysis and career_analysis.confidence_score) else f"{min(len(skills_list)*15, 100)}%",
        'roadmap_metric': f"{roadmap_progress}%",
        'resume_metric': f"{latest_analysis.ats_score}%" if (latest_analysis and latest_analysis.ats_score) else ("Created" if has_resume else "Pending"),
        'interview_metric': "Active" if has_interview_attempt else "Pending",
    }

    context = {
        'profile': profile,
        'completion_percentage': completion_percentage,
        'launch_plan': launch_plan,
        'active_enrollment': active_enrollment,
        'target_career': target_career,
        'skills_list': skills_list,
        'total_apps_count': total_apps_count,
        'interview_apps_count': interview_apps_count,
        'offer_apps_count': offer_apps_count,
        'applied_apps_count': applied_apps_count,
        'assessment_apps_count': assessment_apps_count,
        'followup_due_apps': followup_due_apps,
        'followup_due_count': followup_due_count,
        'upcoming_interviews': upcoming_interviews,
        'latest_analysis': latest_analysis,
        'has_resume': has_resume,
        # Enhanced redesign context
        'greeting_time': greeting_time,
        'user_initials': user_initials,
        'next_step': next_step,
        'career_journey': career_journey,
        'recommendations': recommendations,
        'readiness_data': readiness_data,
        'career_analysis': career_analysis,
        'current_milestone': current_milestone,
        'current_topic': current_topic,
        'milestone_completed_topics': milestone_completed_topics,
        'milestone_total_topics': milestone_total_topics,
        'roadmap_progress': roadmap_progress,
        'roadmap_completed_count': roadmap_completed_count,
        'roadmap_total_topics': roadmap_total_topics,
        'different_from_target': different_from_target,
    }
    return render(request, 'core/dashboard.html', context)