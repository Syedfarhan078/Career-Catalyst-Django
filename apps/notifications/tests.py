from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from .models import Notification
from .services import (
    create_notification,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    get_unread_count,
    get_recent_notifications
)
from apps.community.models import MentorProfile, MentorshipRequest
from apps.community.services import (
    create_mentorship_request_service,
    respond_to_request_service,
    submit_mentor_review_service,
    review_mentor_application_service,
    register_mentor_service
)
from apps.profiles.models import StudentProfile

User = get_user_model()


class NotificationModelAndServiceTests(TestCase):
    """
    Unit tests for Notification model, service validation, deduplication, and read state.
    """
    def setUp(self):
        self.user_a = User.objects.create_user(username='alice', email='alice@test.com', password='pw')
        self.user_b = User.objects.create_user(username='bob', email='bob@test.com', password='pw')

    def test_create_notification_persists_fields(self):
        notif = create_notification(
            recipient=self.user_a,
            actor=self.user_b,
            title="Session Booked",
            message="Bob booked a session with you.",
            notification_type="mentorship_request_submitted",
            target_url="/community/mentors/dashboard/requests/"
        )
        self.assertIsNotNone(notif.pk)
        self.assertEqual(notif.recipient, self.user_a)
        self.assertEqual(notif.actor, self.user_b)
        self.assertEqual(notif.title, "Session Booked")
        self.assertEqual(notif.notification_type, "mentorship_request_submitted")
        self.assertFalse(notif.is_read)
        self.assertIsNone(notif.read_at)
        self.assertEqual(get_unread_count(self.user_a), 1)

    def test_self_notification_prevented(self):
        # An actor should not receive notifications for their own action
        notif = create_notification(
            recipient=self.user_a,
            actor=self.user_a,
            title="Self alert",
            message="You performed an action."
        )
        self.assertIsNone(notif)
        self.assertEqual(Notification.objects.count(), 0)

    def test_duplicate_notification_suppression(self):
        # Create initial notification
        notif1 = create_notification(
            recipient=self.user_a,
            actor=self.user_b,
            title="Test alert",
            message="Test message",
            notification_type="general",
            deduplicate_seconds=60
        )
        # Attempt immediate duplicate creation
        notif2 = create_notification(
            recipient=self.user_a,
            actor=self.user_b,
            title="Test alert",
            message="Test message",
            notification_type="general",
            deduplicate_seconds=60
        )
        self.assertEqual(Notification.objects.filter(recipient=self.user_a).count(), 1)
        self.assertEqual(notif1.pk, notif2.pk)

    def test_mark_as_read_persists_timestamp(self):
        notif = create_notification(
            recipient=self.user_a,
            title="Unread alert",
            message="Read me"
        )
        self.assertFalse(notif.is_read)
        self.assertEqual(get_unread_count(self.user_a), 1)

        updated = mark_notification_as_read(notif.id, self.user_a)
        self.assertIsNotNone(updated)
        self.assertTrue(updated.is_read)
        self.assertIsNotNone(updated.read_at)
        self.assertEqual(get_unread_count(self.user_a), 0)

        # Marking already-read notification again keeps it read
        updated_again = mark_notification_as_read(notif.id, self.user_a)
        self.assertTrue(updated_again.is_read)

    def test_mark_all_notifications_as_read(self):
        for i in range(3):
            create_notification(recipient=self.user_a, title=f"Alert {i}", message="Hi", deduplicate_seconds=0)
        self.assertEqual(get_unread_count(self.user_a), 3)

        count = mark_all_notifications_as_read(self.user_a)
        self.assertEqual(count, 3)
        self.assertEqual(get_unread_count(self.user_a), 0)


