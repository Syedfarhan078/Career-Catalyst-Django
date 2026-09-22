import json
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.profiles.models import StudentProfile
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

    def test_parse_empty_or_invalid_url(self):
        self.assertEqual(parse_job_url(""), {"company_name": "", "platform": "Direct Company Page"})
        self.assertEqual(parse_job_url(None), {"company_name": "", "platform": "Direct Company Page"})
        res = parse_job_url("not-a-valid-url")
        self.assertIn("company_name", res)


class JobApplicationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tracker_student",
            email="student@example.com",
            password="testpassword123",
            first_name="Farhan",
            last_name="Ahmed"
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            career_goal="Full-Stack Developer",
            preferred_domain="Web Development",
            skills="Python, Django, React, SQL"
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
        self.assertTrue(ghosted_app.is_ghosted)

        # Test applied_time_display
        today_app = JobApplication.objects.create(
            user=self.user,
            company_name="Stripe",
            role_title="Backend Intern",
            applied_date=today,
            status="applied"
        )
        yesterday_app = JobApplication.objects.create(
            user=self.user,
            company_name="Vercel",
            role_title="Frontend Engineer",
            applied_date=today - timedelta(days=1),
            status="applied"
        )
        old_app = JobApplication.objects.create(
            user=self.user,
            company_name="Oracle",
            role_title="Database Engineer",
            applied_date=today - timedelta(days=40),
            status="applied"
        )

        self.assertEqual(today_app.applied_time_display, "Today")
        self.assertEqual(yesterday_app.applied_time_display, "Yesterday")
        self.assertEqual(recent_app.applied_time_display, "2 days ago")
        self.assertEqual(ghosted_app.applied_time_display, "16 days ago")
        self.assertEqual(old_app.applied_time_display, (today - timedelta(days=40)).strftime("%b %d, %Y"))

    def test_status_choices_includes_withdrawn(self):
        statuses = [choice[0] for choice in JobApplication.STATUS_CHOICES]
        self.assertIn("withdrawn", statuses)
        self.assertIn("offer", statuses)
        self.assertIn("rejected", statuses)
        self.assertIn("interview", statuses)
        self.assertIn("assessment", statuses)
        self.assertIn("referral_requested", statuses)
        self.assertIn("applied", statuses)
        self.assertIn("bookmarked", statuses)

    def test_generate_follow_up_email_with_profile(self):
        today = timezone.now().date()
        app = JobApplication.objects.create(
            user=self.user,
            company_name="Razorpay",
            role_title="Backend Intern",
            applied_date=today - timedelta(days=6),
            status="applied",
            contact_person="Priya Sharma"
        )
        data = generate_follow_up_email(app, self.user)
        self.assertIn("Razorpay", data["subject"])
        self.assertIn("Backend Intern", data["body"])
        self.assertIn("Farhan Ahmed", data["body"])
        self.assertIn("Python", data["body"])
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
        self.profile = StudentProfile.objects.create(
            user=self.user,
            career_goal="Full-Stack Developer",
            preferred_domain="Web Development"
        )
        self.other_user = User.objects.create_user(
            username="other_user",
            email="other@example.com",
            password="otherpassword",
            first_name="Jane",
            last_name="Doe"
        )
        self.client.login(username="tracker_user", password="secretpassword")

    def test_kanban_view_unauthenticated_redirects(self):
        anon_client = Client()
        response = anon_client.get(reverse('tracker:kanban'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_kanban_view_authenticated(self):
        response = self.client.get(reverse('tracker:kanban'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Application Tracker")
        self.assertContains(response, "Full-Stack Developer")
        self.assertIn('columns', response.context)
        self.assertIn('user_initials', response.context)
        self.assertEqual(response.context['user_initials'], 'SF')
        self.assertEqual(response.context['target_career'], 'Full-Stack Developer')

    def test_kanban_view_all_8_columns_present(self):
        response = self.client.get(reverse('tracker:kanban'))
        self.assertEqual(response.status_code, 200)
        col_ids = [c['id'] for c in response.context['columns']]
        expected_cols = [
            'bookmarked', 'applied', 'referral_requested', 'assessment',
            'interview', 'offer', 'rejected', 'withdrawn'
        ]
        self.assertEqual(col_ids, expected_cols)

    def test_kanban_view_metrics_calculation(self):
        today = timezone.now().date()
        # Create applications across stages
        JobApplication.objects.create(user=self.user, company_name="Co1", role_title="R1", status="applied", applied_date=today - timedelta(days=7))
        JobApplication.objects.create(user=self.user, company_name="Co2", role_title="R2", status="assessment", applied_date=today)
        JobApplication.objects.create(user=self.user, company_name="Co3", role_title="R3", status="interview", applied_date=today)
        JobApplication.objects.create(user=self.user, company_name="Co4", role_title="R4", status="offer", applied_date=today)

        response = self.client.get(reverse('tracker:kanban'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_apps'], 4)
        self.assertEqual(response.context['interviews_count'], 1)
        self.assertEqual(response.context['offers_count'], 1)
        self.assertEqual(response.context['follow_up_needed_count'], 1)
        # Responses count = 1 assessment + 1 interview + 1 offer = 3 / 4 = 75.0%
        self.assertEqual(response.context['response_rate'], 75.0)

    def test_kanban_view_search_query_filter(self):
        JobApplication.objects.create(user=self.user, company_name="Atlassian", role_title="Dev", status="applied")
        JobApplication.objects.create(user=self.user, company_name="Google", role_title="SDE", status="applied")

        response = self.client.get(reverse('tracker:kanban') + '?q=Atlassian')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_apps'], 1)
        self.assertEqual(response.context['all_apps'][0].company_name, "Atlassian")

    def test_kanban_view_job_type_filter(self):
        JobApplication.objects.create(user=self.user, company_name="CoA", role_title="Dev", job_type="Internship", status="applied")
        JobApplication.objects.create(user=self.user, company_name="CoB", role_title="SDE", job_type="Full-Time", status="applied")

        response = self.client.get(reverse('tracker:kanban') + '?job_type=Internship')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_apps'], 1)
        self.assertEqual(response.context['all_apps'][0].company_name, "CoA")

    def test_kanban_view_empty_state_and_filtered_empty(self):
        # Empty state with 0 apps
        response = self.client.get(reverse('tracker:kanban'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your job search pipeline is empty")

        # Empty state with search filter
        JobApplication.objects.create(user=self.user, company_name="Netflix", role_title="Eng", status="applied")
        response_search = self.client.get(reverse('tracker:kanban') + '?q=NonExistentCompany')
        self.assertEqual(response_search.status_code, 200)
        self.assertContains(response_search, "No matching applications found")

    def test_add_application_view_success(self):
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

    def test_add_application_view_invalid(self):
        # Missing role_title
        response = self.client.post(reverse('tracker:add'), {
            'company_name': 'Atlassian',
            'role_title': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(JobApplication.objects.filter(company_name='Atlassian', user=self.user).exists())

    def test_edit_application_get_json(self):
        app = JobApplication.objects.create(
            user=self.user,
            company_name="Datadog",
            role_title="Support Eng",
            status="interview",
            location="Remote",
            salary_or_stipend="12 LPA"
        )
        response = self.client.get(reverse('tracker:edit', kwargs={'pk': app.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['company_name'], "Datadog")
        self.assertEqual(data['role_title'], "Support Eng")
        self.assertEqual(data['status'], "interview")
        self.assertEqual(data['location'], "Remote")
        self.assertEqual(data['salary_or_stipend'], "12 LPA")

    def test_edit_application_post_update(self):
        app = JobApplication.objects.create(
            user=self.user,
            company_name="Datadog",
            role_title="Support Eng",
            status="applied"
        )
        response = self.client.post(reverse('tracker:edit', kwargs={'pk': app.id}), {
            'company_name': 'Datadog Inc',
            'role_title': 'Senior Support Eng',
            'job_type': 'Full-Time',
            'status': 'interview',
            'location': 'Bangalore',
            'applied_date': timezone.now().date().strftime('%Y-%m-%d'),
        })
        self.assertEqual(response.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.company_name, "Datadog Inc")
        self.assertEqual(app.role_title, "Senior Support Eng")
        self.assertEqual(app.status, "interview")

    def test_delete_application(self):
        app = JobApplication.objects.create(
            user=self.user,
            company_name="Canva",
            role_title="Design Eng",
            status="bookmarked"
        )
        response = self.client.post(reverse('tracker:delete', kwargs={'pk': app.id}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(JobApplication.objects.filter(pk=app.id).exists())

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
            data=json.dumps({'status': 'offer'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'offer')
        self.assertTrue(data['is_offer'])
        app.refresh_from_db()
        self.assertEqual(app.status, 'offer')

    def test_api_update_status_invalid(self):
        app = JobApplication.objects.create(
            user=self.user,
            company_name='Uber',
            role_title='SWE-1',
            status='applied'
        )
        url = reverse('tracker:api_update_status', kwargs={'pk': app.id})
        response = self.client.post(
            url,
            data=json.dumps({'status': 'invalid_stage'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_api_parse_url(self):
        url = reverse('tracker:api_parse_url') + "?url=https://boards.greenhouse.io/postman/jobs/123"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["company_name"], "Postman")

    def test_api_generate_followup(self):
        app = JobApplication.objects.create(
            user=self.user,
            company_name='Figma',
            role_title='Frontend Dev',
            status='applied'
        )
        url = reverse('tracker:api_followup', kwargs={'pk': app.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Figma", data['subject'])
        self.assertIn("Frontend Dev", data['body'])

    def test_ownership_isolation(self):
        # Application owned by other_user
        other_app = JobApplication.objects.create(
            user=self.other_user,
            company_name="SecretCo",
            role_title="Secret Role",
            status="applied"
        )

        # User cannot GET edit JSON for another user's application
        response_edit_get = self.client.get(reverse('tracker:edit', kwargs={'pk': other_app.id}))
        self.assertEqual(response_edit_get.status_code, 404)

        # User cannot POST edit update to another user's application
        response_edit_post = self.client.post(reverse('tracker:edit', kwargs={'pk': other_app.id}), {
            'company_name': 'HackedCo',
            'role_title': 'Hacked Role',
            'job_type': 'Full-Time',
            'status': 'applied',
        })
        self.assertEqual(response_edit_post.status_code, 404)

        # User cannot delete another user's application
        response_delete = self.client.post(reverse('tracker:delete', kwargs={'pk': other_app.id}))
        self.assertEqual(response_delete.status_code, 404)
        self.assertTrue(JobApplication.objects.filter(pk=other_app.id).exists())

        # User cannot update status of another user's application
        response_status = self.client.post(
            reverse('tracker:api_update_status', kwargs={'pk': other_app.id}),
            data=json.dumps({'status': 'rejected'}),
            content_type='application/json'
        )
        self.assertEqual(response_status.status_code, 404)

        # User cannot generate followup for another user's application
        response_followup = self.client.get(reverse('tracker:api_followup', kwargs={'pk': other_app.id}))
        self.assertEqual(response_followup.status_code, 404)

        # Kanban view of User does not list other_user's app
        response_kanban = self.client.get(reverse('tracker:kanban'))
        self.assertNotContains(response_kanban, "SecretCo")
