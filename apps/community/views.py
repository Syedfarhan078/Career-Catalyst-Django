from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, TemplateView
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Count, Q, Avg
from django.urls import reverse
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
    save_mentor_availability_service
)
from .utils import calculate_mentor_match_score

User = get_user_model()


# --- COMMUNITY FORUM VIEWS (FROM SPRINT 22) ---

@method_decorator(login_required, name='dispatch')
class CommunityHubView(TemplateView):
    template_name = "community/hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_threads"] = ForumThread.objects.select_related('category', 'author').order_by('-created_at')[:3]
        context["active_mentors"] = MentorProfile.objects.filter(status='Approved', verified=True)[:4]
        context["recent_projects"] = SharedProject.objects.select_related('author').annotate(likes_count=Count('likes')).order_by('-created_at')[:3]
        context["recent_stories"] = SuccessStory.objects.all()[:3]
        
        user_likes = ProjectLike.objects.filter(user=self.request.user).values_list('project_id', flat=True)
        context["liked_project_ids"] = list(user_likes)
        return context


@method_decorator(login_required, name='dispatch')
class ForumListView(ListView):
    model = ForumThread
    template_name = "community/forum_list.html"
    context_object_name = "threads"
    paginate_by = 10

    def get_queryset(self):
        queryset = ForumThread.objects.select_related('category', 'author').annotate(replies_count=Count('replies'))
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = ForumCategory.objects.all()
        context["active_category"] = self.request.GET.get('category', '')
        return context


@method_decorator(login_required, name='dispatch')
class ForumThreadDetailView(DetailView):
    model = ForumThread
    template_name = "community/forum_detail.html"
    context_object_name = "thread"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["replies"] = self.object.replies.select_related('author').all()
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
    return render(request, "community/create_thread.html", {"categories": categories})


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
        return SharedProject.objects.select_related('author').annotate(likes_count=Count('likes'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_likes = ProjectLike.objects.filter(
            user=self.request.user
        ).values_list('project_id', flat=True)
        context["liked_project_ids"] = list(user_likes)
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

    return render(request, "community/share_project.html")


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


# --- MENTOR MARKETPLACE VIEWS ---

@method_decorator(login_required, name='dispatch')
class MarketplaceListView(ListView):
    model = MentorProfile
    template_name = "community/marketplace.html"
    context_object_name = "mentors"
    paginate_by = 9

    def get_queryset(self):
        # Only public visible approved mentors
        queryset = MentorProfile.objects.filter(status='Approved', verified=True)
        
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
        return context


@method_decorator(login_required, name='dispatch')
class MentorDetailView(DetailView):
    model = MentorProfile
    template_name = "community/mentor_detail.html"
    context_object_name = "mentor"

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

        return context


@login_required
def mentor_register(request):
    """
    Enables professional registration as a Mentor.
    If the user already has a MentorProfile, redirects them to their dashboard.
    """
    # Check if they already registered
    try:
        profile = request.user.mentor_profile
        if profile.status == 'Approved':
            return redirect('community:mentor_dashboard')
        else:
            return render(request, "community/mentor_status.html", {"profile": profile})
    except MentorProfile.DoesNotExist:
        pass

    if request.method == 'POST':
        form = MentorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            # Delegate to Business Logic Layer
            register_mentor_service(request.user, form.cleaned_data)
            messages.success(request, "Your application has been submitted and is pending verification.")
            return redirect('community:mentor_register')
    else:
        form = MentorRegistrationForm()

    return render(request, "community/mentor_register.html", {"form": form})


@login_required
def mentor_dashboard(request):
    """
    Dashboard for approved mentors showing analytics, booking history, and requests list.
    """
    # Ensure they are approved mentors
    mentor = get_object_or_404(MentorProfile, user=request.user)
    if mentor.status != 'Approved':
        return render(request, "community/mentor_status.html", {"profile": mentor})

    # Analytics calculation
    all_requests = MentorshipRequest.objects.filter(mentor=mentor)
    total_sessions = all_requests.filter(status='Completed').count()
    upcoming_sessions = all_requests.filter(status='Accepted').count()
    pending_sessions = all_requests.filter(status='Pending').count()
    
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
        "recent_requests": recent_requests,
        "recent_reviews": recent_reviews,
        "profile_completion": profile_completion
    })


@login_required
def edit_mentor_profile(request):
    mentor = get_object_or_404(MentorProfile, user=request.user)
    
    if request.method == 'POST':
        form = MentorProfileEditForm(request.POST, instance=mentor)
        if form.is_valid():
            # Delegate to Business Services
            update_mentor_profile_service(mentor, form.cleaned_data)
            messages.success(request, "Profile updated successfully.")
            return redirect('community:mentor_dashboard')
    else:
        form = MentorProfileEditForm(instance=mentor, initial={'skills_csv': mentor.skills})

    return render(request, "community/edit_mentor_profile.html", {"form": form, "mentor": mentor})


@login_required
def manage_availability(request):
    mentor = get_object_or_404(MentorProfile, user=request.user)
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
        "mentor": mentor
    })


@login_required
def delete_availability(request, pk):
    mentor = get_object_or_404(MentorProfile, user=request.user)
    avail = get_object_or_404(MentorAvailability, pk=pk, mentor=mentor)
    avail.delete()
    messages.success(request, "Availability slot deleted.")
    return redirect('community:manage_availability')