class MentorshipLifecycleNotificationIntegrationTests(TestCase):
    """
    Tests all required mentorship lifecycle events generate correct notifications
    to the correct recipients with accurate target URLs.
    """
    def setUp(self):
        self.student = User.objects.create_user(username='student_s', email='student@test.com', password='pw')
        self.mentor_user = User.objects.create_user(username='mentor_m', email='mentor@test.com', password='pw')
        self.staff_user = User.objects.create_user(username='admin_a', email='admin@test.com', password='pw', is_staff=True)

        StudentProfile.objects.create(user=self.student, preferred_domain='Backend')
        self.mentor_profile = MentorProfile.objects.create(
            user=self.mentor_user,
            full_name='Master Yoda',
            company='Jedi Order',
            designation='Grand Master',
            status='Approved',
            verified=True,
            available_days='Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday',
            available_time_slots='10:00 AM - 12:00 PM',
            max_sessions_per_week=10
        )

        today = timezone.now().date()
        self.booking_date = today + timedelta(days=1)

    def test_student_submits_request_notifies_mentor(self):
        req = create_mentorship_request_service(
            student=self.student,
            mentor=self.mentor_profile,
            form_cleaned_data={
                "requested_date": self.booking_date,
                "requested_time": "10:00:00",
                "purpose": "System Architecture Review",
                "student_message": "Need feedback on distributed locks."
            }
        )
        # Mentor notification
        mentor_notif = Notification.objects.filter(
            recipient=self.mentor_user,
            notification_type='mentorship_request_submitted'
        ).first()
        self.assertIsNotNone(mentor_notif)
        self.assertEqual(mentor_notif.actor, self.student)
        self.assertEqual(mentor_notif.related_request, req)
        self.assertIn("student_s", mentor_notif.message)
        self.assertEqual(mentor_notif.target_url, reverse('community:mentor_requests'))

        # Student confirmation notification
        student_notif = Notification.objects.filter(
            recipient=self.student,
            notification_type='mentorship_request_submitted'
        ).first()
        self.assertIsNotNone(student_notif)
        self.assertEqual(student_notif.target_url, reverse('community:student_bookings'))

    def test_mentor_accepts_request_notifies_student(self):
        req = MentorshipRequest.objects.create(
            student=self.student,
            mentor=self.mentor_profile,
            requested_date=self.booking_date,
            requested_time="10:00:00",
            purpose="Career Advice",
            status="Pending"
        )
        respond_to_request_service(
            request_obj=req,
            action='accept',
            response_message="Glad to connect!",
            meeting_link="https://meet.google.com/xyz-123",
            actor=self.mentor_user
        )
        student_notif = Notification.objects.filter(
            recipient=self.student,
            notification_type='mentorship_request_accepted'
        ).first()
        self.assertIsNotNone(student_notif)
        self.assertEqual(student_notif.actor, self.mentor_user)
        self.assertIn("https://meet.google.com/xyz-123", student_notif.message)
        self.assertEqual(student_notif.target_url, reverse('community:student_bookings'))

    def test_mentor_rejects_request_notifies_student(self):
        req = MentorshipRequest.objects.create(
            student=self.student,
            mentor=self.mentor_profile,
            requested_date=self.booking_date,
            requested_time="10:00:00",
            purpose="Career Advice",
            status="Pending"
        )
        respond_to_request_service(
            request_obj=req,
            action='reject',
            response_message="Schedule full at this time.",
            actor=self.mentor_user
        )
        student_notif = Notification.objects.filter(
            recipient=self.student,
            notification_type='mentorship_request_rejected'
        ).first()
        self.assertIsNotNone(student_notif)
        self.assertEqual(student_notif.actor, self.mentor_user)
        self.assertIn("Schedule full", student_notif.message)
        self.assertEqual(student_notif.target_url, reverse('community:student_bookings'))

    def test_student_cancels_pending_request_notifies_mentor(self):
        req = MentorshipRequest.objects.create(
            student=self.student,
            mentor=self.mentor_profile,
            requested_date=self.booking_date,
            requested_time="10:00:00",
            purpose="Interview Prep",
            status="Pending"
        )
        respond_to_request_service(
            request_obj=req,
            action='cancel',
            response_message="No longer needed",
            actor=self.student
        )
        mentor_notif = Notification.objects.filter(
            recipient=self.mentor_user,
            notification_type='mentorship_session_cancelled'
        ).first()
        self.assertIsNotNone(mentor_notif)
        self.assertEqual(mentor_notif.actor, self.student)
        self.assertEqual(mentor_notif.target_url, reverse('community:mentor_requests'))

    def test_mentor_cancels_accepted_session_notifies_student(self):
        req = MentorshipRequest.objects.create(
            student=self.student,
            mentor=self.mentor_profile,
            requested_date=self.booking_date,
            requested_time="10:00:00",
            purpose="Interview Prep",
            status="Accepted"
        )
        respond_to_request_service(
            request_obj=req,
            action='cancel',
            response_message="Emergency conflict arose",
            actor=self.mentor_user
        )
        student_notif = Notification.objects.filter(
            recipient=self.student,
            notification_type='mentorship_session_cancelled'
        ).first()
        self.assertIsNotNone(student_notif)
        self.assertEqual(student_notif.actor, self.mentor_user)
        self.assertEqual(student_notif.target_url, reverse('community:student_bookings'))

    def test_mentor_completes_session_notifies_student(self):
        req = MentorshipRequest.objects.create(
            student=self.student,
            mentor=self.mentor_profile,
            requested_date=self.booking_date,
            requested_time="10:00:00",
            purpose="Interview Prep",
            status="Accepted"
        )
        respond_to_request_service(
            request_obj=req,
            action='complete',
            response_message="Great session!",
            actor=self.mentor_user
        )
        student_notif = Notification.objects.filter(
            recipient=self.student,
            notification_type='mentorship_session_completed'
        ).first()
        self.assertIsNotNone(student_notif)
        self.assertEqual(student_notif.actor, self.mentor_user)
        self.assertIn("leave a review", student_notif.message.lower())
        self.assertEqual(student_notif.target_url, reverse('community:student_bookings'))

    def test_student_reviews_mentor_notifies_mentor(self):
        req = MentorshipRequest.objects.create(
            student=self.student,
            mentor=self.mentor_profile,
            requested_date=self.booking_date,
            requested_time="10:00:00",
            purpose="Interview Prep",
            status="Completed"
        )
        submit_mentor_review_service(
            student=self.student,
            mentor=self.mentor_profile,
            rating=5,
            comment="Awesome guidance!"
        )
        mentor_notif = Notification.objects.filter(
            recipient=self.mentor_user,
            notification_type='mentor_review_received'
        ).first()
        self.assertIsNotNone(mentor_notif)
        self.assertEqual(mentor_notif.actor, self.student)
        self.assertIn("5-star", mentor_notif.message)


