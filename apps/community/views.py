from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, TemplateView
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.contrib import messages
from django.db.models import Count, Q, Avg
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.conf import settings
from functools import wraps
import json

from .models import (
    ForumCategory, ForumThread, ForumReply, SharedProject, ProjectLike, 
    SuccessStory, MentorMessage, MentorProfile, MentorSkill, 
    MentorshipRequest, MentorReview, MentorAvailability
)
from apps.profiles.models import StudentProfile
from django.contrib.auth import get_user_model

# Import Clean Architecture Layer
from .forms import (
    MentorRegistrationForm, MentorProfileEditForm, MentorshipBookingForm, 
    MentorReviewForm, MentorAvailabilityForm
)
from .services import (
    register_mentor_service, update_mentor_profile_service, 
    review_mentor_application_service, create_mentorship_request_service, 
    respond_to_request_service, submit_mentor_review_service, 
    save_mentor_availability_service,
    pause_mentor_availability_service, resume_mentor_availability_service,
    get_mentor_step_down_readiness, execute_mentor_step_down_service,
    reactivate_mentor_service
)
from .utils import calculate_mentor_match_score

User = get_user_model()


def get_user_sidebar_context(user):
    """
    Helper to provide consistent sidebar user badge and career context
    across the Community & Mentors workspace.
    """
    if not user or not user.is_authenticated:
        return {'profile': None, 'user_initials': '', 'target_career': ''}
    profile = getattr(user, 'studentprofile', None)
    first_initial = (user.first_name[:1] if user.first_name else user.username[:1]).upper()
    last_initial = (user.last_name[:1] if user.last_name else "").upper()
    user_initials = f"{first_initial}{last_initial}" if last_initial else (user.username[:2].upper())
    target_career = profile.career_goal.strip() if (profile and profile.career_goal) else ""
    return {
        'profile': profile,
        'user_initials': user_initials,
        'target_career': target_career,
    }


