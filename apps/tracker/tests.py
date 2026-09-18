from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from apps.tracker.models import JobApplication
from apps.tracker.services import parse_job_url, generate_follow_up_email

User = get_user_model()


class JobTrackerServiceTests(TestCase):
    def test_parse_greenhouse_url(self):
        url = "https://boards.greenhouse.io/zepto/jobs/123456"
        res = parse_job_url(url)
        self.assertEqual(res["company_name"], "Zepto")
        self.assertEqual(res["platform"], "Greenhouse")

    def test_parse_lever_url(self):
        url = "https://jobs.lever.co/stripe/a1b2-c3d4"
        res = parse_job_url(url)
        self.assertEqual(res["company_name"], "Stripe")
        self.assertEqual(res["platform"], "Lever")

    def test_parse_wellfound_url(self):
        url = "https://wellfound.com/company/swiggy/jobs/999"
        res = parse_job_url(url)
        self.assertEqual(res["company_name"], "Swiggy")
        self.assertEqual(res["platform"], "Wellfound")

    def test_parse_linkedin_url(self):
        url = "https://www.linkedin.com/jobs/view/987654321"
        res = parse_job_url(url)
        self.assertEqual(res["platform"], "LinkedIn")

    def test_parse_direct_company_url(self):
        url = "https://careers.airbnb.com/positions/software-engineer"
        res = parse_job_url(url)
        self.assertEqual(res["company_name"], "Airbnb")


class JobApplicationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tracker_student",
            email="student@example.com",
            password="testpassword123",
            first_name="Farhan",
            last_name="Ahmed"
        )

    def test_model_follow_up_and_ghosted_properties(self):
        today = timezone.now().date()
        
        # Recent app (< 5 days)
        recent_app = JobApplication.objects.create(
            user=self.user,
            company_name="Google",
            role_title="SDE Intern",
            applied_date=today - timedelta(days=2),
            status="applied"
        )
        self.assertFalse(recent_app.needs_follow_up)
        self.assertFalse(recent_app.is_ghosted)

        # 6 days old applied app (Needs Follow-up)
        followup_app = JobApplication.objects.create(
            user=self.user,
            company_name="Microsoft",
            role_title="Software Engineer",
            applied_date=today - timedelta(days=6),
            status="applied"
        )
        self.assertTrue(followup_app.needs_follow_up)
        self.assertFalse(followup_app.is_ghosted)

        # 16 days old applied app (Ghosted)
        ghosted_app = JobApplication.objects.create(
            user=self.user,
            company_name="Amazon",
            role_title="SDE-1",
            applied_date=today - timedelta(days=16),
            status="applied"
        )
        # Test applied_time_display
        today_app = JobApplication.objects.create(
            user=self.user,
            company_name="Stripe",
            role_title="Backend Intern",
            applied_date=today,
            status="applied"
        )
        self.assertEqual(today_app.applied_time_display, "Today")
        self.assertEqual(recent_app.applied_time_display, "2 days ago")
        self.assertEqual(ghosted_app.applied_time_display, "16 days ago")

    def test_generate_follow_up_email(self):
        today = timezone.now().date()
        app = JobApplication.objects.create(
            user=self.user,
            company_name="Razorpay",
            role_title="Backend Intern",
            applied_date=today - timedelta(days=6),
            status="applied"
        )
        data = generate_follow_up_email(app, self.user)
        self.assertIn("Razorpay", data["subject"])
        self.assertIn("Backend Intern", data["body"])
        self.assertIn("Farhan Ahmed", data["body"])
        self.assertTrue(data["mailto_url"].startswith("mailto:?"))


class JobTrackerViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="tracker_user",
            email="user@example.com",
            password="secretpassword",
            first_name="Syed",
            last_name="Farhan"
        )
        self.client.login(username="tracker_user", password="secretpassword")

    def test_kanban_view_status_code(self):
        response = self.client.get(reverse('tracker:kanban'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Application Tracker")

    def test_add_application_view(self):
        response = self.client.post(reverse('tracker:add'), {
            'company_name': 'Atlassian',
            'role_title': 'Graduate SDE',
            'job_type': 'Full-Time',
            'status': 'applied',
            'location': 'Bangalore',
            'applied_date': timezone.now().date().strftime('%Y-%m-%d'),
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JobApplication.objects.filter(company_name='Atlassian', user=self.user).exists())

    def test_api_update_status(self):
        app = JobApplication.objects.create(
            user=self.user,
            company_name='Uber',
            role_title='SWE-1',
            status='applied'
        )
        url = reverse('tracker:api_update_status', kwargs={'pk': app.id})
        response = self.client.post(
            url,
            data=json.dumps({'status': 'interview'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'interview')

    def test_api_parse_url(self):
        url = reverse('tracker:api_parse_url') + "?url=https://boards.greenhouse.io/postman/jobs/123"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["company_name"], "Postman")
