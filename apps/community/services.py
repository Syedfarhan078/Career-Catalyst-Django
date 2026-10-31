from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Avg, Count
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from .models import (
    MentorProfile, MentorSkill, MentorshipRequest, MentorReview, 
    MentorAvailability, MentorMessage, MentorLifecycleEvent
)
from .utils import simulate_notification
from apps.notifications.services import create_notification

@transaction.atomic
def register_mentor_service(user, form_cleaned_data):
    """
    Creates a new MentorProfile for a user and sets it to 'Pending' verification.
    Also parses the skills_csv and populates MentorSkill models.
    Ensures user.role is set to 'mentor'.
    """
    if getattr(user, 'role', None) != 'mentor':
        user.role = 'mentor'
        user.save(update_fields=['role'])

    skills_csv = form_cleaned_data.pop('skills_csv', '')
    
    # Check if profile already exists, if so overwrite or update
    profile, created = MentorProfile.objects.update_or_create(
        user=user,
        defaults={
            'full_name': form_cleaned_data.get('full_name'),
            'email': form_cleaned_data.get('email'),
            'phone_number': form_cleaned_data.get('phone_number'),
            'company': form_cleaned_data.get('company'),
            'designation': form_cleaned_data.get('designation'),
            'experience_years': form_cleaned_data.get('experience_years'),
            'current_location': form_cleaned_data.get('current_location'),
            'bio': form_cleaned_data.get('bio'),
            'career_domains': form_cleaned_data.get('career_domains'),
            'skills': skills_csv,
            'linkedin_url': form_cleaned_data.get('linkedin_url', ''),
            'github_url': form_cleaned_data.get('github_url', ''),
            'portfolio_url': form_cleaned_data.get('portfolio_url', ''),
            'resume': form_cleaned_data.get('resume'),
            'languages': form_cleaned_data.get('languages'),
            'available_days': form_cleaned_data.get('available_days'),
            'available_time_slots': form_cleaned_data.get('available_time_slots'),
            'max_sessions_per_week': form_cleaned_data.get('max_sessions_per_week', 5),
            'mentorship_type': form_cleaned_data.get('mentorship_type', 'Online'),
            'status': 'Pending',
            'verified': False
        }
    )

    # Sync MentorSkill objects
    profile.mentor_skills.all().delete()
    skills_list = [s.strip() for s in skills_csv.split(',') if s.strip()]
    for skill_name in skills_list:
        MentorSkill.objects.create(mentor=profile, name=skill_name)

    # Send confirmation alert to user
    create_notification(
        recipient=user,
        title="Mentorship Registration Received",
        message="Your application has been received and is currently Pending Verification by admins.",
        notification_type="general",
        target_url=reverse('community:mentor_register')
    )
    simulate_notification(
        user=user,
        subject="Mentorship Registration Received",
        message="Your application has been received and is currently Pending Verification by admins."
    )
    
    return profile


@transaction.atomic
def update_mentor_profile_service(profile, form_cleaned_data):
    """
    Updates an existing MentorProfile and syncs MentorSkill models.
    """
    skills_csv = form_cleaned_data.pop('skills_csv', '')
    
    for key, value in form_cleaned_data.items():
        setattr(profile, key, value)
    
    profile.skills = skills_csv
    profile.save()

    # Sync MentorSkills
    profile.mentor_skills.all().delete()
    skills_list = [s.strip() for s in skills_csv.split(',') if s.strip()]
    for skill_name in skills_list:
        MentorSkill.objects.create(mentor=profile, name=skill_name)

    return profile


