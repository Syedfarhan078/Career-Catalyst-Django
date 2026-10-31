from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from django.core.exceptions import ValidationError
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

    def _get_next_date(self, target_weekday=0):
        """Returns the next future date matching target_weekday (0=Monday)."""
        today = timezone.now().date()
        days_ahead = (target_weekday - today.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

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
        
        # Approve mentor application via staff action url (POST required)
        url = reverse('community:admin_action', args=[self.mentor_profile.id, 'approve'])
        response = self.client.post(url)
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
        
        # Book a session for next available Monday
        booking_date = self._get_next_date(0)
        url = reverse('community:book_session', args=[self.mentor_profile.id])
        booking_data = {
            "requested_date": booking_date.strftime("%Y-%m-%d"),
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

        # Create completed mentorship session so review is authorized
        booking_date = self._get_next_date(0)
        MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date=booking_date,
            requested_time="11:00:00",
            purpose="Resume Review",
            status="Completed"
        )

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

    def test_post_enforcement_on_mutations(self):
        # 1. admin_action requires POST
        self.client.force_login(self.staff_user)
        admin_url = reverse('community:admin_action', args=[self.mentor_profile.id, 'approve'])
        get_res = self.client.get(admin_url)
        self.assertEqual(get_res.status_code, 405)

        # 2. cancel_booking requires POST
        req = MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date='2026-09-01',
            requested_time='10:00:00',
            purpose='Career Guidance',
            status='Pending'
        )
        self.client.force_login(self.student_user)
        cancel_url = reverse('community:cancel_booking', args=[req.id])
        get_res = self.client.get(cancel_url)
        self.assertEqual(get_res.status_code, 405)

        post_res = self.client.post(cancel_url)
        self.assertEqual(post_res.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'Cancelled')

        # 3. delete_availability requires POST
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        avail = MentorAvailability.objects.create(
            mentor=self.mentor_profile,
            day='Monday',
            start_time='09:00:00',
            end_time='10:00:00',
            max_sessions=2
        )
        self.client.force_login(self.mentor_user)
        del_url = reverse('community:delete_availability', args=[avail.id])
        get_res = self.client.get(del_url)
        self.assertEqual(get_res.status_code, 405)

        post_res = self.client.post(del_url)
        self.assertEqual(post_res.status_code, 302)
        self.assertFalse(MentorAvailability.objects.filter(id=avail.id).exists())

    def test_bidirectional_mentor_chat(self):
        # Setup accepted booking
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date='2026-09-01',
            requested_time='10:00:00',
            purpose='Resume Review',
            status='Accepted'
        )

        # 1. Student accesses chat with mentor
        self.client.force_login(self.student_user)
        chat_url = reverse('community:mentor_chat', args=[self.mentor_user.id])
        res = self.client.get(chat_url)
        self.assertEqual(res.status_code, 200)

        # 2. Student sends message
        send_url = reverse('community:send_mentor_message', args=[self.mentor_user.id])
        send_res = self.client.post(
            send_url,
            json.dumps({"content": "Hello Alice, looking forward to our session!"}),
            content_type="application/json"
        )
        self.assertEqual(send_res.status_code, 200)
        data = send_res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['message']['sender'], self.student_user.username)

        # 3. Mentor accesses chat with student
        self.client.force_login(self.mentor_user)
        mentor_chat_url = reverse('community:mentor_chat', args=[self.student_user.id])
        res = self.client.get(mentor_chat_url)
        self.assertEqual(res.status_code, 200)

        # 4. Mentor sends reply
        mentor_send_url = reverse('community:send_mentor_message', args=[self.student_user.id])
        mentor_send_res = self.client.post(
            mentor_send_url,
            json.dumps({"content": "Hi Bob! Glad to connect. Send over your resume PDF."}),
            content_type="application/json"
        )
        self.assertEqual(mentor_send_res.status_code, 200)
        mentor_data = mentor_send_res.json()
        self.assertTrue(mentor_data['success'])
        self.assertEqual(mentor_data['message']['sender'], self.mentor_user.username)

        # Verify DB messages
        self.assertEqual(MentorMessage.objects.count(), 2)

    def test_chat_locked_when_no_accepted_booking(self):
        other_student = User.objects.create_user(username='other_student', email='other@test.com', password='pw')
        self.client.force_login(other_student)

        # Chat view redirects when locked
        chat_url = reverse('community:mentor_chat', args=[self.mentor_user.id])
        res = self.client.get(chat_url)
        self.assertEqual(res.status_code, 302)

        # Chat send returns 403 Forbidden
        send_url = reverse('community:send_mentor_message', args=[self.mentor_user.id])
        send_res = self.client.post(
            send_url,
            json.dumps({"content": "Trying to bypass lock"}),
            content_type="application/json"
        )
        self.assertEqual(send_res.status_code, 403)

    def test_forum_and_project_flows(self):
        self.client.force_login(self.student_user)

        # Create forum thread
        create_url = reverse('community:create_thread')
        res = self.client.post(create_url, {
            "category": self.category.id,
            "title": "How to master Django ORM?",
            "content": "Any good tips on optimizing querysets and avoiding N+1?"
        })
        self.assertEqual(res.status_code, 302)
        thread = ForumThread.objects.first()
        self.assertIsNotNone(thread)
        self.assertEqual(thread.title, "How to master Django ORM?")

        # Add reply
        reply_url = reverse('community:add_reply', args=[thread.id])
        rep_res = self.client.post(reply_url, {"content": "Use select_related and prefetch_related!"})
        self.assertEqual(rep_res.status_code, 302)
        self.assertEqual(thread.replies.count(), 1)

        # Share project
        share_url = reverse('community:share_project')
        proj_res = self.client.post(share_url, {
            "title": "E-Commerce Microservice",
            "description": "Built using Django and Celery",
            "github_link": "https://github.com/test/ecommerce",
            "live_link": "https://ecommerce.demo.com",
            "tags": "python,django"
        })
        self.assertEqual(proj_res.status_code, 302)
        proj = SharedProject.objects.first()
        self.assertIsNotNone(proj)

        # Toggle like
        like_url = reverse('community:toggle_like_project', args=[proj.id])
        like_res = self.client.post(like_url)
        self.assertEqual(like_res.status_code, 200)
        self.assertTrue(like_res.json()['is_liked'])
        self.assertEqual(like_res.json()['likes_count'], 1)

        # Toggle like off
        unlike_res = self.client.post(like_url)
        self.assertEqual(unlike_res.status_code, 200)
        self.assertFalse(unlike_res.json()['is_liked'])
        self.assertEqual(unlike_res.json()['likes_count'], 0)

    def test_workspace_templates_rendering(self):
        # 1. Student workspace views
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        thread = ForumThread.objects.create(
            category=self.category,
            title='Test Thread',
            content='Test Content',
            author=self.student_user
        )

        self.client.force_login(self.student_user)

        urls_to_test = [
            reverse('community:hub'),
            reverse('community:forum_list'),
            reverse('community:create_thread'),
            reverse('community:forum_detail', args=[thread.id]),
            reverse('community:project_list'),
            reverse('community:share_project'),
            reverse('community:story_list'),
            reverse('community:mentor_list'),
            reverse('community:mentor_detail', args=[self.mentor_profile.id]),
            reverse('community:student_bookings'),
        ]

        for u in urls_to_test:
            res = self.client.get(u)
            self.assertEqual(res.status_code, 200, f"Failed rendering {u}")
            self.assertContains(res, 'dash-shell')
            self.assertContains(res, 'dash-sidebar')

        # 2. Mentor workspace views
        self.client.force_login(self.mentor_user)
        mentor_urls = [
            reverse('community:mentor_dashboard'),
            reverse('community:manage_availability'),
            reverse('community:mentor_requests'),
            reverse('community:edit_profile'),
        ]
        for u in mentor_urls:
            res = self.client.get(u)
            self.assertEqual(res.status_code, 200, f"Failed rendering {u}")
            self.assertContains(res, 'dash-shell')

        # 3. Staff admin panel
        self.client.force_login(self.staff_user)
        admin_res = self.client.get(reverse('community:admin_verify'))
        self.assertEqual(admin_res.status_code, 200)
        self.assertContains(admin_res, 'dash-shell')

    def test_cannot_book_unapproved_or_unverified_mentor(self):
        """Phase 1: Students cannot book sessions with Pending, Rejected, or Blocked mentors."""
        self.client.force_login(self.student_user)
        booking_date = self._get_next_date(0)
        url = reverse('community:book_session', args=[self.mentor_profile.id])
        booking_data = {
            "requested_date": booking_date.strftime("%Y-%m-%d"),
            "requested_time": "11:00:00",
            "purpose": "Resume Review",
            "student_message": "Testing booking unapproved mentor."
        }

        # 1. Pending mentor
        self.mentor_profile.status = 'Pending'
        self.mentor_profile.verified = False
        self.mentor_profile.save()
        res = self.client.post(url, booking_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.count(), 0)

        # 2. Rejected mentor
        self.mentor_profile.status = 'Rejected'
        self.mentor_profile.save()
        res = self.client.post(url, booking_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.count(), 0)

        # 3. Blocked mentor
        self.mentor_profile.status = 'Blocked'
        self.mentor_profile.save()
        res = self.client.post(url, booking_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.count(), 0)

    def test_mentor_endpoints_require_approved_status(self):
        """Phase 1: Non-mentors and unapproved mentors cannot access mentor-only views."""
        # Student user (no mentor profile)
        self.client.force_login(self.student_user)
        mentor_urls = [
            reverse('community:mentor_dashboard'),
            reverse('community:manage_availability'),
            reverse('community:mentor_requests'),
            reverse('community:edit_profile'),
        ]
        for u in mentor_urls:
            res = self.client.get(u)
            self.assertEqual(res.status_code, 302)
            self.assertIn(reverse('community:mentor_register'), res.url)

        # Mentor user but Rejected status
        self.client.force_login(self.mentor_user)
        self.mentor_profile.status = 'Rejected'
        self.mentor_profile.verified = False
        self.mentor_profile.save()
        for u in mentor_urls:
            res = self.client.get(u)
            self.assertEqual(res.status_code, 200) # Renders mentor_status.html
            self.assertContains(res, 'Application Declined')

    def test_invalid_state_transitions_rejected(self):
        """Phase 1: State machine transitions are strictly enforced."""
        from .services import respond_to_request_service
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        booking_date = self._get_next_date(0)
        req = MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date=booking_date,
            requested_time="11:00:00",
            purpose="Career Guidance",
            status="Pending"
        )

        # Cannot directly complete a Pending request
        with self.assertRaises(ValidationError):
            respond_to_request_service(req, 'complete', 'Trying to complete pending')

        # Accept request -> Accepted
        respond_to_request_service(req, 'accept', 'Accepted session')
        self.assertEqual(req.status, 'Accepted')

        # Cannot accept an already accepted request
        with self.assertRaises(ValidationError):
            respond_to_request_service(req, 'accept', 'Double accept')

        # Cannot reject an already accepted request
        with self.assertRaises(ValidationError):
            respond_to_request_service(req, 'reject', 'Reject accepted')

        # Complete request -> Completed
        respond_to_request_service(req, 'complete', 'Session done')
        self.assertEqual(req.status, 'Completed')

        # Cannot cancel or accept a Completed request
        with self.assertRaises(ValidationError):
            respond_to_request_service(req, 'cancel', 'Cancel completed')
        with self.assertRaises(ValidationError):
            respond_to_request_service(req, 'accept', 'Accept completed')

    def test_cannot_accept_cancelled_request(self):
        """Phase 1: Mentors cannot accept requests that were already cancelled."""
        from .services import respond_to_request_service
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        booking_date = self._get_next_date(0)
        req = MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date=booking_date,
            requested_time="11:00:00",
            purpose="Career Guidance",
            status="Cancelled"
        )

        with self.assertRaises(ValidationError):
            respond_to_request_service(req, 'accept', 'Accepting cancelled request')

    def test_student_cancellation_notifies_mentor(self):
        """Phase 1: Student cancellation notifies mentor, not student."""
        from .services import respond_to_request_service
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        booking_date = self._get_next_date(0)
        req = MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date=booking_date,
            requested_time="11:00:00",
            purpose="Career Guidance",
            status="Pending"
        )

        with patch('apps.community.services.simulate_notification') as mock_notif:
            respond_to_request_service(req, 'cancel', 'Cancelled by student.', actor=self.student_user)
            mock_notif.assert_called_once()
            called_user = mock_notif.call_args[1]['user']
            self.assertEqual(called_user, self.mentor_user)

    def test_rejected_mentor_reapplication_workflow(self):
        """Phase 1: Rejected mentor can load pre-filled form with ?reapply=1 and resubmit."""
        self.client.force_login(self.mentor_user)
        self.mentor_profile.status = 'Rejected'
        self.mentor_profile.verified = False
        self.mentor_profile.save()

        # Normal GET renders status page
        res = self.client.get(reverse('community:mentor_register'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Application Declined')

        # GET with reapply=1 renders registration form pre-populated
        reapply_res = self.client.get(reverse('community:mentor_register') + '?reapply=1')
        self.assertEqual(reapply_res.status_code, 200)
        self.assertContains(reapply_res, 'Alice Mentor')
        self.assertContains(reapply_res, 'Staff Engineer')

        # POST resubmits application and sets status back to Pending
        post_data = {
            'full_name': 'Alice Mentor Updated',
            'email': 'alice@mentor.com',
            'phone_number': '1234567890',
            'company': 'Google Inc',
            'designation': 'Principal Engineer',
            'experience_years': 10,
            'current_location': 'San Francisco, CA',
            'bio': 'Updated bio details.',
            'career_domains': 'Backend, Cloud',
            'skills_csv': 'Python, Django, Go, Kubernetes',
            'languages': 'English',
            'available_days': 'Monday, Wednesday',
            'available_time_slots': '10:00 AM - 12:00 PM',
            'max_sessions_per_week': 5,
            'mentorship_type': 'Online',
            'agreement': 'on'
        }
        submit_res = self.client.post(reverse('community:mentor_register'), post_data)
        self.assertEqual(submit_res.status_code, 302)

        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.status, 'Pending')
        self.assertFalse(self.mentor_profile.verified)
        self.assertEqual(self.mentor_profile.full_name, 'Alice Mentor Updated')

    def test_reviews_restricted_to_completed_sessions(self):
        """Phase 1: Reviews cannot be submitted without a Completed session."""
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        self.client.force_login(self.student_user)
        url = reverse('community:submit_review', args=[self.mentor_profile.id])
        review_data = {"rating": 5, "comment": "Premature review."}

        # 1. No booking at all -> rejected
        res = self.client.post(url, review_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MentorReview.objects.count(), 0)

        # 2. Pending booking -> rejected
        booking_date = self._get_next_date(0)
        req = MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date=booking_date,
            requested_time="11:00:00",
            purpose="Resume Review",
            status="Pending"
        )
        res = self.client.post(url, review_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MentorReview.objects.count(), 0)

        # 3. Accepted booking -> rejected
        req.status = 'Accepted'
        req.save()
        res = self.client.post(url, review_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MentorReview.objects.count(), 0)

        # 4. Completed booking -> accepted
        req.status = 'Completed'
        req.save()
        res = self.client.post(url, review_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MentorReview.objects.count(), 1)

    def test_duplicate_pending_booking_prevented(self):
        """Phase 1: Student cannot create multiple pending requests for the same mentor."""
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        self.client.force_login(self.student_user)
        url = reverse('community:book_session', args=[self.mentor_profile.id])
        booking_date = self._get_next_date(0)
        data = {
            "requested_date": booking_date.strftime("%Y-%m-%d"),
            "requested_time": "10:00:00",
            "purpose": "Career Guidance",
            "student_message": "First request."
        }
        res1 = self.client.post(url, data)
        self.assertEqual(res1.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.count(), 1)

        # Second request while first is still Pending
        booking_date_2 = self._get_next_date(2) # Wednesday
        data2 = {
            "requested_date": booking_date_2.strftime("%Y-%m-%d"),
            "requested_time": "11:00:00",
            "purpose": "Resume Review",
            "student_message": "Second spam request."
        }
        res2 = self.client.post(url, data2)
        self.assertEqual(res2.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.count(), 1) # Still 1

    def test_slot_collision_booking_prevented(self):
        """Phase 1: Two students cannot book the exact same date and time slot."""
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.save()

        booking_date = self._get_next_date(0)
        MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date=booking_date,
            requested_time="10:00:00",
            purpose="Career Guidance",
            status="Pending"
        )

        # Another student attempts same slot
        other_student = User.objects.create_user(username='other_student_jane', email='jane@test.com', password='pw')
        self.client.force_login(other_student)
        url = reverse('community:book_session', args=[self.mentor_profile.id])
        data = {
            "requested_date": booking_date.strftime("%Y-%m-%d"),
            "requested_time": "10:00:00",
            "purpose": "Resume Review",
            "student_message": "Conflicting slot request."
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.count(), 1) # Rejected conflict

    def test_weekly_capacity_enforced(self):
        """Phase 1: Bookings exceeding max_sessions_per_week are rejected."""
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.max_sessions_per_week = 2
        self.mentor_profile.save()

        booking_date = self._get_next_date(0)
        # Create 2 sessions filling capacity for that week
        MentorshipRequest.objects.create(
            student=User.objects.create_user(username='u1', email='u1@test.com', password='pw'),
            mentor=self.mentor_profile,
            requested_date=booking_date,
            requested_time="09:00:00",
            purpose="Career Guidance",
            status="Accepted"
        )
        MentorshipRequest.objects.create(
            student=User.objects.create_user(username='u2', email='u2@test.com', password='pw'),
            mentor=self.mentor_profile,
            requested_date=booking_date,
            requested_time="11:00:00",
            purpose="Career Guidance",
            status="Accepted"
        )

        # 3rd student attempts to book that same week
        self.client.force_login(self.student_user)
        url = reverse('community:book_session', args=[self.mentor_profile.id])
        booking_data = {
            "requested_date": booking_date.strftime("%Y-%m-%d"),
            "requested_time": "10:00:00",
            "purpose": "Resume Review",
            "student_message": "Exceeding capacity booking."
        }
        res = self.client.post(url, booking_data)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.filter(mentor=self.mentor_profile).count(), 2)

    def test_declared_availability_enforced(self):
        """Phase 1: Bookings outside declared days or hours are rejected."""
        self.mentor_profile.status = 'Approved'
        self.mentor_profile.verified = True
        self.mentor_profile.available_days = 'Monday, Wednesday'
        self.mentor_profile.save()

        # Create structured availability slot for Monday (10:00 to 12:00)
        MentorAvailability.objects.create(
            mentor=self.mentor_profile,
            day='Monday',
            start_time='10:00:00',
            end_time='12:00:00',
            max_sessions=2
        )

        self.client.force_login(self.student_user)
        url = reverse('community:book_session', args=[self.mentor_profile.id])

        # 1. Booking on wrong day (Tuesday = 1)
        tuesday_date = self._get_next_date(1)
        res1 = self.client.post(url, {
            "requested_date": tuesday_date.strftime("%Y-%m-%d"),
            "requested_time": "11:00:00",
            "purpose": "Resume Review",
            "student_message": "Wrong day booking."
        })
        self.assertEqual(res1.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.count(), 0)

        # 2. Booking on Monday but outside hours (03:00 PM)
        monday_date = self._get_next_date(0)
        res2 = self.client.post(url, {
            "requested_date": monday_date.strftime("%Y-%m-%d"),
            "requested_time": "15:00:00",
            "purpose": "Resume Review",
            "student_message": "Outside hours booking."
        })
        self.assertEqual(res2.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.count(), 0)


