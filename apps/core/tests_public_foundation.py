from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.core.context_processors import canonical_context
from apps.profiles.models import StudentProfile

User = get_user_model()


class PublicWebsiteFoundationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.student_user = User.objects.create_user(
            username='teststudent',
            email='student@example.com',
            password='password123',
            role='student'
        )
        StudentProfile.objects.create(
            user=self.student_user,
            college='Engineering College',
            degree='B.Tech',
            branch='Computer Science',
            career_goal='Software Engineer',
            skills='Python, Django'
        )

    def test_anonymous_visitor_can_access_homepage(self):
        """Anonymous visitor receives HTTP 200 on the public homepage with valid layout and SEO tags."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        # Tagline and purpose
        content = response.content.decode('utf-8')
        self.assertIn("CareerCatalyst — Learn. Build. Innovate.", content)
        self.assertIn("Stop guessing what to learn next.", content)

        # SEO Metadata & Social tags
        self.assertIn('<meta name="robots" content="index, follow">', content)
        self.assertIn('rel="canonical"', content)
        self.assertIn('property="og:title"', content)
        self.assertIn('name="twitter:card"', content)
        self.assertIn('"@type": "WebApplication"', content)

        # Expected homepage sections
        self.assertIn('id="hero"', content)
        self.assertIn('id="journey"', content)
        self.assertIn('id="roadmaps"', content)
        self.assertIn('id="features"', content)
        self.assertIn('id="audience"', content)
        self.assertIn('id="principles"', content)
        self.assertIn('id="faq"', content)
        self.assertIn('id="cta"', content)

    def test_anonymous_navbar_contains_expected_public_links(self):
        """Anonymous navigation displays public links without exposing private workspace controls."""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        # Public navigation items
        self.assertIn('>Home<', content)
        self.assertIn('>Roadmaps<', content)
        self.assertIn('>Features<', content)
        self.assertIn('>How It Works<', content)
        self.assertIn('>Career Journey<', content)
        self.assertIn('>FAQ<', content)
        self.assertIn('>Login<', content)
        self.assertIn('>Get Started<', content)

        # Workspace-only items must NOT be visible to anonymous visitors
        self.assertNotIn('notificationDropdown', content)
        self.assertNotIn('Job CRM & Tracker', content)
        self.assertNotIn('Resume History', content)
        self.assertNotIn('Sign Out', content)

    def test_authenticated_student_redirect_from_homepage(self):
        """Authenticated student visiting '/' is redirected to their workspace dashboard."""
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

    def test_canonical_context_processor(self):
        """Verifies canonical context processor returns expected origin and host."""
        request = self.factory.get('/test-page/')
        context = canonical_context(request)
        self.assertIn('CANONICAL_ORIGIN', context)
        self.assertIn('CANONICAL_HOSTNAME', context)
        self.assertIn('CANONICAL_PROTOCOL', context)
        self.assertTrue(context['CANONICAL_ORIGIN'].startswith('http'))

    def test_authenticated_user_receives_noindex_robots_directive(self):
        """When an authenticated user renders a layout extending base.html, robots tag is noindex."""
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('<meta name="robots" content="noindex, nofollow">', content)
        self.assertNotIn('<meta name="robots" content="index, follow">', content)