@transaction.atomic
def review_mentor_application_service(profile, action, reviewer):
    """
    Admin reviews a mentor application.
    action can be: 'approve', 'reject', 'block'
    Acquires row lock on MentorProfile first to maintain consistent lock ordering.
    """
    if not reviewer.is_staff and not reviewer.is_superuser:
        raise PermissionError("Only staff/admins can review mentor applications.")

    # 1. Row-lock MentorProfile first (consistent order: MentorProfile -> MentorshipRequest)
    profile = MentorProfile.objects.select_for_update().get(pk=profile.pk)
        
    if action == 'approve':
        profile.status = 'Approved'
        profile.verified = True
        subject = "Mentorship Profile Approved!"
        msg = f"Congratulations {profile.full_name}, your mentorship application has been approved and activated in the marketplace."
        n_type = 'mentorship_profile_approved'
        target = reverse('community:mentor_dashboard')
    elif action == 'reject':
        profile.status = 'Rejected'
        profile.verified = False
        subject = "Mentorship Profile Status Update"
        msg = f"Hello {profile.full_name}, your application was rejected. Please review your credentials and submit again."
        n_type = 'mentorship_profile_rejected'
        target = reverse('community:mentor_register')
    elif action == 'block':
        # Idempotency check: if already blocked, do not duplicate notifications or cancellations
        if profile.status == 'Blocked':
            return profile

        profile.status = 'Blocked'
        profile.verified = False
        subject = "Mentorship Account Blocked"
        msg = "Your mentor profile has been blocked by administrators due to policy violations."
        n_type = 'mentorship_profile_blocked'
        target = reverse('community:mentor_register')

        # 2. Retrieve and lock ALL active (Pending and Accepted) requests
        active_requests = MentorshipRequest.objects.select_for_update().filter(
            mentor=profile,
            status__in=['Pending', 'Accepted']
        )
        for req in active_requests:
            prev_status = req.status
            req.status = 'Cancelled'
            req.mentor_response = "Mentor account suspended by administrators."
            req.save(update_fields=['status', 'mentor_response'])
            create_notification(
                recipient=req.student,
                actor=reviewer,
                title="Mentorship Request Cancelled",
                message=f"Your {prev_status.lower()} mentorship session with {profile.full_name} was cancelled as the mentor account was blocked by administrators.",
                notification_type='mentorship_session_cancelled',
                target_url=reverse('community:student_bookings'),
                related_request=req
            )
            simulate_notification(
                user=req.student,
                subject="Mentorship Request Cancelled",
                message=f"Your {prev_status.lower()} mentorship session with {profile.full_name} was cancelled as the mentor account was blocked by administrators."
            )

        # Audit lifecycle event
        MentorLifecycleEvent.objects.create(
            mentor=profile,
            event_type='block',
            actor=reviewer,
            reason="Mentor account blocked by administrators due to policy violations."
        )
    else:
        raise ValueError(f"Invalid review action: {action}")
        
    profile.save()
    create_notification(
        recipient=profile.user,
        actor=reviewer,
        title=subject,
        message=msg,
        notification_type=n_type,
        target_url=target
    )
    simulate_notification(user=profile.user, subject=subject, message=msg)
    return profile


