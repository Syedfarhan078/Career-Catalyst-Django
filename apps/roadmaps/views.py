from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages

from .models import CareerPath, Milestone, Topic, UserRoadmap, TopicProgress
from apps.profiles.models import StudentProfile


def _get_user_display_context(user):
    """Helper to provide consistent user profile and initials context for the sidebar."""
    profile = getattr(user, 'profile', None)
    if not profile:
        profile = StudentProfile.objects.filter(user=user).first()
    target_career = profile.career_goal.strip() if (profile and profile.career_goal) else ""

    first_initial = (user.first_name[:1] if user.first_name else user.username[:1]).upper()
    last_initial = (user.last_name[:1] if user.last_name else "").upper()
    user_initials = f"{first_initial}{last_initial}" if last_initial else (user.username[:2].upper())

    return {
        'profile': profile,
        'target_career': target_career,
        'user_initials': user_initials,
    }


@method_decorator(login_required, name='dispatch')
class CareerPathListView(ListView):
    model = CareerPath
    template_name = 'roadmaps/path_list.html'
    context_object_name = 'paths'

    def get_queryset(self):
        return CareerPath.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_ctx = _get_user_display_context(self.request.user)
        context.update(user_ctx)
        target_career = user_ctx['target_career']
        profile = user_ctx['profile']

        if self.request.user.is_authenticated:
            enrollments = UserRoadmap.objects.filter(
                user=self.request.user
            ).select_related('career_path')
            
            # Map progress and categorize into in-progress vs completed
            progress_map = {}
            completed_enrollments = []
            in_progress_enrollments = []
            
            for enrollment in enrollments:
                p = enrollment.progress_percentage()
                progress_map[enrollment.career_path_id] = p
                if p >= 100:
                    completed_enrollments.append(enrollment)
                else:
                    in_progress_enrollments.append(enrollment)

            context['enrollments'] = enrollments
            context['in_progress_enrollments'] = in_progress_enrollments
            context['completed_enrollments'] = completed_enrollments
            context['enrolled_ids'] = list(enrollments.values_list('career_path_id', flat=True))
            context['progress_map'] = progress_map
            context['completed_path_ids'] = [e.career_path_id for e in completed_enrollments]
            context['in_progress_path_ids'] = [e.career_path_id for e in in_progress_enrollments]

            # Deterministic Primary Active Roadmap Selection
            # 1. Match StudentProfile career_goal to an enrolled CareerPath
            # 2. Fallback to preferred_domain match
            # 3. Fallback to most recently started active enrollment
            active_enrollments = list(enrollments.filter(is_active=True).select_related('career_path'))
            primary_enrollment = None

            if target_career and active_enrollments:
                for enr in active_enrollments:
                    if enr.career_path.name.strip().lower() == target_career.lower() or target_career.lower() in enr.career_path.name.lower():
                        primary_enrollment = enr
                        break
                if not primary_enrollment and profile and profile.preferred_domain:
                    for enr in active_enrollments:
                        if profile.preferred_domain.lower() in enr.career_path.name.lower():
                            primary_enrollment = enr
                            break

            if not primary_enrollment and active_enrollments:
                active_enrollments.sort(key=lambda x: (x.started_at, x.id), reverse=True)
                primary_enrollment = active_enrollments[0]

            # Primary Active Roadmap Details & Sequential Journey
            roadmap_progress = 0
            roadmap_completed_count = 0
            roadmap_total_topics = 0
            is_roadmap_completed = False
            current_milestone = None
            current_topic = None
            milestone_journey = []
            secondary_enrollments = []

            if primary_enrollment:
                roadmap_progress = primary_enrollment.progress_percentage()
                roadmap_completed_count = primary_enrollment.completed_count()
                roadmap_total_topics = primary_enrollment.career_path.total_topics()
                is_roadmap_completed = bool(
                    roadmap_total_topics > 0 and roadmap_completed_count >= roadmap_total_topics
                )

                incomplete_prog = TopicProgress.objects.filter(
                    user_roadmap=primary_enrollment,
                    is_completed=False
                ).select_related('topic', 'topic__milestone').order_by(
                    'topic__milestone__order', 'topic__milestone__week_number', 'topic__order'
                ).first()

                if incomplete_prog:
                    current_milestone = incomplete_prog.topic.milestone
                    current_topic = incomplete_prog.topic

                # Build sequential milestone journey
                for ms in primary_enrollment.career_path.milestones.prefetch_related('topics').all():
                    ms_topics = list(ms.topics.all())
                    ms_total = len(ms_topics)
                    ms_topic_ids = [t.id for t in ms_topics]
                    ms_completed = TopicProgress.objects.filter(
                        user_roadmap=primary_enrollment,
                        topic_id__in=ms_topic_ids,
                        is_completed=True
                    ).count()

                    if is_roadmap_completed or (ms_total > 0 and ms_completed >= ms_total):
                        status = 'completed'
                    elif current_milestone and ms.id == current_milestone.id:
                        status = 'current'
                    else:
                        status = 'upcoming'

                    milestone_journey.append({
                        'id': ms.id,
                        'week_number': ms.week_number,
                        'title': ms.title,
                        'level': ms.level,
                        'status': status,
                        'total_topics': ms_total,
                        'completed_topics': ms_completed,
                    })

                # Secondary enrolled tracks
                secondary_enrollments = [e for e in enrollments if e.id != primary_enrollment.id]

            context['primary_enrollment'] = primary_enrollment
            context['roadmap_progress'] = roadmap_progress
            context['roadmap_completed_count'] = roadmap_completed_count
            context['roadmap_total_topics'] = roadmap_total_topics
            context['is_roadmap_completed'] = is_roadmap_completed
            context['current_milestone'] = current_milestone
            context['current_topic'] = current_topic
            context['milestone_journey'] = milestone_journey
            context['secondary_enrollments'] = secondary_enrollments

            # Reorder all paths so started roadmaps come at top
            all_paths = list(context['paths'])
            completed_ids_set = set(context['completed_path_ids'])
            in_progress_ids_set = set(context['in_progress_path_ids'])
            
            def sort_key(path):
                if path.id in in_progress_ids_set:
                    return 0
                elif path.id in completed_ids_set:
                    return 1
                return 2
            
            all_paths.sort(key=sort_key)

            # Annotate paths with helper attributes for template rendering
            target_career_path = None
            for p in all_paths:
                is_match = bool(target_career and (p.name.strip().lower() == target_career.lower() or target_career.lower() in p.name.lower()))
                p.matches_target_goal = is_match
                if is_match and not target_career_path:
                    target_career_path = p
                p.is_enrolled = (p.id in context['enrolled_ids'])
                p.progress_pct = progress_map.get(p.id, 0)
                p.is_completed = (p.id in completed_ids_set)

            context['paths'] = all_paths
            context['target_career_path'] = target_career_path

        return context


