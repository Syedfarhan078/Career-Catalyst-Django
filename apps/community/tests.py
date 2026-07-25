from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command
import json

from .models import (
    ForumCategory, ForumThread, ForumReply, MentorProfile, SharedProject, 
    ProjectLike, SuccessStory, MentorMessage, MentorshipRequest, 
    MentorReview, MentorAvailability
)
from apps.profiles.models import StudentProfile
from .utils import calculate_mentor_match_score

User = get_user_model()

class MentorMarketplaceTests(TestCase):
    def setUp(self):
        # Create users
        self.student_user = User.objects.create_user(
            username='student_bob',
            email='bob@student.com',
            password='password123'
        )
        self.mentor_user = User.objects.create_user(
            username='mentor_alice',
            email='alice@mentor.com',
            password='password123'
        )
        self.staff_user = User.objects.create_user(
            username='staff_admin',
            email='admin@platform.com',
            password='password123',
            is_staff=True
        )
        
        # Create StudentProfile
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            preferred_domain='Backend',
            skills='Python, Django, SQL'
        )

        # Create MentorProfile (Pending review)
        self.mentor_profile = MentorProfile.objects.create(
            user=self.mentor_user,
            full_name='Alice Mentor',
            email='alice@mentor.com',
            phone_number='1234567890',
            company='Google',
            designation='Staff Engineer',
            experience_years=8,
            current_location='San Francisco, CA',
            bio='Expert Google backend engineer.',
            career_domains='Backend, DevOps',
            skills='Python, Django, Kubernetes, Docker, SQL',
            languages='English',
            available_days='Monday, Wednesday',
            available_time_slots='10:00 AM - 12:00 PM',
            status='Pending',
            verified=False
        )

        self.category = ForumCategory.objects.create(
            name='General',
            slug='general'
        )

    def test_mentor_registration_defaults_to_pending(self):
        # Check defaults
        self.assertEqual(self.mentor_profile.status, 'Pending')
        self.assertFalse(self.mentor_profile.verified)

    def test_marketplace_visibility_filters(self):
        self.client.force_login(self.student_user)
        
        # 1. Access marketplace -> should be empty since Alice is Pending
        url = reverse('community:mentor_list')
        response = self.client.get(url)
        self.assertEqual(len(response.context['mentors']), 0)

        # 2. Approve Alice
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        # 3. Access marketplace -> Alice should now be visible
        response = self.client.get(url)
        self.assertEqual(len(response.context['mentors']), 1)
        self.assertEqual(response.context['mentors'][0].full_name, 'Alice Mentor')

    def test_admin_verification_flow(self):
        self.client.force_login(self.staff_user)
        
        # Approve mentor application via staff action url
        url = reverse('community:admin_action', args=[self.mentor_profile.id, 'approve'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302) # Redirects back to verify panel
        
        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.status, 'Approved')
        self.assertTrue(self.mentor_profile.verified)

    def test_mentorship_booking_and_acceptance(self):
        # Approve mentor first
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        self.client.force_login(self.student_user)
        
        # Book a session
        url = reverse('community:book_session', args=[self.mentor_profile.id])
        booking_data = {
            "requested_date": "2026-08-10",
            "requested_time": "11:00:00",
            "purpose": "Resume Review",
            "student_message": "Please review my resume details."
        }
        response = self.client.post(url, booking_data)
        self.assertEqual(response.status_code, 302) # Redirects

        req = MentorshipRequest.objects.first()
        self.assertEqual(req.status, 'Pending')
        self.assertEqual(req.student, self.student_user)

        # Mentor accepts the request
        self.client.force_login(self.mentor_user)
        respond_url = reverse('community:respond_request', args=[req.id])
        respond_data = {
            "action": "accept",
            "response_message": "Sure, let's connect!",
            "meeting_link": "https://meet.google.com/abc-def-ghi"
        }
        response = self.client.post(respond_url, respond_data)
        self.assertEqual(response.status_code, 302)

        req.refresh_from_db()
        self.assertEqual(req.status, 'Accepted')
        self.assertEqual(req.meeting_link, "https://meet.google.com/abc-def-ghi")

    def test_mentor_review_and_rating_averages(self):
        # Approve mentor
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        self.client.force_login(self.student_user)
        
        # Submit a review
        url = reverse('community:submit_review', args=[self.mentor_profile.id])
        review_data = {
            "rating": 5,
            "comment": "Excellent guidance, very helpful engineer!"
        }
        response = self.client.post(url, review_data)
        self.assertEqual(response.status_code, 302)

        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.rating, 5.0)
        self.assertEqual(self.mentor_profile.total_reviews, 1)

    def test_matching_score_algorithm(self):
        # Alice Mentor: Domain matches 'Backend', Skills include 'Python', 'Django', 'SQL' (matches student completely)
        # Experience is 8 years -> Experience score points: 90
        # Rating is 0.0 -> Rating score: 0
        score = calculate_mentor_match_score(self.student_profile, self.mentor_profile)
        
        # Calculation:
        # Skill Match: bob has 'Python', 'Django', 'SQL'. All 3 exist in alice. Skill score = 100. Weighted = 40% * 100 = 40.
        # Domain Match: bob has 'Backend'. Matches alice 'Backend'. Domain score = 100. Weighted = 30% * 100 = 30.
        # Experience: 8 years -> exp_score = 90. Weighted = 20% * 90 = 18.
        # Rating: 0.0 -> rating_score = 0. Weighted = 10% * 0 = 0.
        # Total Match Score = 40 + 30 + 18 + 0 = 88.0%
        self.assertEqual(score, 88.0)