@transaction.atomic
def create_mentorship_request_service(student, mentor, form_cleaned_data):
    """
    Creates a new MentorshipRequest for a student to a mentor.
    Serializes concurrent bookings using select_for_update row locking.
    Enforces active mentor verification, self-booking prevention, duplicate pending request
    prevention, slot conflict prevention, weekly capacity, and declared availability.
    """
    # Concurrency Protection: acquire row-level lock on the mentor profile
    mentor = MentorProfile.objects.select_for_update().get(pk=mentor.pk)

    if mentor.status != 'Approved' or not mentor.verified:
        raise ValidationError("Cannot book a session with a mentor who is not currently active and approved.")

    if mentor.is_paused:
        raise ValidationError("This mentor has temporarily paused accepting new booking requests.")

    if mentor.user == student:
        raise ValidationError("You cannot book a mentorship session with yourself.")

    requested_date = form_cleaned_data.get('requested_date')
    requested_time = form_cleaned_data.get('requested_time')

    if requested_date < timezone.now().date():
        raise ValidationError("You cannot book a mentorship session for a past date.")

    # 1. Prevent duplicate pending requests from the same student to this mentor
    if MentorshipRequest.objects.filter(student=student, mentor=mentor, status='Pending').exists():
        raise ValidationError("You already have a pending mentorship request with this mentor. Please await their response before booking another session.")

    # 2. Prevent slot collision (same mentor, date, and time already requested or accepted)
    if MentorshipRequest.objects.filter(mentor=mentor, requested_date=requested_date, requested_time=requested_time, status__in=['Pending', 'Accepted']).exists():
        raise ValidationError("This mentor already has a session booked or requested for this date and time.")

    # 3. Enforce weekly capacity limit (max_sessions_per_week)
    start_of_week = requested_date - timedelta(days=requested_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    weekly_count = MentorshipRequest.objects.filter(
        mentor=mentor,
        requested_date__range=[start_of_week, end_of_week],
        status__in=['Pending', 'Accepted']
    ).count()
    if weekly_count >= mentor.max_sessions_per_week:
        raise ValidationError(f"This mentor has reached their maximum booking capacity ({mentor.max_sessions_per_week} sessions) for the week of {start_of_week.strftime('%b %d, %Y')}.")

    # 4. Enforce declared availability
    day_name = requested_date.strftime('%A')
    if mentor.availabilities.exists():
        day_slots = mentor.availabilities.filter(day=day_name)
        if not day_slots.exists():
            raise ValidationError(f"This mentor is not available on {day_name}s.")
        if not any(slot.start_time <= requested_time <= slot.end_time for slot in day_slots):
            raise ValidationError(f"The requested time ({requested_time.strftime('%I:%M %p')}) is outside the mentor's declared availability for {day_name}.")
    elif mentor.available_days:
        allowed_days = [d.strip().lower() for d in mentor.available_days.split(',') if d.strip()]
        if day_name.lower() not in allowed_days:
            raise ValidationError(f"This mentor is not available on {day_name}s. Available days: {mentor.available_days}.")

    request_obj = MentorshipRequest.objects.create(
        student=student,
        mentor=mentor,
        requested_date=requested_date,
        requested_time=requested_time,
        purpose=form_cleaned_data.get('purpose'),
        student_message=form_cleaned_data.get('student_message'),
        status='Pending'
    )

    # Notify Mentor
    create_notification(
        recipient=mentor.user,
        actor=student,
        title="New Mentorship Request Received",
        message=f"You received a new session request from {student.username} for {request_obj.purpose} on {request_obj.requested_date}.",
        notification_type='mentorship_request_submitted',
        target_url=reverse('community:mentor_requests'),
        related_request=request_obj
    )
    simulate_notification(
        user=mentor.user,
        subject="New Mentorship Request Received",
        message=f"You received a new session request from {student.username} for {request_obj.purpose} on {request_obj.requested_date}."
    )
    # Notify Student
    create_notification(
        recipient=student,
        actor=None,
        title="Mentorship Request Submitted",
        message=f"Your request to book a session with {mentor.full_name} has been submitted successfully.",
        notification_type='mentorship_request_submitted',
        target_url=reverse('community:student_bookings'),
        related_request=request_obj
    )
    simulate_notification(
        user=student,
        subject="Mentorship Request Submitted",
        message=f"Your request to book a session with {mentor.full_name} has been submitted successfully."
    )
    
    return request_obj


@transaction.atomic
def respond_to_request_service(request_obj, action, response_message, meeting_link=None, meeting_date=None, meeting_time=None, actor=None):
    """
    Responds to or updates a student request (accept/reject/complete/cancel).
    Validates state transitions and notifies the appropriate recipient.
    Acquires row locks in consistent order: MentorProfile -> MentorshipRequest.
    """
    # 1. Row-lock MentorProfile first (consistent order: MentorProfile -> MentorshipRequest)
    mentor = MentorProfile.objects.select_for_update().get(pk=request_obj.mentor_id)

    # 2. Row-lock MentorshipRequest second to synchronize concurrent transactions and sync latest state
    fresh_request = MentorshipRequest.objects.select_for_update().get(pk=request_obj.pk)
    request_obj.status = fresh_request.status

    if request_obj.status in ['Rejected', 'Completed', 'Cancelled']:
        raise ValidationError(f"Cannot perform '{action}' on a mentorship request that is already {request_obj.status}.")

    response_message = (response_message or '').strip()

    if action == 'accept':
        if mentor.status != 'Approved' or not mentor.verified or mentor.is_paused:
            raise ValidationError("Cannot accept a request when mentor profile is not active, approved, and unpaused.")
        if request_obj.status != 'Pending':
            raise ValidationError(f"Cannot accept a request with status '{request_obj.status}'. Only Pending requests can be accepted.")
        request_obj.status = 'Accepted'
        request_obj.meeting_link = meeting_link or ''
        request_obj.meeting_date = meeting_date or request_obj.requested_date
        request_obj.meeting_time = meeting_time or request_obj.requested_time
        request_obj.mentor_response = response_message
        
        subject = "Mentorship Request Accepted!"
        msg = f"Your session request has been accepted by {request_obj.mentor.full_name}. Meeting Link: {request_obj.meeting_link}"
        recipient = request_obj.student
        notif_actor = actor or request_obj.mentor.user
        notification_type = 'mentorship_request_accepted'
        target_url = reverse('community:student_bookings')

    elif action == 'reject':
        if request_obj.status != 'Pending':
            raise ValidationError(f"Cannot reject a request with status '{request_obj.status}'. Only Pending requests can be rejected.")
        request_obj.status = 'Rejected'
        request_obj.mentor_response = response_message
        subject = "Mentorship Request Declined"
        msg = f"Your session request was declined by {request_obj.mentor.full_name}. Reason: {response_message}"
        recipient = request_obj.student
        notif_actor = actor or request_obj.mentor.user
        notification_type = 'mentorship_request_rejected'
        target_url = reverse('community:student_bookings')

    elif action == 'complete':
        if request_obj.status != 'Accepted':
            raise ValidationError(f"Cannot complete a request with status '{request_obj.status}'. Only Accepted sessions can be marked as Completed.")
        request_obj.status = 'Completed'
        request_obj.mentor_response = response_message
        subject = "Mentorship Session Completed"
        msg = f"Your session with {request_obj.mentor.full_name} has been marked as Completed. Please leave a review!"
        recipient = request_obj.student
        notif_actor = actor or request_obj.mentor.user
        notification_type = 'mentorship_session_completed'
        target_url = reverse('community:student_bookings')

    elif action == 'cancel':
        if request_obj.status not in ['Pending', 'Accepted']:
            raise ValidationError(f"Cannot cancel a session with status '{request_obj.status}'.")
        
        if not response_message:
            raise ValidationError("A cancellation reason or note is required.")

        request_obj.status = 'Cancelled'
        request_obj.mentor_response = response_message
        notification_type = 'mentorship_session_cancelled'
        if actor and actor == request_obj.student:
            subject = "Mentorship Session Cancelled by Student"
            msg = f"The mentorship session requested by {request_obj.student.username} for {request_obj.requested_date} was cancelled by the student. Reason: {response_message}"
            recipient = request_obj.mentor.user
            notif_actor = request_obj.student
            target_url = reverse('community:mentor_requests')
        else:
            subject = "Mentorship Session Cancelled"
            msg = f"The mentorship session on {request_obj.requested_date} with {request_obj.mentor.full_name} has been cancelled by the mentor. Reason: {response_message}"
            recipient = request_obj.student
            notif_actor = actor or request_obj.mentor.user
            target_url = reverse('community:student_bookings')
    else:
        raise ValueError(f"Invalid response action: {action}")

    request_obj.save()
    create_notification(
        recipient=recipient,
        actor=notif_actor,
        title=subject,
        message=msg,
        notification_type=notification_type,
        target_url=target_url,
        related_request=request_obj
    )
    simulate_notification(user=recipient, subject=subject, message=msg)
    return request_obj


@transaction.atomic
def submit_mentor_review_service(student, mentor, rating, comment):
    """
    Submits a review for a mentor and recalculates their overall rating.
    Reviews are strictly restricted to students who completed a mentorship session.
    """
    has_completed = MentorshipRequest.objects.filter(
        student=student,
        mentor=mentor,
        status='Completed'
    ).exists()
    if not has_completed:
        raise ValidationError("You can only submit a review after completing a mentorship session with this mentor.")

    review, created = MentorReview.objects.update_or_create(
        student=student,
        mentor=mentor,
        defaults={
            'rating': rating,
            'comment': comment
        }
    )

    # Recalculate average rating
    aggregates = mentor.reviews.aggregate(avg_rating=Avg('rating'), count=Count('id'))
    mentor.rating = aggregates['avg_rating'] or 0.0
    mentor.total_reviews = aggregates['count'] or 0
    mentor.save()

    # Notify Mentor
    create_notification(
        recipient=mentor.user,
        actor=student,
        title="New Review Received",
        message=f"Student {student.username} left a {rating}-star rating on your profile.",
        notification_type='mentor_review_received',
        target_url=reverse('community:mentor_dashboard')
    )
    simulate_notification(
        user=mentor.user,
        subject="New Review Received",
        message=f"Student {student.username} left a {rating}-star rating on your profile."
    )
    
    return review


@transaction.atomic
def save_mentor_availability_service(mentor, day, start_time, end_time, max_sessions):
    """
    Saves or updates a day's time range slot in MentorAvailability.
    """
    availability, created = MentorAvailability.objects.update_or_create(
        mentor=mentor,
        day=day,
        defaults={
            'start_time': start_time,
            'end_time': end_time,
            'max_sessions': max_sessions
        }
    )
    return availability


# ==========================================
# PHASE 4: MENTOR LIFECYCLE SERVICES
# ==========================================

@transaction.atomic
def pause_mentor_availability_service(user, reason=""):
    """
    Temporarily pauses an approved mentor's availability for new booking requests.
    Existing sessions, reviews, and mentor workspace access remain intact.
    """
    if not hasattr(user, 'mentor_profile'):
        raise ValidationError("User has no mentor profile.")

    mentor = MentorProfile.objects.select_for_update().get(user=user)
    if mentor.status != 'Approved' or not mentor.verified:
        raise ValidationError("Only approved and verified mentors can pause availability.")

    if mentor.is_paused:
        return mentor  # Idempotent

    mentor.is_paused = True
    mentor.paused_at = timezone.now()
    mentor.save(update_fields=['is_paused', 'paused_at'])

    MentorLifecycleEvent.objects.create(
        mentor=mentor,
        event_type='pause',
        actor=user,
        reason=reason or ''
    )

    create_notification(
        recipient=user,
        actor=None,
        title="Mentorship Availability Paused",
        message="You have temporarily paused incoming booking requests. Existing sessions remain active.",
        notification_type='general',
        target_url=reverse('community:mentor_dashboard')
    )
    return mentor


@transaction.atomic
def resume_mentor_availability_service(user, reason=""):
    """
    Resumes an approved mentor's availability to accept new bookings in the marketplace.
    """
    if not hasattr(user, 'mentor_profile'):
        raise ValidationError("User has no mentor profile.")

    mentor = MentorProfile.objects.select_for_update().get(user=user)
    if mentor.status != 'Approved' or not mentor.verified:
        raise ValidationError("Only approved and verified mentors can resume availability.")

    if not mentor.is_paused:
        return mentor  # Idempotent

    mentor.is_paused = False
    mentor.paused_at = None
    mentor.save(update_fields=['is_paused', 'paused_at'])

    MentorLifecycleEvent.objects.create(
        mentor=mentor,
        event_type='resume',
        actor=user,
        reason=reason or ''
    )

    create_notification(
        recipient=user,
        actor=None,
        title="Mentorship Availability Resumed",
        message="Your mentor profile is now active and accepting new session requests in the marketplace.",
        notification_type='general',
        target_url=reverse('community:mentor_dashboard')
    )
    return mentor


def get_mentor_step_down_readiness(user):
    """
    Checks whether a mentor is eligible to step down.
    Returns status and outstanding request querysets.
    """
    if not hasattr(user, 'mentor_profile'):
        return {
            'eligible': False,
            'accepted_sessions': MentorshipRequest.objects.none(),
            'pending_requests': MentorshipRequest.objects.none(),
            'accepted_count': 0,
            'pending_count': 0,
        }

    mentor = user.mentor_profile
    accepted_sessions = MentorshipRequest.objects.filter(mentor=mentor, status='Accepted').select_related('student')
    pending_requests = MentorshipRequest.objects.filter(mentor=mentor, status='Pending').select_related('student')
    accepted_count = accepted_sessions.count()
    pending_count = pending_requests.count()

    return {
        'eligible': (accepted_count == 0),
        'accepted_sessions': accepted_sessions,
        'pending_requests': pending_requests,
        'accepted_count': accepted_count,
        'pending_count': pending_count,
    }


@transaction.atomic
def execute_mentor_step_down_service(user, reason=""):
    """
    Executes a voluntary step-down for an approved mentor.
    Prerequisite: All accepted sessions must be resolved (completed or explicitly cancelled).
    Automatically cancels all Pending requests with student notifications.
    Transitions status to 'Inactive', persists step-down reason, records lifecycle event,
    preserves historical records, and notifies the mentor.
    """
    if not hasattr(user, 'mentor_profile'):
        raise ValidationError("User has no mentor profile.")

    # 1. Row-lock MentorProfile first (consistent order: MentorProfile -> MentorshipRequest)
    mentor = MentorProfile.objects.select_for_update().get(user=user)
    if mentor.status != 'Approved' or not mentor.verified:
        raise ValidationError("Only approved mentors can initiate step-down.")

    # 2. Concurrency check & lock: Lock ALL active and pending requests for this mentor
    active_and_pending_requests = list(
        MentorshipRequest.objects.select_for_update().filter(
            mentor=mentor,
            status__in=['Pending', 'Accepted']
        )
    )
    accepted_sessions = [r for r in active_and_pending_requests if r.status == 'Accepted']
    if accepted_sessions:
        raise ValidationError(
            f"Cannot step down while {len(accepted_sessions)} accepted session(s) remain unresolved. "
            "Please complete or cancel them before stepping down."
        )

    # 3. Automatically cancel all pending requests with student notifications
    pending_requests = [r for r in active_and_pending_requests if r.status == 'Pending']
    for req in pending_requests:
        req.status = 'Cancelled'
        req.mentor_response = "Mentor has temporarily stepped down from mentorship."
        req.save(update_fields=['status', 'mentor_response'])
        create_notification(
            recipient=req.student,
            actor=user,
            title="Mentorship Request Cancelled",
            message=f"Your pending mentorship request with {mentor.full_name} was cancelled because the mentor has stepped down from mentorship.",
            notification_type='mentorship_session_cancelled',
            target_url=reverse('community:student_bookings'),
            related_request=req
        )

    # 4. Deactivate mentor profile and persist step-down reason
    mentor.status = 'Inactive'
    mentor.is_paused = True
    mentor.stepped_down_at = timezone.now()
    mentor.step_down_reason = reason or ''
    mentor.save(update_fields=['status', 'is_paused', 'stepped_down_at', 'step_down_reason'])

    # 5. Persist structured lifecycle audit event
    MentorLifecycleEvent.objects.create(
        mentor=mentor,
        event_type='step_down',
        actor=user,
        reason=reason or ''
    )

    # 6. Notify mentor
    create_notification(
        recipient=user,
        actor=None,
        title="Mentor Profile Deactivated",
        message="You have voluntarily stepped down as a mentor. Your history, reviews, and completed sessions remain preserved. You can reactivate anytime from your account settings.",
        notification_type='general',
        target_url=reverse('dashboard')
    )

    return mentor


@transaction.atomic
def reactivate_mentor_service(user, resume_bookings=True, reason=""):
    """
    Reactivates a previously approved mentor profile that was voluntarily stepped down (status='Inactive').
    Does not require new administrative approval.
    Blocked or rejected profiles cannot self-reactivate.
    """
    if not hasattr(user, 'mentor_profile'):
        raise ValidationError("No mentor profile found for this user.")

    # 1. Row-lock MentorProfile
    mentor = MentorProfile.objects.select_for_update().get(user=user)

    if mentor.status == 'Blocked':
        raise ValidationError("Your mentor account is suspended by administrators and cannot be self-reactivated.")
    if mentor.status == 'Rejected':
        raise ValidationError("Your mentor application was declined. Please submit a new application.")
    if mentor.status == 'Pending':
        raise ValidationError("Your mentor application is currently awaiting initial admin review.")
    if mentor.status == 'Approved':
        return mentor  # Already approved, idempotent

    if mentor.status == 'Inactive':
        mentor.status = 'Approved'
        mentor.verified = True
        mentor.stepped_down_at = None
        mentor.step_down_reason = ''
        mentor.is_paused = not resume_bookings
        if not mentor.is_paused:
            mentor.paused_at = None
        else:
            mentor.paused_at = timezone.now()
        mentor.save(update_fields=['status', 'verified', 'stepped_down_at', 'step_down_reason', 'is_paused', 'paused_at'])

        # Persist structured lifecycle audit event
        MentorLifecycleEvent.objects.create(
            mentor=mentor,
            event_type='reactivate',
            actor=user,
            reason=reason or ''
        )

        create_notification(
            recipient=user,
            actor=None,
            title="Mentor Profile Reactivated!",
            message="Your mentor profile has been reactivated. Welcome back to the CareerCatalyst Mentor Community!",
            notification_type='general',
            target_url=reverse('community:mentor_dashboard')
        )
        return mentor

    raise ValidationError(f"Invalid mentor profile state for reactivation: '{mentor.status}'.")

