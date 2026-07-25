from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Avg, Count
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
    """
    request_obj = MentorshipRequest.objects.create(
        student=student,
        mentor=mentor,
        requested_date=form_cleaned_data.get('requested_date'),
        requested_time=form_cleaned_data.get('requested_time'),
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
def respond_to_request_service(request_obj, action, response_message, meeting_link=None, meeting_date=None, meeting_time=None):
    """
    Mentor responds to a student request (accept/reject/complete/cancel).
    """
    request_obj.mentor_response = response_message

    if action == 'accept':
        request_obj.status = 'Accepted'
        request_obj.meeting_link = meeting_link or ''
        request_obj.meeting_date = meeting_date or request_obj.requested_date
        request_obj.meeting_time = meeting_time or request_obj.requested_time
        
        subject = "Mentorship Request Accepted!"
        msg = f"Your session request has been accepted by {request_obj.mentor.full_name}. Meeting Link: {request_obj.meeting_link}"
    elif action == 'reject':
        request_obj.status = 'Rejected'
        subject = "Mentorship Request Declined"
        msg = f"Your session request was declined by {request_obj.mentor.full_name}. Reason: {response_message}"
    elif action == 'complete':
        request_obj.status = 'Completed'
        subject = "Mentorship Session Completed"
        msg = f"Your session with {request_obj.mentor.full_name} has been marked as Completed. Please leave a review!"
    elif action == 'cancel':
        request_obj.status = 'Cancelled'
        subject = "Session Cancelled"
        msg = f"The mentorship session on {request_obj.requested_date} has been cancelled."
    else:
        raise ValueError(f"Invalid response action: {action}")

    request_obj.save()
    simulate_notification(user=request_obj.student, subject=subject, message=msg)
    return request_obj


@transaction.atomic
def submit_mentor_review_service(student, mentor, rating, comment):
    """
    Submits a review for a mentor and recalculates their overall rating.
    """
    review = MentorReview.objects.create(
        student=student,
        mentor=mentor,
        rating=rating,
        comment=comment
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