@method_decorator(login_required, name='dispatch')
class RoadmapDetailView(DetailView):
    model = CareerPath
    template_name = 'roadmaps/path_detail.html'
    context_object_name = 'path'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        path = self.object
        user_ctx = _get_user_display_context(self.request.user)
        context.update(user_ctx)

        milestones = path.milestones.prefetch_related('topics').all()
        context['milestones'] = milestones

        # Check enrollment
        user_roadmap = UserRoadmap.objects.filter(
            user=self.request.user, career_path=path
        ).first()
        context['user_roadmap'] = user_roadmap

        current_milestone = None
        current_topic = None
        is_roadmap_completed = False

        if user_roadmap:
            # Build a set of completed topic IDs for quick lookup
            completed_ids = set(
                TopicProgress.objects.filter(
                    user_roadmap=user_roadmap, is_completed=True
                ).values_list('topic_id', flat=True)
            )
            progress = user_roadmap.progress_percentage()
            completed_count = user_roadmap.completed_count()
            total_topics = path.total_topics()
            is_roadmap_completed = bool(total_topics > 0 and completed_count >= total_topics)

            # Find first incomplete topic
            incomplete_prog = TopicProgress.objects.filter(
                user_roadmap=user_roadmap,
                is_completed=False
            ).select_related('topic', 'topic__milestone').order_by(
                'topic__milestone__order', 'topic__milestone__week_number', 'topic__order'
            ).first()

            if incomplete_prog:
                current_milestone = incomplete_prog.topic.milestone
                current_topic = incomplete_prog.topic

            context['completed_ids'] = completed_ids
            context['progress'] = progress
            context['completed_count'] = completed_count
            context['total_topics'] = total_topics
        else:
            completed_ids = set()
            context['completed_ids'] = completed_ids
            context['progress'] = 0
            context['completed_count'] = 0
            context['total_topics'] = path.total_topics()

        # Build structured milestone data with status
        milestone_data = []
        for ms in milestones:
            ms_topics = list(ms.topics.all())
            ms_total = len(ms_topics)
            ms_topic_ids = [t.id for t in ms_topics]
            ms_completed = len(completed_ids.intersection(ms_topic_ids)) if user_roadmap else 0

            if is_roadmap_completed or (ms_total > 0 and ms_completed >= ms_total):
                status = 'completed'
            elif current_milestone and ms.id == current_milestone.id:
                status = 'current'
            else:
                status = 'upcoming'

            milestone_data.append({
                'milestone': ms,
                'status': status,
                'completed_count': ms_completed,
                'total_count': ms_total,
                'is_current': bool(current_milestone and ms.id == current_milestone.id),
            })

        context['milestone_data'] = milestone_data
        context['current_milestone'] = current_milestone
        context['current_topic'] = current_topic
        context['is_roadmap_completed'] = is_roadmap_completed

        return context


