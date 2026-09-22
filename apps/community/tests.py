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
