from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages

from .models import CareerPath, Milestone, Topic, UserRoadmap, TopicProgress


@method_decorator(login_required, name='dispatch')
class CareerPathListView(ListView):
    model = CareerPath
    template_name = 'roadmaps/path_list.html'
    context_object_name = 'paths'

    def get_queryset(self):
        return CareerPath.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get user's active enrollments
        if self.request.user.is_authenticated:
            enrolled_ids = UserRoadmap.objects.filter(
                user=self.request.user
            ).values_list('career_path_id', flat=True)
            context['enrolled_ids'] = list(enrolled_ids)
        return context


@method_decorator(login_required, name='dispatch')
class RoadmapDetailView(DetailView):
    model = CareerPath
    template_name = 'roadmaps/path_detail.html'
    context_object_name = 'path'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        path = self.object
        milestones = path.milestones.prefetch_related('topics').all()
        context['milestones'] = milestones

        # Check enrollment
        user_roadmap = UserRoadmap.objects.filter(
            user=self.request.user, career_path=path
        ).first()
        context['user_roadmap'] = user_roadmap

        if user_roadmap:
            # Build a set of completed topic IDs for quick lookup
            completed_ids = set(
                TopicProgress.objects.filter(
                    user_roadmap=user_roadmap, is_completed=True
                ).values_list('topic_id', flat=True)
            )
            context['completed_ids'] = completed_ids
            context['progress'] = user_roadmap.progress_percentage()
            context['completed_count'] = user_roadmap.completed_count()
            context['total_topics'] = path.total_topics()
        else:
            context['completed_ids'] = set()
            context['progress'] = 0
            context['completed_count'] = 0
            context['total_topics'] = path.total_topics()

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

        return JsonResponse({
            'success': True,
            'is_completed': progress.is_completed,
            'progress_percentage': user_roadmap.progress_percentage(),
            'completed_count': user_roadmap.completed_count(),
            'total_topics': user_roadmap.career_path.total_topics(),
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