class Phase2MentorWorkspaceTests(TestCase):
    """
    Phase 2: Comprehensive test suite for Dedicated Mentor Workspace,
    workspace switching, session security, mentor shell isolation, and mentees view.
    """
    def setUp(self):
        self.student_user = User.objects.create_user(
            username='student_phase2',
            email='student2@test.com',
            password='password123'
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            preferred_domain='Backend',
            skills='Python, Django'
        )

        self.mentor_user = User.objects.create_user(
            username='mentor_phase2',
            email='mentor2@test.com',
            password='password123'
        )
        self.mentor_student_profile = StudentProfile.objects.create(
            user=self.mentor_user,
            preferred_domain='Fullstack',
            career_goal='Principal Engineer',
            skills='Python, React, AWS'
        )
        self.mentor_profile = MentorProfile.objects.create(
            user=self.mentor_user,
            full_name='Dr. Elena Vance',
            email='elena@mentor.com',
            phone_number='9876543210',
            company='Black Mesa Labs',
            designation='Research Director',
            experience_years=12,
            current_location='New Mexico, USA',
            bio='Physics and engineering mentor.',
            career_domains='Backend, Cloud',
            skills='Python, Django, AWS, Distributed Systems',
            languages='English',
            available_days='Monday, Tuesday, Wednesday, Thursday, Friday',
            available_time_slots='10:00 AM - 12:00 PM',
            status='Approved',
            verified=True,
            max_sessions_per_week=5
        )

    def test_default_workspace_for_student_is_student(self):
        """Phase 2: Default workspace for regular student is 'student'."""
        self.client.force_login(self.student_user)
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['is_approved_mentor'])
        self.assertEqual(res.context['active_workspace'], 'student')

    def test_approved_mentor_can_switch_workspaces_roundtrip(self):
        """Phase 2: Approved mentors can switch to mentor workspace and back to student workspace."""
        self.client.force_login(self.mentor_user)

        # 1. Switch to mentor workspace
        res = self.client.post(reverse('community:switch_workspace'), {'role': 'mentor'})
        self.assertRedirects(res, reverse('community:mentor_dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'mentor')

        # Verify mentor dashboard loads successfully
        dash_res = self.client.get(reverse('community:mentor_dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertTrue(dash_res.context['is_approved_mentor'])
        self.assertEqual(dash_res.context['active_workspace'], 'mentor')

        # 2. Switch back to student workspace
        res_back = self.client.post(reverse('community:switch_workspace'), {'role': 'student'})
        self.assertRedirects(res_back, reverse('dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'student')

    def test_unapproved_users_cannot_switch_to_mentor_workspace(self):
        """Phase 2: Students and unapproved applicants cannot switch to mentor workspace."""
        # 1. Regular student
        self.client.force_login(self.student_user)
        res = self.client.post(reverse('community:switch_workspace'), {'role': 'mentor'})
        self.assertRedirects(res, reverse('dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'student')

        # 2. Pending mentor
        self.mentor_profile.status = 'Pending'
        self.mentor_profile.verified = False
        self.mentor_profile.save()
        self.client.force_login(self.mentor_user)

        res_pending = self.client.post(reverse('community:switch_workspace'), {'role': 'mentor'})
        self.assertRedirects(res_pending, reverse('dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'student')

        # 3. Rejected mentor
        self.mentor_profile.status = 'Rejected'
        self.mentor_profile.save()
        res_rejected = self.client.post(reverse('community:switch_workspace'), {'role': 'mentor'})
        self.assertRedirects(res_rejected, reverse('dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'student')

        # 4. Blocked mentor
        self.mentor_profile.status = 'Blocked'
        self.mentor_profile.save()
        res_blocked = self.client.post(reverse('community:switch_workspace'), {'role': 'mentor'})
        self.assertRedirects(res_blocked, reverse('dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'student')

    def test_tampered_session_clamped_and_denied_access(self):
        """Phase 2: Forging session active_role='mentor' is clamped and rejected by backend guards."""
        self.client.force_login(self.student_user)
        session = self.client.session
        session['active_role'] = 'mentor'
        session.save()

        # Context processor detects unauthorized role and clamps to 'student'
        dash_res = self.client.get(reverse('dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertEqual(dash_res.context['active_workspace'], 'student')
        self.assertFalse(dash_res.context['is_approved_mentor'])

        # Attempting direct access to mentor views is blocked by @mentor_required
        protected_urls = [
            reverse('community:mentor_dashboard'),
            reverse('community:mentor_mentees'),
            reverse('community:mentor_requests'),
            reverse('community:manage_availability'),
            reverse('community:edit_profile'),
        ]
        for url in protected_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302)
            self.assertIn(reverse('community:mentor_register'), res.url)

    def test_mentor_views_render_dedicated_mentor_shell(self):
        """Phase 2: Mentor views render mentor sidebar and identity without student navigation."""
        self.client.force_login(self.mentor_user)

        views_to_check = [
            reverse('community:mentor_dashboard'),
            reverse('community:mentor_mentees'),
            reverse('community:mentor_requests'),
            reverse('community:manage_availability'),
            reverse('community:edit_profile'),
        ]

        for url in views_to_check:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Failed accessing {url}")
            # Mentor shell elements
            self.assertContains(res, 'mentor-sidebar')
            self.assertContains(res, 'Mentor Application Sidebar')
            self.assertContains(res, 'Mentorship Portal')
            self.assertContains(res, 'Dr. Elena Vance')
            self.assertContains(res, 'Black Mesa Labs')
            # Must NOT contain student-specific sidebar links
            self.assertNotContains(res, 'href="/guidance/"')
            self.assertNotContains(res, 'Engineering Student')

    def test_mentor_mentees_view_display_and_filtering(self):
        """Phase 2: mentor_mentees_view displays accepted/completed mentees and supports status filter."""
        student_a = User.objects.create_user(username='mentee_a', email='a@test.com', password='pw')
        student_b = User.objects.create_user(username='mentee_b', email='b@test.com', password='pw')
        student_c = User.objects.create_user(username='mentee_c', email='c@test.com', password='pw')
        student_d = User.objects.create_user(username='mentee_d', email='d@test.com', password='pw')

        # 1. Accepted request
        MentorshipRequest.objects.create(
            student=student_a,
            mentor=self.mentor_profile,
            requested_date=timezone.now().date(),
            requested_time="10:00:00",
            purpose="System Design",
            status="Accepted"
        )
        # 2. Completed request
        MentorshipRequest.objects.create(
            student=student_b,
            mentor=self.mentor_profile,
            requested_date=timezone.now().date(),
            requested_time="11:00:00",
            purpose="Resume Review",
            status="Completed"
        )
        # 3. Pending request (should not appear in mentees list)
        MentorshipRequest.objects.create(
            student=student_c,
            mentor=self.mentor_profile,
            requested_date=timezone.now().date(),
            requested_time="14:00:00",
            purpose="Career Advice",
            status="Pending"
        )
        # 4. Cancelled request (should not appear)
        MentorshipRequest.objects.create(
            student=student_d,
            mentor=self.mentor_profile,
            requested_date=timezone.now().date(),
            requested_time="15:00:00",
            purpose="Interview Prep",
            status="Cancelled"
        )

        self.client.force_login(self.mentor_user)
        url = reverse('community:mentor_mentees')

        # All mentees (Accepted + Completed)
        res_all = self.client.get(url)
        self.assertEqual(res_all.status_code, 200)
        self.assertContains(res_all, 'mentee_a')
        self.assertContains(res_all, 'mentee_b')
        self.assertNotContains(res_all, 'mentee_c')
        self.assertNotContains(res_all, 'mentee_d')

        # Active filter
        res_active = self.client.get(url, {'filter': 'active'})
        self.assertEqual(res_active.status_code, 200)
        self.assertContains(res_active, 'mentee_a')
        self.assertNotContains(res_active, 'mentee_b')

        # Completed filter
        res_completed = self.client.get(url, {'filter': 'completed'})
        self.assertEqual(res_completed.status_code, 200)
        self.assertContains(res_completed, 'mentee_b')
        self.assertNotContains(res_completed, 'mentee_a')

    def test_mentor_dashboard_active_mentees_metric(self):
        """Phase 2: mentor_dashboard accurately calculates distinct active mentees."""
        student_x = User.objects.create_user(username='st_x', email='x@test.com', password='pw')
        student_y = User.objects.create_user(username='st_y', email='y@test.com', password='pw')

        # Two accepted sessions with student_x
        MentorshipRequest.objects.create(
            student=student_x, mentor=self.mentor_profile,
            requested_date=timezone.now().date(), requested_time="09:00:00",
            purpose="One", status="Accepted"
        )
        MentorshipRequest.objects.create(
            student=student_x, mentor=self.mentor_profile,
            requested_date=timezone.now().date(), requested_time="10:00:00",
            purpose="Two", status="Accepted"
        )
        # One accepted session with student_y
        MentorshipRequest.objects.create(
            student=student_y, mentor=self.mentor_profile,
            requested_date=timezone.now().date(), requested_time="11:00:00",
            purpose="Three", status="Accepted"
        )

        self.client.force_login(self.mentor_user)
        res = self.client.get(reverse('community:mentor_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['active_mentees'], 2)

    def test_core_dashboard_redirects_approved_mentor_in_mentor_workspace(self):
        """Phase 2: Core /dashboard/ redirects to mentor dashboard when active_role is 'mentor'."""
        self.client.force_login(self.mentor_user)
        session = self.client.session
        session['active_role'] = 'mentor'
        session.save()

        res = self.client.get(reverse('dashboard'))
        self.assertRedirects(res, reverse('community:mentor_dashboard'))

        # When switched to 'student', renders normal student dashboard
        session['active_role'] = 'student'
        session.save()
        res_student = self.client.get(reverse('dashboard'))
        self.assertEqual(res_student.status_code, 200)

    def test_marketplace_cta_adapts_for_mentor_and_student(self):
        """Phase 2: Directory CTA shows 'Mentor Dashboard' for mentors, 'Apply as Mentor' for students."""
        # 1. Regular student
        self.client.force_login(self.student_user)
        res_student = self.client.get(reverse('community:mentor_list'))
        self.assertEqual(res_student.status_code, 200)
        self.assertContains(res_student, 'Apply as Mentor')
        self.assertNotContains(res_student, 'Mentor Dashboard')

        # 2. Approved mentor
        self.client.force_login(self.mentor_user)
        res_mentor = self.client.get(reverse('community:mentor_list'))
        self.assertEqual(res_mentor.status_code, 200)
        self.assertContains(res_mentor, 'Mentor Dashboard')
        self.assertNotContains(res_mentor, 'Apply as Mentor')

    def test_workspace_switch_preserves_session_and_student_data(self):
        """Phase 2: Switching workspaces does not log the user out and preserves user profile data."""
        self.client.force_login(self.mentor_user)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.mentor_user.pk)

        # Switch to mentor
        self.client.post(reverse('community:switch_workspace'), {'role': 'mentor'})
        self.assertEqual(int(self.client.session['_auth_user_id']), self.mentor_user.pk)

        # Switch to student
        self.client.post(reverse('community:switch_workspace'), {'role': 'student'})
        self.assertEqual(int(self.client.session['_auth_user_id']), self.mentor_user.pk)

        # Verify StudentProfile is fully intact
        self.mentor_student_profile.refresh_from_db()
        self.assertEqual(self.mentor_student_profile.preferred_domain, 'Fullstack')
        self.assertEqual(self.mentor_student_profile.career_goal, 'Principal Engineer')

    def test_navbar_renders_workspace_switcher_for_mentors_only(self):
        """Phase 2: Navbar includes workspace switcher UI elements only for approved mentors."""
        from django.template.loader import render_to_string
        from django.test import RequestFactory
        factory = RequestFactory()

        # 1. Regular student in navbar
        request_student = factory.get('/')
        request_student.user = self.student_user
        request_student.session = self.client.session
        html_student = render_to_string('partials/navbar.html', {
            'user': self.student_user,
            'is_approved_mentor': False,
            'active_workspace': 'student',
        }, request=request_student)
        self.assertNotIn('Mentor Workspace', html_student)
        self.assertNotIn('/community/workspace/switch/', html_student)

        # 2. Approved mentor in navbar
        request_mentor = factory.get('/')
        request_mentor.user = self.mentor_user
        request_mentor.session = self.client.session
        html_mentor = render_to_string('partials/navbar.html', {
            'user': self.mentor_user,
            'is_approved_mentor': True,
            'active_workspace': 'student',
        }, request=request_mentor)
        self.assertIn('Mentor Workspace', html_mentor)
        self.assertIn('/community/workspace/switch/?role=mentor', html_mentor)

        # 3. Student dashboard sidebar shows workspace mode toggle only to approved mentors
        self.client.force_login(self.student_user)
        dash_student = self.client.get(reverse('dashboard'))
        self.assertNotContains(dash_student, 'Switch to Mentor Workspace')

        self.client.force_login(self.mentor_user)
        dash_mentor = self.client.get(reverse('dashboard'))
        self.assertContains(dash_mentor, 'Switch to Mentor Workspace')


class Phase4MentorLifecycleTests(TestCase):
    """
    Phase 4: Comprehensive test suite for Mentor Lifecycle:
    Pause/Resume Availability, Step-Down Workflow, Inactive State,
    Reactivation, and Administrative Blocking.
    """
    def setUp(self):
        self.student_user = User.objects.create_user(
            username='student_p4',
            email='p4_student@test.com',
            password='password123'
        )
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            preferred_domain='Backend'
        )

        self.mentor_user = User.objects.create_user(
            username='mentor_p4',
            email='p4_mentor@test.com',
            password='password123'
        )
        self.mentor_student_profile = StudentProfile.objects.create(
            user=self.mentor_user,
            preferred_domain='DevOps',
            career_goal='Lead Architect'
        )
        self.mentor_profile = MentorProfile.objects.create(
            user=self.mentor_user,
            full_name='Dr. Gordon Freeman',
            email='gordon@blackmesa.gov',
            company='Black Mesa',
            designation='Research Fellow',
            experience_years=10,
            status='Approved',
            verified=True,
            available_days='Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday',
            available_time_slots='10:00 AM - 12:00 PM',
            max_sessions_per_week=10,
            is_paused=False
        )

        self.staff_user = User.objects.create_user(
            username='staff_p4',
            email='staff_p4@test.com',
            password='password123',
            is_staff=True
        )

        self.future_date = timezone.now().date() + timedelta(days=2)

    def test_pause_and_resume_availability_workflow(self):
        """Phase 4: Approved mentor can pause availability, disappearing from marketplace, and resume."""
        self.client.force_login(self.mentor_user)

        # 1. Pause availability
        res_pause = self.client.post(reverse('community:pause_availability'))
        self.assertRedirects(res_pause, reverse('community:mentor_dashboard'))

        self.mentor_profile.refresh_from_db()
        self.assertTrue(self.mentor_profile.is_paused)
        self.assertIsNotNone(self.mentor_profile.paused_at)

        # 2. Marketplace excludes paused mentor
        self.client.force_login(self.student_user)
        market_res = self.client.get(reverse('community:mentor_list'))
        self.assertNotContains(market_res, 'Dr. Gordon Freeman')

        # 3. Direct booking attempt is rejected
        booking_res = self.client.post(
            reverse('community:book_session', args=[self.mentor_profile.id]),
            {
                "requested_date": self.future_date.strftime("%Y-%m-%d"),
                "requested_time": "10:00:00",
                "purpose": "Career Guidance",
                "student_message": "Trying to book paused mentor"
            }
        )
        self.assertEqual(booking_res.status_code, 302)
        self.assertEqual(MentorshipRequest.objects.count(), 0)

        # 4. Resume availability
        self.client.force_login(self.mentor_user)
        res_resume = self.client.post(reverse('community:resume_availability'))
        self.assertRedirects(res_resume, reverse('community:mentor_dashboard'))

        self.mentor_profile.refresh_from_db()
        self.assertFalse(self.mentor_profile.is_paused)
        self.assertIsNone(self.mentor_profile.paused_at)

        # 5. Marketplace now displays mentor
        self.client.force_login(self.student_user)
        market_res2 = self.client.get(reverse('community:mentor_list'))
        self.assertContains(market_res2, 'Dr. Gordon Freeman')

    def test_pause_availability_preserves_existing_sessions(self):
        """Phase 4: Pausing availability leaves scheduled accepted sessions intact and mentor workspace accessible."""
        req = MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date=self.future_date,
            requested_time="10:00:00",
            purpose="Career Guidance",
            status="Accepted"
        )
        self.client.force_login(self.mentor_user)
        self.client.post(reverse('community:pause_availability'))

        # Session remains Accepted
        req.refresh_from_db()
        self.assertEqual(req.status, 'Accepted')

        # Mentor can still access mentor dashboard
        dash_res = self.client.get(reverse('community:mentor_dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, 'Availability Paused')

    def test_step_down_blocked_by_unresolved_accepted_sessions(self):
        """Phase 4: Mentor cannot step down while accepted sessions remain unresolved."""
        MentorshipRequest.objects.create(
            student=self.student_user,
            mentor=self.mentor_profile,
            requested_date=self.future_date,
            requested_time="10:00:00",
            purpose="Roadmap Discussion",
            status="Accepted"
        )
        self.client.force_login(self.mentor_user)

        # GET confirms step-down is blocked
        get_res = self.client.get(reverse('community:mentor_step_down'))
        self.assertEqual(get_res.status_code, 200)
        self.assertFalse(get_res.context['eligible'])
        self.assertContains(get_res, 'Step-down blocked')

        # POST is rejected
        post_res = self.client.post(reverse('community:mentor_step_down'), {'reason': 'Stepping down'})
        self.assertRedirects(post_res, reverse('community:mentor_step_down'))

        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.status, 'Approved')

    def test_step_down_execution_cancels_pending_requests_and_notifies_students(self):
        """Phase 4: Step-down cancels pending requests, notifies students, and sets status to Inactive."""
        student2 = User.objects.create_user(username='student_two', email='s2@test.com', password='pw')

        req1 = MentorshipRequest.objects.create(
            student=self.student_user, mentor=self.mentor_profile,
            requested_date=self.future_date, requested_time="10:00:00",
            purpose="Career Guidance", status="Pending"
        )
        req2 = MentorshipRequest.objects.create(
            student=student2, mentor=self.mentor_profile,
            requested_date=self.future_date, requested_time="11:00:00",
            purpose="Resume Review", status="Pending"
        )

        self.client.force_login(self.mentor_user)
        res = self.client.post(reverse('community:mentor_step_down'), {'reason': 'Taking a sabbatical'})
        self.assertRedirects(res, reverse('dashboard'))

        # Mentor profile state
        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.status, 'Inactive')
        self.assertTrue(self.mentor_profile.is_paused)
        self.assertIsNotNone(self.mentor_profile.stepped_down_at)

        # Both pending requests cancelled
        req1.refresh_from_db()
        req2.refresh_from_db()
        self.assertEqual(req1.status, 'Cancelled')
        self.assertEqual(req2.status, 'Cancelled')

        # Session role reset
        self.assertEqual(self.client.session.get('active_role'), 'student')

    def test_stepped_down_mentor_denied_mentor_workspace(self):
        """Phase 4: Inactive mentors cannot access mentor workspace and are clamped to student."""
        self.mentor_profile.status = 'Inactive'
        self.mentor_profile.is_paused = True
        self.mentor_profile.save()

        self.client.force_login(self.mentor_user)

        # Cannot switch to mentor role
        switch_res = self.client.post(reverse('community:switch_workspace'), {'role': 'mentor'})
        self.assertRedirects(switch_res, reverse('dashboard'))
        self.assertEqual(self.client.session.get('active_role'), 'student')

        # Visiting mentor dashboard renders mentor_status.html with reactivate option
        dash_res = self.client.get(reverse('community:mentor_dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, 'Mentor Account Inactive')
        self.assertContains(dash_res, 'Reactivate Mentor Profile')

    def test_reactivate_inactive_mentor(self):
        """Phase 4: Inactive mentor can self-reactivate without administrative re-approval."""
        self.mentor_profile.status = 'Inactive'
        self.mentor_profile.is_paused = True
        self.mentor_profile.save()

        self.client.force_login(self.mentor_user)

        reactivate_res = self.client.post(
            reverse('community:reactivate_mentor'),
            {'resume_bookings': '1'}
        )
        self.assertRedirects(reactivate_res, reverse('community:mentor_dashboard'))

        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.status, 'Approved')
        self.assertTrue(self.mentor_profile.verified)
        self.assertFalse(self.mentor_profile.is_paused)
        self.assertEqual(self.client.session.get('active_role'), 'mentor')

    def test_reactivate_blocked_mentor_prohibited(self):
        """Phase 4: Administratively blocked mentors cannot self-reactivate."""
        self.mentor_profile.status = 'Blocked'
        self.mentor_profile.verified = False
        self.mentor_profile.save()

        self.client.force_login(self.mentor_user)
        res = self.client.post(reverse('community:reactivate_mentor'))
        self.assertRedirects(res, reverse('dashboard'))

        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.status, 'Blocked')

    def test_admin_blocking_mentor_cancels_pending_requests(self):
        """Phase 4: Admin blocking a mentor automatically cancels pending requests with student alerts."""
        req = MentorshipRequest.objects.create(
            student=self.student_user, mentor=self.mentor_profile,
            requested_date=self.future_date, requested_time="10:00:00",
            purpose="Career Guidance", status="Pending"
        )
        self.client.force_login(self.staff_user)

        res = self.client.post(
            reverse('community:admin_action', args=[self.mentor_profile.id, 'block'])
        )
        self.assertRedirects(res, reverse('community:admin_verify'))

        self.mentor_profile.refresh_from_db()
        self.assertEqual(self.mentor_profile.status, 'Blocked')

        req.refresh_from_db()
        self.assertEqual(req.status, 'Cancelled')

    def test_lifecycle_get_mutations_rejected(self):
        """Phase 4: GET requests cannot mutate lifecycle states (require POST)."""
        self.client.force_login(self.mentor_user)

        # GET pause -> 405
        res1 = self.client.get(reverse('community:pause_availability'))
        self.assertEqual(res1.status_code, 405)

        # GET resume -> 405
        res2 = self.client.get(reverse('community:resume_availability'))
        self.assertEqual(res2.status_code, 405)

        # GET reactivate -> 405
        res3 = self.client.get(reverse('community:reactivate_mentor'))
        self.assertEqual(res3.status_code, 405)

    def test_unauthenticated_lifecycle_access_redirects(self):
        """Phase 4: Unauthenticated access to lifecycle endpoints is redirected to login."""
        urls = [
            reverse('community:pause_availability'),
            reverse('community:resume_availability'),
            reverse('community:mentor_step_down'),
            reverse('community:reactivate_mentor'),
        ]
        for url in urls:
            res = self.client.post(url)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/accounts/login/', res.url)