@login_required
def enroll_roadmap(request, slug):
    if request.method == 'POST':
        path = get_object_or_404(CareerPath, slug=slug, is_active=True)
        user_roadmap, created = UserRoadmap.objects.get_or_create(
            user=request.user,
            career_path=path
        )
        if created:
            # Create TopicProgress entries for all topics in this path
            topics = Topic.objects.filter(milestone__career_path=path)
            progress_objects = [
                TopicProgress(user_roadmap=user_roadmap, topic=topic)
                for topic in topics
            ]
            TopicProgress.objects.bulk_create(progress_objects)
            messages.success(request, f"You have enrolled in the {path.name} roadmap!")
        else:
            messages.info(request, f"You are already enrolled in the {path.name} roadmap.")
        return redirect('roadmaps:path_detail', slug=slug)
    return redirect('roadmaps:path_list')


@login_required
def toggle_topic(request, topic_id):
    if request.method == 'POST':
        topic = get_object_or_404(Topic, pk=topic_id)
        # Find user's roadmap for this topic's career path
        user_roadmap = get_object_or_404(
            UserRoadmap,
            user=request.user,
            career_path=topic.milestone.career_path
        )
        progress, created = TopicProgress.objects.get_or_create(
            user_roadmap=user_roadmap,
            topic=topic
        )
        # Toggle
        progress.is_completed = not progress.is_completed
        progress.completed_at = timezone.now() if progress.is_completed else None
        progress.save()

        # Check if this specific week (milestone) is now completely finished
        milestone = topic.milestone
        milestone_topic_ids = list(milestone.topics.values_list('id', flat=True))
        completed_milestone_topics_count = TopicProgress.objects.filter(
            user_roadmap=user_roadmap,
            topic_id__in=milestone_topic_ids,
            is_completed=True
        ).count()
        week_completed = (completed_milestone_topics_count == len(milestone_topic_ids)) and progress.is_completed

        return JsonResponse({
            'success': True,
            'is_completed': progress.is_completed,
            'progress_percentage': user_roadmap.progress_percentage(),
            'completed_count': user_roadmap.completed_count(),
            'total_topics': user_roadmap.career_path.total_topics(),
            'week_completed': week_completed,
            'week_number': milestone.week_number,
            'week_title': milestone.title,
        })
    return JsonResponse({'success': False}, status=405)


@method_decorator(login_required, name='dispatch')
class MyRoadmapView(ListView):
    model = UserRoadmap
    template_name = 'roadmaps/my_roadmap.html'
    context_object_name = 'enrollments'

    def get_queryset(self):
        return UserRoadmap.objects.filter(
            user=self.request.user
        ).select_related('career_path')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_get_user_display_context(self.request.user))
        return context
