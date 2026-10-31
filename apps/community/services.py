from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Avg, Count
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from .models import MentorProfile, MentorSkill, MentorshipRequest, MentorReview, MentorAvailability, MentorMessage
from .utils import simulate_notification

@transaction.atomic
def register_mentor_service(user, form_cleaned_data):
    """
    Creates a new MentorProfile for a user and sets it to 'Pending' verification.
    Also parses the skills_csv and populates MentorSkill models.
    """
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
    """
    if not reviewer.is_staff and not reviewer.is_superuser:
        raise PermissionError("Only staff/admins can review mentor applications.")
        
    if action == 'approve':
        profile.status = 'Approved'
        profile.verified = True
        subject = "Mentorship Profile Approved!"
        msg = f"Congratulations {profile.full_name}, your mentorship application has been approved and activated in the marketplace."
    elif action == 'reject':
        profile.status = 'Rejected'
        profile.verified = False
        subject = "Mentorship Profile Status Update"
        msg = f"Hello {profile.full_name}, your application was rejected. Please review your credentials and submit again."
    elif action == 'block':
        profile.status = 'Blocked'
        profile.verified = False
        subject = "Mentorship Account Blocked"
        msg = "Your mentor profile has been blocked by administrators due to policy violations."
    else:
        raise ValueError(f"Invalid review action: {action}")
        
    profile.save()
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
    simulate_notification(
        user=mentor.user,
        subject="New Mentorship Request Received",
        message=f"You received a new session request from {student.username} for {request_obj.purpose} on {request_obj.requested_date}."
    )
    # Notify Student
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
    """
    if request_obj.status in ['Rejected', 'Completed', 'Cancelled']:
        raise ValidationError(f"Cannot perform '{action}' on a mentorship request that is already {request_obj.status}.")

    request_obj.mentor_response = response_message

    if action == 'accept':
        if request_obj.status != 'Pending':
            raise ValidationError(f"Cannot accept a request with status '{request_obj.status}'. Only Pending requests can be accepted.")
        request_obj.status = 'Accepted'
        request_obj.meeting_link = meeting_link or ''
        request_obj.meeting_date = meeting_date or request_obj.requested_date
        request_obj.meeting_time = meeting_time or request_obj.requested_time
        
        subject = "Mentorship Request Accepted!"
        msg = f"Your session request has been accepted by {request_obj.mentor.full_name}. Meeting Link: {request_obj.meeting_link}"
        recipient = request_obj.student

    elif action == 'reject':
        if request_obj.status != 'Pending':
            raise ValidationError(f"Cannot reject a request with status '{request_obj.status}'. Only Pending requests can be rejected.")
        request_obj.status = 'Rejected'
        subject = "Mentorship Request Declined"
        msg = f"Your session request was declined by {request_obj.mentor.full_name}. Reason: {response_message}"
        recipient = request_obj.student

    elif action == 'complete':
        if request_obj.status != 'Accepted':
            raise ValidationError(f"Cannot complete a request with status '{request_obj.status}'. Only Accepted sessions can be marked as Completed.")
        request_obj.status = 'Completed'
        subject = "Mentorship Session Completed"
        msg = f"Your session with {request_obj.mentor.full_name} has been marked as Completed. Please leave a review!"
        recipient = request_obj.student

    elif action == 'cancel':
        if request_obj.status not in ['Pending', 'Accepted']:
            raise ValidationError(f"Cannot cancel a session with status '{request_obj.status}'.")
        request_obj.status = 'Cancelled'
        if actor and actor == request_obj.student:
            subject = "Mentorship Session Cancelled by Student"
            msg = f"The mentorship session requested by {request_obj.student.username} for {request_obj.requested_date} was cancelled by the student."
            recipient = request_obj.mentor.user
        else:
            subject = "Mentorship Session Cancelled"
            msg = f"The mentorship session on {request_obj.requested_date} with {request_obj.mentor.full_name} has been cancelled."
            recipient = request_obj.student
    else:
        raise ValueError(f"Invalid response action: {action}")

    request_obj.save()
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