class NotificationSecurityAndOwnershipTests(TestCase):
    """
    Security tests verifying that users cannot view, modify, or mark another user's notifications.
    """
    def setUp(self):
        self.student_a = User.objects.create_user(username='student_a', email='a@test.com', password='pw')
        self.student_b = User.objects.create_user(username='student_b', email='b@test.com', password='pw')

        self.notif_a = create_notification(
            recipient=self.student_a,
            title="A's private notification",
            message="Confidential career insight"
        )

    def test_user_cannot_mark_other_users_notification_as_read(self):
        self.client.force_login(self.student_b)
        url = reverse('notifications:mark_as_read', args=[self.notif_a.id])
        res = self.client.post(url)
        # Should be redirected with error or 404 in JSON
        self.assertRedirects(res, reverse('notifications:history'))

        # Record should remain unread
        self.notif_a.refresh_from_db()
        self.assertFalse(self.notif_a.is_read)

    def test_ajax_unauthorized_mark_as_read_returns_404(self):
        self.client.force_login(self.student_b)
        url = reverse('notifications:mark_as_read', args=[self.notif_a.id])
        res = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 404)

        self.notif_a.refresh_from_db()
        self.assertFalse(self.notif_a.is_read)

    def test_history_page_strictly_scoped_to_logged_in_user(self):
        self.client.force_login(self.student_b)
        res = self.client.get(reverse('notifications:history'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, "Confidential career insight")

        # Log in as A
        self.client.force_login(self.student_a)
        res_a = self.client.get(reverse('notifications:history'))
        self.assertEqual(res_a.status_code, 200)
        self.assertContains(res_a, "Confidential career insight")

    def test_unauthenticated_endpoints_require_login(self):
        # GET history
        res1 = self.client.get(reverse('notifications:history'))
        self.assertEqual(res1.status_code, 302)
        self.assertIn('/accounts/login/', res1.url)

        # POST mark read
        res2 = self.client.post(reverse('notifications:mark_as_read', args=[self.notif_a.id]))
        self.assertEqual(res2.status_code, 302)

        # POST mark all read
        res3 = self.client.post(reverse('notifications:mark_all_as_read'))
        self.assertEqual(res3.status_code, 302)


class NotificationViewsAndUITests(TestCase):
    """
    Tests for Notification views, history pagination, filters, and navbar context.
    """
    def setUp(self):
        self.user = User.objects.create_user(username='carol', email='carol@test.com', password='pw')
        StudentProfile.objects.create(user=self.user, preferred_domain='Backend')

        # Create 20 notifications for pagination testing
        for i in range(20):
            create_notification(
                recipient=self.user,
                title=f"Notification #{i}",
                message=f"Message body {i}",
                deduplicate_seconds=0
            )

    def test_history_pagination(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse('notifications:history'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['page_obj']), 15) # Page size 15

        res_page2 = self.client.get(reverse('notifications:history') + '?page=2')
        self.assertEqual(res_page2.status_code, 200)
        self.assertEqual(len(res_page2.context['page_obj']), 5)

    def test_unread_filter(self):
        self.client.force_login(self.user)
        # Mark first 5 as read
        for notif in Notification.objects.filter(recipient=self.user)[:5]:
            notif.mark_as_read()

        # Filter by unread
        res = self.client.get(reverse('notifications:history') + '?filter=unread')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['unread_count'], 15)

    def test_navbar_context_renders_live_counts(self):
        from django.template.loader import render_to_string
        factory = RequestFactory()
        req = factory.get('/')
        req.user = self.user
        req.session = {}

        html = render_to_string('partials/navbar.html', {
            'user': self.user,
            'unread_notifications_count': 20,
            'recent_notifications': Notification.objects.filter(recipient=self.user)[:5],
            'is_approved_mentor': False,
            'active_workspace': 'student'
        }, request=req)

        self.assertIn('20', html)
        self.assertIn('Notification #', html)
        self.assertIn('View All Notifications', html)

    def test_mark_all_as_read_ajax(self):
        self.client.force_login(self.user)
        res = self.client.post(
            reverse('notifications:mark_all_as_read'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['updated_count'], 20)
        self.assertEqual(data['unread_count'], 0)
        self.assertEqual(Notification.objects.filter(recipient=self.user, is_read=False).count(), 0)