@login_required
def book_mentorship_session(request, mentor_id):
    """
    POST-only endpoint for booking sessions.
    """
    if request.method == 'POST':
        mentor = get_object_or_404(MentorProfile, pk=mentor_id)
        
        # Prevent self-booking
        if mentor.user == request.user:
            messages.error(request, "You cannot book a session with yourself.")
            return redirect('community:mentor_detail', pk=mentor.id)

        form = MentorshipBookingForm(request.POST)
        if form.is_valid():
            # Delegate to Business Logic Layer
            create_mentorship_request_service(request.user, mentor, form.cleaned_data)
            messages.success(request, "Mentorship request sent successfully! Track it in your booking history.")
        else:
            messages.error(request, "Error in booking form fields. Please select valid date/times.")
        return redirect('community:mentor_detail', pk=mentor.id)
    return HttpResponseForbidden()


@login_required
def mentor_requests_list(request):
    mentor = get_object_or_404(MentorProfile, user=request.user)
    requests_received = MentorshipRequest.objects.filter(mentor=mentor)
    
    return render(request, "community/mentor_requests.html", {
        "requests": requests_received,
        "mentor": mentor
    })


@login_required
def respond_to_request(request, pk):
    """
    Mentor accepts, rejects, or completes a student booking.
    """
    mentor = get_object_or_404(MentorProfile, user=request.user)
    req = get_object_or_404(MentorshipRequest, pk=pk, mentor=mentor)

    if request.method == 'POST':
        action = request.POST.get('action') # 'accept', 'reject', 'complete'
        message = request.POST.get('response_message', '').strip()
        link = request.POST.get('meeting_link', '').strip()
        
        # Delegate to Business Logic Layer
        respond_to_request_service(
            req, 
            action, 
            response_message=message, 
            meeting_link=link
        )
        messages.success(request, f"Request successfully marked as {action}ed.")
        return redirect('community:mentor_requests')
    return HttpResponseForbidden()


@login_required
def student_bookings_list(request):
    bookings = MentorshipRequest.objects.filter(student=request.user)
    review_form = MentorReviewForm()
    
    return render(request, "community/student_bookings.html", {
        "bookings": bookings,
        "review_form": review_form
    })


@login_required
def cancel_student_booking(request, pk):
    req = get_object_or_404(MentorshipRequest, pk=pk, student=request.user)
    if req.status in ['Pending', 'Accepted']:
        # Delegate to Business Services
        respond_to_request_service(req, 'cancel', "Cancelled by student.")
        messages.success(request, "Session cancelled.")
    else:
        messages.error(request, "You cannot cancel this session.")
    return redirect('community:student_bookings')


@login_required
def submit_mentor_review(request, mentor_id):
    if request.method == 'POST':
        mentor = get_object_or_404(MentorProfile, pk=mentor_id)
        form = MentorReviewForm(request.POST)
        if form.is_valid():
            # Delegate to Business Services
            submit_mentor_review_service(
                request.user, 
                mentor, 
                form.cleaned_data['rating'], 
                form.cleaned_data['comment']
            )
            messages.success(request, "Thank you! Your feedback has been recorded.")
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
        
    pending_mentors = MentorProfile.objects.filter(status='Pending')
    all_mentors = MentorProfile.objects.exclude(status='Pending')
    
    return render(request, "community/admin_verify.html", {
        "pending": pending_mentors,
        "all_mentors": all_mentors
    })


@login_required
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
    mentor = get_object_or_404(User, pk=mentor_id)
    profile = get_object_or_404(MentorProfile, user=mentor)
    
    messages_query = MentorMessage.objects.filter(
        (models.Q(sender=request.user) & models.Q(recipient=mentor)) |
        (models.Q(sender=mentor) & models.Q(recipient=request.user))
    ).order_by('sent_at')

    messages_query.filter(recipient=request.user, is_read=False).update(is_read=True)

    return render(request, "community/mentor_chat.html", {
        "mentor": mentor,
        "profile": profile,
        "chat_messages": messages_query
    })


@login_required
def send_mentor_message(request, mentor_id):
    if request.method == 'POST':
        mentor = get_object_or_404(User, pk=mentor_id)
        profile = get_object_or_404(MentorProfile, user=mentor)
        
        import json
        data = json.loads(request.body)
        content = data.get("content", "").strip()

        if not content:
            return JsonResponse({"error": "Message content cannot be empty."}, status=400)

        user_msg = MentorMessage.objects.create(
            sender=request.user,
            recipient=mentor,
            content=content
        )

        mentor_response_txt = f"Hello {request.user.username}! Thanks for reaching out. As a {profile.job_title} at {profile.company}, I'd be happy to guide you on this path. What specific learning milestone or project query are you tackling right now?"
        
        mentor_msg = MentorMessage.objects.create(
            sender=mentor,
            recipient=request.user,
            content=mentor_response_txt
        )

        return JsonResponse({
            "success": True,
            "messages": [
                {
                    "sender": "Candidate",
                    "content": user_msg.content,
                    "sent_at": user_msg.sent_at.strftime("%I:%M %p")
                },
                {
                    "sender": "Mentor",
                    "content": mentor_msg.content,
                    "sent_at": mentor_msg.sent_at.strftime("%I:%M %p")
                }
            ]
        })
    return JsonResponse({"error": "POST method required"}, status=405)