def mentor_required(view_func):
    """
    Decorator ensuring the user is authenticated and is an Approved & Verified mentor.
    Redirects unapproved, pending, rejected, or blocked users to the mentor status / register page.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        if not hasattr(request.user, 'mentor_profile'):
            messages.info(request, "Please register to become a mentor first.")
            return redirect('community:mentor_register')
        mentor = request.user.mentor_profile
        if mentor.status != 'Approved' or not mentor.verified:
            ctx = get_user_sidebar_context(request.user)
            ctx['profile'] = mentor
            ctx['mentor_profile'] = mentor
            return render(request, "community/mentor_status.html", ctx)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# --- COMMUNITY FORUM VIEWS (FROM SPRINT 22) ---

@method_decorator(login_required, name='dispatch')
class CommunityHubView(TemplateView):
    template_name = "community/hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_threads"] = ForumThread.objects.select_related('category', 'author', 'author__mentor_profile').order_by('-created_at')[:3]
        context["active_mentors"] = MentorProfile.objects.filter(status='Approved', verified=True, is_paused=False).select_related('user')[:4]
        context["recent_projects"] = SharedProject.objects.select_related('author').annotate(likes_count=Count('likes')).order_by('-created_at')[:3]
        context["recent_stories"] = SuccessStory.objects.all()[:3]
        
        user_likes = ProjectLike.objects.filter(user=self.request.user).values_list('project_id', flat=True)
        context["liked_project_ids"] = list(user_likes)
        context.update(get_user_sidebar_context(self.request.user))
        return context


@method_decorator(login_required, name='dispatch')
class ForumListView(ListView):
    model = ForumThread
    template_name = "community/forum_list.html"
    context_object_name = "threads"
    paginate_by = 10

    def get_queryset(self):
        queryset = ForumThread.objects.select_related('category', 'author', 'author__mentor_profile').annotate(replies_count=Count('replies')).order_by('-created_at')
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = ForumCategory.objects.all()
        context["active_category"] = self.request.GET.get('category', '')
        context.update(get_user_sidebar_context(self.request.user))
        return context


@method_decorator(login_required, name='dispatch')
class ForumThreadDetailView(DetailView):
    model = ForumThread
    template_name = "community/forum_detail.html"
    context_object_name = "thread"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["replies"] = self.object.replies.select_related('author', 'author__mentor_profile').all()
        context.update(get_user_sidebar_context(self.request.user))
        return context


@login_required
def create_thread(request):
    if request.method == 'POST':
        category_id = request.POST.get('category')
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()

        if not category_id or not title or not content:
            messages.error(request, "All fields are required to start a thread.")
            return redirect('community:create_thread')

        category = get_object_or_404(ForumCategory, pk=category_id)
        thread = ForumThread.objects.create(
            category=category,
            title=title,
            content=content,
            author=request.user
        )
        messages.success(request, f"Your discussion thread '{title}' has been posted!")
        return redirect('community:forum_detail', pk=thread.pk)

    categories = ForumCategory.objects.all()
    context = {"categories": categories, **get_user_sidebar_context(request.user)}
    return render(request, "community/create_thread.html", context)


@login_required
def add_reply(request, pk):
    if request.method == 'POST':
        thread = get_object_or_404(ForumThread, pk=pk)
        content = request.POST.get('content', '').strip()

        if content:
            ForumReply.objects.create(
                thread=thread,
                content=content,
                author=request.user
            )
            messages.success(request, "Your reply has been posted.")
        else:
            messages.error(request, "Reply content cannot be empty.")
        return redirect('community:forum_detail', pk=thread.pk)
    return redirect('community:forum_list')


# --- PROJECTS & SUCCESS STORIES ---

@method_decorator(login_required, name='dispatch')
class ProjectListView(ListView):
    model = SharedProject
    template_name = "community/projects.html"
    context_object_name = "projects"
    paginate_by = 10

    def get_queryset(self):
        return SharedProject.objects.select_related('author').annotate(likes_count=Count('likes')).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_likes = ProjectLike.objects.filter(
            user=self.request.user
        ).values_list('project_id', flat=True)
        context["liked_project_ids"] = list(user_likes)
        context.update(get_user_sidebar_context(self.request.user))
        return context


@login_required
def share_project(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        github_link = request.POST.get('github_link', '').strip()
        live_link = request.POST.get('live_link', '').strip()
        tags = request.POST.get('tags', '').strip()

        if not title or not description:
            messages.error(request, "Title and description are required fields.")
            return redirect('community:share_project')

        project = SharedProject.objects.create(
            title=title,
            description=description,
            github_link=github_link,
            live_link=live_link,
            tags=tags,
            author=request.user
        )
        messages.success(request, f"Your project '{title}' has been shared successfully!")
        return redirect('community:project_list')

    return render(request, "community/share_project.html", get_user_sidebar_context(request.user))


@login_required
def toggle_like_project(request, pk):
    if request.method == 'POST':
        project = get_object_or_404(SharedProject, pk=pk)
        like_rel = ProjectLike.objects.filter(user=request.user, project=project)

        if like_rel.exists():
            like_rel.delete()
            is_liked = False
        else:
            ProjectLike.objects.create(user=request.user, project=project)
            is_liked = True

        total_likes = project.likes.count()

        return JsonResponse({
            "success": True,
            "is_liked": is_liked,
            "likes_count": total_likes
        })
    return JsonResponse({"error": "POST method required"}, status=405)


@method_decorator(login_required, name='dispatch')
class SuccessStoryListView(ListView):
    model = SuccessStory
    template_name = "community/stories.html"
    context_object_name = "stories"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_user_sidebar_context(self.request.user))
        return context


# --- MENTOR MARKETPLACE VIEWS ---

@method_decorator(login_required, name='dispatch')
class MarketplaceListView(ListView):
    model = MentorProfile
    template_name = "community/marketplace.html"
    context_object_name = "mentors"
    paginate_by = 9

    def get_queryset(self):
        # Only public visible approved and unpaused mentors
        queryset = MentorProfile.objects.filter(status='Approved', verified=True, is_paused=False).select_related('user').prefetch_related('mentor_skills')
        
        # Advanced Filtering
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(full_name__icontains=search_query) |
                Q(company__icontains=search_query) |
                Q(designation__icontains=search_query) |
                Q(skills__icontains=search_query)
            )

        domain = self.request.GET.get('domain', '').strip()
        if domain:
            queryset = queryset.filter(career_domains__icontains=domain)

        company = self.request.GET.get('company', '').strip()
        if company:
            queryset = queryset.filter(company__iexact=company)

        skill = self.request.GET.get('skill', '').strip()
        if skill:
            queryset = queryset.filter(mentor_skills__name__iexact=skill)

        min_exp = self.request.GET.get('experience', '').strip()
        if min_exp.isdigit():
            queryset = queryset.filter(experience_years__gte=int(min_exp))

        min_rating = self.request.GET.get('rating', '').strip()
        if min_rating:
            try:
                queryset = queryset.filter(rating__gte=float(min_rating))
            except ValueError:
                pass

        location = self.request.GET.get('location', '').strip()
        if location:
            queryset = queryset.filter(current_location__icontains=location)

        # Sorting
        sort_by = self.request.GET.get('sort', '').strip()
        if sort_by == 'highest_rated':
            queryset = queryset.order_by('-rating')
        elif sort_by == 'most_experienced':
            queryset = queryset.order_by('-experience_years')
        elif sort_by == 'newest':
            queryset = queryset.order_by('-created_at')

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get StudentProfile if available to calculate match scores
        student_profile = None
        try:
            student_profile = self.request.user.studentprofile
        except StudentProfile.DoesNotExist:
            pass

        # Calculate recommended match score for each mentor object
        mentors_list = list(context["mentors"])
        for mentor in mentors_list:
            if student_profile:
                mentor.match_score = calculate_mentor_match_score(student_profile, mentor)
            else:
                mentor.match_score = None
        
        # Re-sort list by recommended score if selected
        sort_by = self.request.GET.get('sort', '').strip()
        if sort_by == 'recommended' and student_profile:
            mentors_list.sort(key=lambda m: m.match_score or 0.0, reverse=True)
            context["mentors"] = mentors_list

        # Filter lists for layout widgets
        context["all_domains"] = ["Frontend", "Backend", "Full Stack", "Data Science", "Machine Learning", "DevOps", "Cyber Security", "Product Management", "System Design"]
        context["current_filters"] = self.request.GET.dict()
        context.update(get_user_sidebar_context(self.request.user))
        return context


@method_decorator(login_required, name='dispatch')
class MentorDetailView(DetailView):
    model = MentorProfile
    template_name = "community/mentor_detail.html"
    context_object_name = "mentor"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.status != 'Approved' or not obj.verified:
            user = self.request.user
            if not user.is_authenticated or (user != obj.user and not user.is_staff):
                raise Http404("Mentor profile is not currently public.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["availabilities"] = self.object.availabilities.all()
        context["reviews"] = self.object.reviews.select_related('student').all()
        context["booking_form"] = MentorshipBookingForm()
        
        # Calculate Match Score
        student_profile = None
        try:
            student_profile = self.request.user.studentprofile
        except StudentProfile.DoesNotExist:
            pass

        if student_profile:
            context["match_score"] = calculate_mentor_match_score(student_profile, self.object)
        else:
            context["match_score"] = None

        # Check for accepted bookings to enable messaging
        if self.request.user.is_authenticated:
            context["has_accepted_booking"] = MentorshipRequest.objects.filter(
                student=self.request.user,
                mentor=self.object,
                status='Accepted'
            ).exists()
        else:
            context["has_accepted_booking"] = False

        context.update(get_user_sidebar_context(self.request.user))
        return context


@login_required
def mentor_register(request):
    """
    Enables professional registration as a Mentor.
    If already approved, redirects to mentor dashboard.
    If pending or blocked, shows status.
    If rejected, shows status unless reapply=1 or submitting POST.
    """
    existing_profile = getattr(request.user, 'mentor_profile', None)
    if existing_profile:
        if existing_profile.status == 'Approved':
            return redirect('community:mentor_dashboard')
        elif existing_profile.status in ['Pending', 'Blocked', 'Inactive']:
            ctx = get_user_sidebar_context(request.user)
            ctx['profile'] = existing_profile
            ctx['mentor_profile'] = existing_profile
            return render(request, "community/mentor_status.html", ctx)
        elif existing_profile.status == 'Rejected':
            # Only show form if explicitly reapplying via GET param or submitting POST
            if request.method == 'GET' and request.GET.get('reapply') != '1':
                ctx = get_user_sidebar_context(request.user)
                ctx['profile'] = existing_profile
                ctx['mentor_profile'] = existing_profile
                return render(request, "community/mentor_status.html", ctx)

    if request.method == 'POST':
        form = MentorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            register_mentor_service(request.user, form.cleaned_data)
            messages.success(request, "Your application has been submitted and is pending verification.")
            return redirect('community:mentor_register')
    else:
        if existing_profile and existing_profile.status == 'Rejected':
            form = MentorRegistrationForm(
                instance=existing_profile,
                initial={
                    'skills_csv': existing_profile.skills,
                    'agreement': False
                }
            )
        else:
            form = MentorRegistrationForm()

    return render(request, "community/mentor_register.html", {
        "form": form,
        **get_user_sidebar_context(request.user)
    })


@login_required
def switch_workspace(request):
    """
    Switches active workspace between Student and Mentor.
    Validates mentor status before allowing 'mentor' role.
    """
    role = request.GET.get('role') or request.POST.get('role')
    if role == 'mentor':
        if hasattr(request.user, 'mentor_profile') and request.user.mentor_profile.status == 'Approved' and request.user.mentor_profile.verified:
            request.session['active_role'] = 'mentor'
            messages.success(request, "Switched to Mentor Workspace.")
            return redirect('community:mentor_dashboard')
        else:
            messages.error(request, "You must be an approved mentor to access the Mentor Workspace.")
            request.session['active_role'] = 'student'
            return redirect('dashboard')
    else:
        request.session['active_role'] = 'student'
        messages.success(request, "Switched to Student Workspace.")
        return redirect('dashboard')


@login_required
@mentor_required
def mentor_dashboard(request):
    """
    Dashboard for approved mentors showing analytics, booking history, and requests list.
    """
    request.session['active_role'] = 'mentor'
    mentor = request.user.mentor_profile

    # Analytics calculation
    all_requests = MentorshipRequest.objects.filter(mentor=mentor).select_related('student')
    total_sessions = all_requests.filter(status='Completed').count()
    upcoming_sessions = all_requests.filter(status='Accepted').count()
    pending_sessions = all_requests.filter(status='Pending').count()
    active_mentees = all_requests.filter(status='Accepted').values('student').distinct().count()
    
    recent_requests = all_requests.filter(status='Pending')[:5]
    recent_reviews = mentor.reviews.select_related('student').all()[:5]

    # Simple completeness check
    fields = ['profile_photo', 'linkedin_url', 'github_url', 'portfolio_url', 'bio']
    filled = sum(1 for f in fields if getattr(mentor, f))
    profile_completion = int((filled / len(fields)) * 100)

    return render(request, "community/mentor_dashboard.html", {
        "mentor": mentor,
        "total_sessions": total_sessions,
        "upcoming_sessions": upcoming_sessions,
        "pending_sessions": pending_sessions,
        "active_mentees": active_mentees,
        "recent_requests": recent_requests,
        "recent_reviews": recent_reviews,
        "profile_completion": profile_completion,
        **get_user_sidebar_context(request.user)
    })


@login_required
@mentor_required
def mentor_mentees_view(request):
    """
    Dedicated view for mentors to track active and historical mentees.
    Displays candidates with Accepted or Completed requests.
    """
    request.session['active_role'] = 'mentor'
    mentor = request.user.mentor_profile
    requests_qs = MentorshipRequest.objects.filter(
        mentor=mentor,
        status__in=['Accepted', 'Completed']
    ).select_related('student', 'student__studentprofile').order_by('-requested_date', '-requested_time')

    filter_status = request.GET.get('filter', 'all')
    if filter_status == 'active':
        requests_qs = requests_qs.filter(status='Accepted')
    elif filter_status == 'completed':
        requests_qs = requests_qs.filter(status='Completed')

    active_mentees_count = MentorshipRequest.objects.filter(
        mentor=mentor,
        status='Accepted'
    ).values('student').distinct().count()

    total_completed_count = MentorshipRequest.objects.filter(
        mentor=mentor,
        status='Completed'
    ).count()

    return render(request, "community/mentor_mentees.html", {
        "mentor": mentor,
        "mentorships": requests_qs,
        "active_mentees_count": active_mentees_count,
        "total_completed_count": total_completed_count,
        "current_filter": filter_status,
        **get_user_sidebar_context(request.user)
    })


# ==========================================
# PHASE 4: MENTOR LIFECYCLE ENDPOINTS
# ==========================================

@login_required
@mentor_required
@require_POST
def pause_availability_view(request):
    """
    POST-only endpoint allowing approved mentors to temporarily pause new incoming requests.
    """
    pause_mentor_availability_service(request.user)
    messages.info(request, "Your mentorship availability is now paused. New booking requests are stopped, while existing sessions remain active.")
    return redirect('community:mentor_dashboard')


@login_required
@mentor_required
@require_POST
def resume_availability_view(request):
    """
    POST-only endpoint allowing approved mentors to resume availability in the marketplace.
    """
    resume_mentor_availability_service(request.user)
    messages.success(request, "Your mentorship availability has resumed. Your profile is now visible for new bookings in the directory.")
    return redirect('community:mentor_dashboard')


@login_required
@mentor_required
def mentor_step_down_view(request):
    """
    Step-down workflow view.
    GET: Displays step-down confirmation page with outstanding sessions and readiness status.
    POST: Validates that no accepted sessions remain, automatically cancels pending requests,
          transitions status to 'Inactive', and returns the user to Student Workspace.
    """
    readiness = get_mentor_step_down_readiness(request.user)
    mentor = request.user.mentor_profile

    if request.method == 'POST':
        try:
            execute_mentor_step_down_service(request.user, reason=request.POST.get('reason', ''))
            request.session['active_role'] = 'student'
            messages.success(request, "You have stepped down from the mentor role. Your profile is now inactive and can be reactivated at any time.")
            return redirect('dashboard')
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
            return redirect('community:mentor_step_down')

    return render(request, "community/mentor_step_down.html", {
        "mentor": mentor,
        "readiness": readiness,
        "eligible": readiness['eligible'],
        "accepted_sessions": readiness['accepted_sessions'],
        "pending_requests": readiness['pending_requests'],
        "accepted_count": readiness['accepted_count'],
        "pending_count": readiness['pending_count'],
        **get_user_sidebar_context(request.user)
    })


@login_required
@require_POST
def reactivate_mentor_view(request):
    """
    POST-only endpoint allowing previously approved, stepped-down mentors to self-reactivate.
    Restores approved status, verified state, and mentor workspace access.
    """
    try:
        resume_bookings = (request.POST.get('resume_bookings', '1') == '1')
        mentor = reactivate_mentor_service(request.user, resume_bookings=resume_bookings)
        request.session['active_role'] = 'mentor'
        messages.success(request, "Welcome back! Your mentor profile has been reactivated.")
        return redirect('community:mentor_dashboard')
    except ValidationError as e:
        messages.error(request, e.message if hasattr(e, 'message') else str(e))
        return redirect('dashboard')


@login_required
@mentor_required
def edit_mentor_profile(request):
    mentor = request.user.mentor_profile
    
    if request.method == 'POST':
        form = MentorProfileEditForm(request.POST, instance=mentor)
        if form.is_valid():
            # Delegate to Business Services
            update_mentor_profile_service(mentor, form.cleaned_data)
            messages.success(request, "Profile updated successfully.")
            return redirect('community:mentor_dashboard')
    else:
        form = MentorProfileEditForm(instance=mentor, initial={'skills_csv': mentor.skills})

    return render(request, "community/edit_mentor_profile.html", {"form": form, "mentor": mentor, **get_user_sidebar_context(request.user)})


@login_required
@mentor_required
def manage_availability(request):
    mentor = request.user.mentor_profile
    availabilities = mentor.availabilities.all()

    if request.method == 'POST':
        form = MentorAvailabilityForm(request.POST)
        if form.is_valid():
            # Delegate to Business Logic Layer
            save_mentor_availability_service(
                mentor,
                form.cleaned_data['day'],
                form.cleaned_data['start_time'],
                form.cleaned_data['end_time'],
                form.cleaned_data['max_sessions']
            )
            messages.success(request, "Availability slot added successfully.")
            return redirect('community:manage_availability')
    else:
        form = MentorAvailabilityForm()

    return render(request, "community/manage_availability.html", {
        "form": form,
        "availabilities": availabilities,
        "mentor": mentor,
        **get_user_sidebar_context(request.user)
    })


@login_required
@require_POST
@mentor_required
def delete_availability(request, pk):
    mentor = request.user.mentor_profile
    avail = get_object_or_404(MentorAvailability, pk=pk, mentor=mentor)
    avail.delete()
    messages.success(request, "Availability slot deleted.")
    return redirect('community:manage_availability')


@login_required
def book_mentorship_session(request, mentor_id):
    """
    POST-only endpoint for booking sessions.
    Validates mentor status and handles business validation errors.
    """
    if request.method == 'POST':
        mentor = get_object_or_404(MentorProfile, pk=mentor_id)

        if mentor.status != 'Approved' or not mentor.verified:
            messages.error(request, "This mentor is not currently accepting mentorship bookings.")
            return redirect('community:mentor_list')

        if mentor.is_paused:
            messages.error(request, f"{mentor.full_name} has temporarily paused accepting new mentorship bookings.")
            return redirect('community:mentor_detail', pk=mentor.id)

        # Prevent self-booking
        if mentor.user == request.user:
            messages.error(request, "You cannot book a session with yourself.")
            return redirect('community:mentor_detail', pk=mentor.id)

        form = MentorshipBookingForm(request.POST)
        if form.is_valid():
            try:
                create_mentorship_request_service(request.user, mentor, form.cleaned_data)
                messages.success(request, "Mentorship request sent successfully! Track it in your booking history.")
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
        return redirect('community:mentor_detail', pk=mentor.id)
    return HttpResponseForbidden()


@login_required
@mentor_required
def mentor_requests_list(request):
    mentor = request.user.mentor_profile
    requests_received = MentorshipRequest.objects.filter(mentor=mentor).select_related('student')
    
    return render(request, "community/mentor_requests.html", {
        "requests": requests_received,
        "mentor": mentor,
        **get_user_sidebar_context(request.user)
    })


@login_required
@mentor_required
def respond_to_request(request, pk):
    """
    Mentor accepts, rejects, or completes a student booking.
    """
    mentor = request.user.mentor_profile
    req = get_object_or_404(MentorshipRequest, pk=pk, mentor=mentor)

    if request.method == 'POST':
        action = request.POST.get('action') # 'accept', 'reject', 'complete'
        message = request.POST.get('response_message', '').strip()
        link = request.POST.get('meeting_link', '').strip()

        try:
            respond_to_request_service(
                req, 
                action, 
                response_message=message, 
                meeting_link=link,
                actor=request.user
            )
            messages.success(request, f"Request successfully marked as {action}ed.")
        except (ValidationError, ValueError) as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
        return redirect('community:mentor_requests')
    return HttpResponseForbidden()


@login_required
def student_bookings_list(request):
    bookings = MentorshipRequest.objects.filter(student=request.user).select_related('mentor', 'mentor__user')
    review_form = MentorReviewForm()
    
    return render(request, "community/student_bookings.html", {
        "bookings": bookings,
        "review_form": review_form,
        **get_user_sidebar_context(request.user)
    })


@login_required
@require_POST
def cancel_student_booking(request, pk):
    req = get_object_or_404(MentorshipRequest, pk=pk, student=request.user)
    if req.status in ['Pending', 'Accepted']:
        try:
            respond_to_request_service(req, 'cancel', "Cancelled by student.", actor=request.user)
            messages.success(request, "Session cancelled.")
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
    else:
        messages.error(request, "You cannot cancel this session.")
    return redirect('community:student_bookings')


@login_required
def submit_mentor_review(request, mentor_id):
    if request.method == 'POST':
        mentor = get_object_or_404(MentorProfile, pk=mentor_id)
        form = MentorReviewForm(request.POST)
        if form.is_valid():
            try:
                submit_mentor_review_service(
                    request.user, 
                    mentor, 
                    form.cleaned_data['rating'], 
                    form.cleaned_data['comment']
                )
                messages.success(request, "Thank you! Your feedback has been recorded.")
            except ValidationError as e:
                messages.error(request, e.message if hasattr(e, 'message') else str(e))
        else:
            messages.error(request, "Invalid review values.")
    return redirect('community:student_bookings')


# --- STAFF/ADMIN PORTAL VIEWS ---

@login_required
def admin_verification_dashboard(request):
    """
    Custom verification dashboard for staff members to Approve, Reject, or Block mentor profiles.
    """
    if not request.user.is_staff and not request.user.is_superuser:
        return HttpResponseForbidden("Access Denied.")
        
    pending_mentors = MentorProfile.objects.filter(status='Pending').select_related('user')
    all_mentors = MentorProfile.objects.exclude(status='Pending').select_related('user')
    
    return render(request, "community/admin_verify.html", {
        "pending": pending_mentors,
        "all_mentors": all_mentors,
        **get_user_sidebar_context(request.user)
    })


@login_required
@require_POST
def admin_action_mentor(request, pk, action):
    """
    Staff review action endpoint. Action values: 'approve', 'reject', 'block'
    """
    if not request.user.is_staff and not request.user.is_superuser:
        return HttpResponseForbidden("Access Denied.")

    profile = get_object_or_404(MentorProfile, pk=pk)
    
    # Delegate to Business Logic Layer
    review_mentor_application_service(profile, action, request.user)
    messages.success(request, f"Mentor '{profile.full_name}' status set to {profile.status}.")
    return redirect('community:admin_verify')


# --- INTER CONVERSATION CHAT PORTAL ---

@login_required
def mentor_chat_view(request, mentor_id):
    other_user = get_object_or_404(User, pk=mentor_id)

    if other_user == request.user:
        messages.error(request, "You cannot chat with yourself.")
        return redirect('community:mentor_list')

    # Restrict chat access to accepted bookings between the two participants
    accepted_request = MentorshipRequest.objects.filter(
        (Q(student=request.user, mentor__user=other_user) |
         Q(student=other_user, mentor__user=request.user)),
        status='Accepted'
    ).select_related('mentor', 'mentor__user', 'student').first()

    if not accepted_request:
        messages.error(request, "Chat access is locked until the booking request is accepted.")
        mentor_profile = getattr(other_user, 'mentor_profile', None)
        if mentor_profile:
            return redirect('community:mentor_detail', pk=mentor_profile.id)
        return redirect('community:student_bookings')

    mentor_profile = accepted_request.mentor

    messages_query = MentorMessage.objects.filter(
        (Q(sender=request.user) & Q(recipient=other_user)) |
        (Q(sender=other_user) & Q(recipient=request.user))
    ).order_by('sent_at')

    messages_query.filter(recipient=request.user, is_read=False).update(is_read=True)

    return render(request, "community/mentor_chat.html", {
        "other_user": other_user,
        "mentor": other_user,  # Backward compatibility
        "mentor_profile": mentor_profile,
        "profile": mentor_profile,
        "chat_messages": messages_query,
        "is_mentor": (request.user == mentor_profile.user),
        **get_user_sidebar_context(request.user)
    })


@login_required
def send_mentor_message(request, mentor_id):
    if request.method == 'POST':
        other_user = get_object_or_404(User, pk=mentor_id)

        if other_user == request.user:
            return JsonResponse({"error": "Cannot send messages to yourself."}, status=400)

        # Restrict message sending to accepted bookings
        accepted_request = MentorshipRequest.objects.filter(
            (Q(student=request.user, mentor__user=other_user) |
             Q(student=other_user, mentor__user=request.user)),
            status='Accepted'
        ).exists()

        if not accepted_request:
            return JsonResponse({"error": "Chat access is locked until the booking is accepted."}, status=403)

        try:
            data = json.loads(request.body)
        except (ValueError, json.JSONDecodeError):
            return JsonResponse({"error": "Invalid JSON."}, status=400)

        content = data.get("content", "").strip()

        if not content:
            return JsonResponse({"error": "Message content cannot be empty."}, status=400)

        user_msg = MentorMessage.objects.create(
            sender=request.user,
            recipient=other_user,
            content=content
        )

        return JsonResponse({
            "success": True,
            "message": {
                "sender": request.user.username,
                "content": user_msg.content,
                "sent_at": user_msg.sent_at.strftime("%I:%M %p")
            }
        })
    return JsonResponse({"error": "POST method required"}, status=405)
