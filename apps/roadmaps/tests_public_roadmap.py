from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.roadmaps.models import CareerPath, Milestone, Topic, UserRoadmap, TopicProgress
from apps.profiles.models import StudentProfile

User = get_user_model()


class PublicRoadmapCatalogueAndDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='teststudent',
            email='student@example.com',
            password='Password123!',
            first_name='Farhan',
            last_name='Ahmed'
        )
        cls.profile = StudentProfile.objects.create(
            user=cls.user,
            career_goal='Backend Engineering',
            college='Engineering Institute',
            degree='B.Tech',
            branch='Computer Science'
        )

        # Active Career Path
        cls.path_active = CareerPath.objects.create(
            name='Backend Engineering',
            slug='backend-engineering',
            description='Comprehensive roadmap for backend architecture, APIs, and databases.',
            icon='bi-server',
            estimated_weeks=10,
            difficulty='Intermediate',
            is_active=True
        )
        cls.ms1 = Milestone.objects.create(
            career_path=cls.path_active,
            week_number=1,
            title='Core Backend Foundations',
            description='HTTP protocol and REST concepts.',
            level='Beginner',
            order=1
        )
        cls.t1 = Topic.objects.create(
            milestone=cls.ms1,
            title='HTTP Protocol & Methods',
            description='Learn GET, POST, PUT, DELETE semantics.',
            resource_url='https://developer.mozilla.org/en-US/docs/Web/HTTP',
            resource_type='Documentation',
            estimated_hours=3.0,
            skills_taught='HTTP, Web Protocols, Networking',
            order=1
        )
        cls.t2 = Topic.objects.create(
            milestone=cls.ms1,
            title='REST API Architecture',
            description='REST constraints and status codes.',
            resource_url='https://restfulapi.net/',
            resource_type='Article',
            estimated_hours=2.5,
            skills_taught='REST APIs, API Design',
            order=2
        )

        cls.ms2 = Milestone.objects.create(
            career_path=cls.path_active,
            week_number=2,
            title='Relational Databases',
            description='PostgreSQL and SQL queries.',
            level='Intermediate',
            order=2
        )
        cls.t3 = Topic.objects.create(
            milestone=cls.ms2,
            title='SQL & PostgreSQL Indexing',
            description='Relational modeling and indexes.',
            resource_url='https://www.postgresql.org/docs/',
            resource_type='Documentation',
            estimated_hours=4.0,
            skills_taught='SQL, PostgreSQL, Database Optimization',
            order=1
        )

        # Inactive Career Path (should NOT be visible publicly)
        cls.path_inactive = CareerPath.objects.create(
            name='Draft Roadmap',
            slug='draft-roadmap',
            description='Unpublished draft roadmap.',
            icon='bi-cone-striped',
            estimated_weeks=8,
            difficulty='Beginner',
            is_active=False
        )

    def test_public_catalogue_anonymous_access(self):
        """Anonymous visitor can access /roadmaps/ and see active paths."""
        response = self.client.get(reverse('roadmaps:path_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Backend Engineering')
        self.assertNotContains(response, 'Draft Roadmap')
        self.assertContains(response, '10 Weeks')
        self.assertContains(response, 'HTTP')
        # Ensure public layout is used and no private progress is exposed
        self.assertNotContains(response, '0 of 3 lessons')

    def test_public_catalogue_search_and_filter(self):
        """Filtering by difficulty and search query works properly."""
        response = self.client.get(reverse('roadmaps:path_list') + '?difficulty=Intermediate')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Backend Engineering')

        # Filter by different difficulty should exclude it
        response_diff = self.client.get(reverse('roadmaps:path_list') + '?difficulty=Advanced')
        self.assertEqual(response_diff.status_code, 200)
        self.assertNotContains(response_diff, 'Backend Engineering')

        # Search query matching
        response_search = self.client.get(reverse('roadmaps:path_list') + '?q=Backend')
        self.assertEqual(response_search.status_code, 200)
        self.assertContains(response_search, 'Backend Engineering')

    def test_public_detail_anonymous_access(self):
        """Anonymous visitor can access /roadmaps/<slug>/ with full curriculum information."""
        response = self.client.get(reverse('roadmaps:path_detail', kwargs={'slug': 'backend-engineering'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Backend Engineering Roadmap')
        self.assertContains(response, 'Core Backend Foundations')
        self.assertContains(response, 'Relational Databases')
        self.assertContains(response, 'HTTP Protocol &amp; Methods')
        self.assertContains(response, 'https://developer.mozilla.org/en-US/docs/Web/HTTP')
        self.assertContains(response, 'Official Docs')
        self.assertContains(response, 'Enroll in Roadmap (Free)')

    def test_public_detail_inactive_returns_404(self):
        """Inactive or unpublished paths return HTTP 404 on public route."""
        response = self.client.get(reverse('roadmaps:path_detail', kwargs={'slug': 'draft-roadmap'}))
        self.assertEqual(response.status_code, 404)

    def test_public_detail_invalid_slug_returns_404(self):
        """Non-existent roadmap slug returns HTTP 404."""
        response = self.client.get(reverse('roadmaps:path_detail', kwargs={'slug': 'non-existent-track'}))
        self.assertEqual(response.status_code, 404)

    def test_public_pages_indexing_directives_anonymous_and_authenticated(self):
        """Public pages must render 'index, follow' regardless of user authentication state."""
        # Anonymous visitor
        resp_anon_list = self.client.get(reverse('roadmaps:path_list'))
        self.assertContains(resp_anon_list, '<meta name="robots" content="index, follow">')

        resp_anon_detail = self.client.get(reverse('roadmaps:path_detail', kwargs={'slug': 'backend-engineering'}))
        self.assertContains(resp_anon_detail, '<meta name="robots" content="index, follow">')

        # Authenticated visitor visiting public page must STILL receive index, follow
        self.client.force_login(self.user)
        resp_auth_list = self.client.get(reverse('roadmaps:path_list'))
        self.assertContains(resp_auth_list, '<meta name="robots" content="index, follow">')

        resp_auth_detail = self.client.get(reverse('roadmaps:path_detail', kwargs={'slug': 'backend-engineering'}))
        self.assertContains(resp_auth_detail, '<meta name="robots" content="index, follow">')

    def test_public_pages_canonical_urls(self):
        """Public pages must render production canonical URLs."""
        resp = self.client.get(reverse('roadmaps:path_detail', kwargs={'slug': 'backend-engineering'}))
        self.assertContains(resp, '<link rel="canonical" href="https://career-catalyst-ad5m.onrender.com/roadmaps/backend-engineering/">')

    def test_public_pages_structured_data(self):
        """Public detail renders BreadcrumbList and Course JSON-LD schema."""
        resp = self.client.get(reverse('roadmaps:path_detail', kwargs={'slug': 'backend-engineering'}))
        self.assertContains(resp, '"@type": "Course"')
        self.assertContains(resp, '"@type": "BreadcrumbList"')
        self.assertContains(resp, '"name": "Backend Engineering Roadmap"')

    def test_private_interactive_roadmap_requires_auth(self):
        """Anonymous visitor attempting to view /dashboard/roadmaps/<slug>/ is redirected to login."""
        response = self.client.get(reverse('roadmaps:learning_detail', kwargs={'slug': 'backend-engineering'}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_private_interactive_roadmap_authenticated_enrolled_access(self):
        """Authenticated student can view their interactive learning console at /dashboard/roadmaps/<slug>/."""
        self.client.force_login(self.user)
        # Enroll user
        enroll_resp = self.client.post(reverse('roadmaps:enroll', kwargs={'slug': 'backend-engineering'}))
        self.assertEqual(enroll_resp.status_code, 302)
        self.assertRedirects(enroll_resp, reverse('roadmaps:learning_detail', kwargs={'slug': 'backend-engineering'}))

        # Access interactive console
        response = self.client.get(reverse('roadmaps:learning_detail', kwargs={'slug': 'backend-engineering'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dash-shell')
        self.assertContains(response, 'data-topic-id=')
        # Private console must output noindex, nofollow
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')

    def test_private_my_roadmap_requires_auth(self):
        """Anonymous visitor attempting to access /roadmaps/my/ is redirected to login."""
        response = self.client.get(reverse('roadmaps:my_roadmap'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_private_my_roadmap_authenticated_displays_workspace(self):
        """Authenticated student accessing /roadmaps/my/ gets their workspace hub with noindex."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('roadmaps:my_roadmap'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dash-shell')
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')

    def test_enrollment_redirects_to_learning_console(self):
        """Enrolling in a roadmap redirects to the private interactive console /dashboard/roadmaps/<slug>/."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('roadmaps:enroll', kwargs={'slug': 'backend-engineering'}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('roadmaps:learning_detail', kwargs={'slug': 'backend-engineering'}))

        # Re-enrolling does not create duplicate and still redirects to learning console
        re_enroll_resp = self.client.post(reverse('roadmaps:enroll', kwargs={'slug': 'backend-engineering'}))
        self.assertEqual(re_enroll_resp.status_code, 302)
        self.assertRedirects(re_enroll_resp, reverse('roadmaps:learning_detail', kwargs={'slug': 'backend-engineering'}))
        self.assertEqual(UserRoadmap.objects.filter(user=self.user, career_path=self.path_active).count(), 1)

    def test_topic_progress_toggle_ajax(self):
        """Topic progress toggle via AJAX works and returns progress percentage."""
        self.client.force_login(self.user)
        self.client.post(reverse('roadmaps:enroll', kwargs={'slug': 'backend-engineering'}))

        # Toggle first topic
        toggle_resp = self.client.post(reverse('roadmaps:toggle_topic', kwargs={'topic_id': self.t1.id}))
        self.assertEqual(toggle_resp.status_code, 200)
        data = toggle_resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_completed'])
        self.assertEqual(data['completed_count'], 1)
        self.assertEqual(data['total_topics'], 3)
        self.assertEqual(data['progress_percentage'], 33)

        # Untoggle first topic
        untoggle_resp = self.client.post(reverse('roadmaps:toggle_topic', kwargs={'topic_id': self.t1.id}))
        self.assertEqual(untoggle_resp.status_code, 200)
        data2 = untoggle_resp.json()
        self.assertTrue(data2['success'])
        self.assertFalse(data2['is_completed'])
        self.assertEqual(data2['progress_percentage'], 0)

    def test_route_resolution_architecture(self):
        """Mandatory Phase 3 URL architecture resolves to the exact expected paths."""
        self.assertEqual(reverse('roadmaps:path_list'), '/roadmaps/')
        self.assertEqual(reverse('roadmaps:path_detail', kwargs={'slug': 'backend-engineering'}), '/roadmaps/backend-engineering/')
        self.assertEqual(reverse('roadmaps:learning_detail', kwargs={'slug': 'backend-engineering'}), '/dashboard/roadmaps/backend-engineering/')
        self.assertEqual(reverse('roadmaps:my_roadmap'), '/roadmaps/my/')
        self.assertEqual(reverse('roadmaps:enroll', kwargs={'slug': 'backend-engineering'}), '/roadmaps/backend-engineering/enroll/')
        self.assertEqual(reverse('roadmaps:toggle_topic', kwargs={'topic_id': 42}), '/roadmaps/api/toggle/42/')

    def test_sitemap_includes_public_roadmaps_and_excludes_private_ones(self):
        """Sitemap includes public catalogue and active roadmaps, but excludes private consoles."""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        # Public catalogue
        self.assertIn('<loc>https://career-catalyst-ad5m.onrender.com/roadmaps/</loc>', content)
        # Active roadmap detail
        self.assertIn('<loc>https://career-catalyst-ad5m.onrender.com/roadmaps/backend-engineering/</loc>', content)
        # Draft inactive roadmap must NOT be in sitemap
        self.assertNotIn('draft-roadmap', content)
        # Private learning console must NOT be in sitemap
        self.assertNotIn('/dashboard/roadmaps/', content)
        self.assertNotIn('/roadmaps/my/', content)
        self.assertNotIn('/roadmaps/api/', content)

    def test_robots_txt_rules(self):
        """robots.txt allows public roadmaps while disallowing private roadmap endpoints."""
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Allow: /roadmaps/$', content)
        self.assertIn('Allow: /roadmaps/*', content)
        self.assertIn('Disallow: /roadmaps/my/', content)
        self.assertIn('Disallow: /roadmaps/certificate/', content)
        self.assertIn('Disallow: /roadmaps/api/', content)
        self.assertIn('Disallow: /roadmaps/*/enroll/', content)
        self.assertIn('Disallow: /dashboard/', content)


class RoadmapBackNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            username='navstudent',
            email='navstudent@example.com',
            password='Password123!',
            first_name='Syed',
            last_name='Ahmed'
        )
        cls.profile = StudentProfile.objects.create(
            user=cls.student,
            career_goal='Cloud Architect'
        )
        cls.path = CareerPath.objects.create(
            name='Cloud Architecture',
            slug='cloud-architecture',
            description='Cloud path description',
            icon='bi-cloud',
            estimated_weeks=8,
            difficulty='Intermediate',
            is_active=True
        )
        cls.milestone = Milestone.objects.create(
            career_path=cls.path,
            week_number=1,
            title='Cloud Foundations',
            level='Beginner',
            order=1
        )
        cls.topic = Topic.objects.create(
            milestone=cls.milestone,
            title='Intro to Cloud Computing',
            description='Basics of virtualization and cloud models.',
            order=1
        )
        cls.user_roadmap = UserRoadmap.objects.create(
            user=cls.student,
            career_path=cls.path
        )
        TopicProgress.objects.create(
            user_roadmap=cls.user_roadmap,
            topic=cls.topic
        )

    def test_public_detail_back_navigation_with_from_catalogue(self):
        """When visiting public detail with ?from=catalogue, back link points to catalogue."""
        url = reverse('roadmaps:path_detail', kwargs={'slug': 'cloud-architecture'}) + '?from=catalogue'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['back_url'], reverse('roadmaps:path_list'))
        self.assertEqual(response.context['back_label'], 'Back to Roadmaps Catalogue')
        self.assertContains(response, reverse('roadmaps:path_list'))
        self.assertContains(response, 'Back to Roadmaps Catalogue')

    def test_public_detail_direct_access_default_fallback(self):
        """Directly opening a public roadmap URL falls back to public catalogue."""
        url = reverse('roadmaps:path_detail', kwargs={'slug': 'cloud-architecture'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['back_url'], reverse('roadmaps:path_list'))
        self.assertEqual(response.context['back_label'], 'Back to Roadmaps Catalogue')

    def test_private_console_back_navigation_from_my_roadmaps(self):
        """When opening learning console with ?from=my_roadmaps, back link returns to /roadmaps/my/."""
        self.client.force_login(self.student)
        url = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'}) + '?from=my_roadmaps'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['back_url'], reverse('roadmaps:my_roadmap'))
        self.assertEqual(response.context['back_label'], 'Back to My Roadmaps')
        self.assertContains(response, reverse('roadmaps:my_roadmap'))
        self.assertContains(response, 'Back to My Roadmaps')

    def test_private_console_back_navigation_from_dashboard(self):
        """When opening learning console with ?from=dashboard, back link returns to /dashboard/."""
        self.client.force_login(self.student)
        url = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'}) + '?from=dashboard'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['back_url'], reverse('dashboard'))
        self.assertEqual(response.context['back_label'], 'Back to Dashboard')
        self.assertContains(response, reverse('dashboard'))
        self.assertContains(response, 'Back to Dashboard')

    def test_private_console_back_navigation_from_guidance(self):
        """When opening learning console with ?from=guidance, back link returns to /recommendation/."""
        self.client.force_login(self.student)
        url = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'}) + '?from=guidance'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['back_url'], reverse('recommendation:dashboard'))
        self.assertEqual(response.context['back_label'], 'Back to Career Guidance')
        self.assertContains(response, reverse('recommendation:dashboard'))
        self.assertContains(response, 'Back to Career Guidance')

    def test_private_console_back_navigation_from_public_detail(self):
        """When opening learning console with ?from=public_detail, back link returns to roadmap overview."""
        self.client.force_login(self.student)
        url = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'}) + '?from=public_detail'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        expected_url = reverse('roadmaps:path_detail', kwargs={'slug': 'cloud-architecture'})
        self.assertEqual(response.context['back_url'], expected_url)
        self.assertEqual(response.context['back_label'], 'Back to Roadmap Overview')
        self.assertContains(response, expected_url)
        self.assertContains(response, 'Back to Roadmap Overview')

    def test_private_console_direct_access_default_fallback(self):
        """Directly opening private learning URL (no origin, no referer) falls back safely to My Roadmaps."""
        self.client.force_login(self.student)
        url = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['back_url'], reverse('roadmaps:my_roadmap'))
        self.assertEqual(response.context['back_label'], 'Back to My Roadmaps')

    def test_private_console_referer_fallback(self):
        """When no query parameter is provided, safe internal referer header is honored."""
        self.client.force_login(self.student)
        url = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'})
        response = self.client.get(url, HTTP_REFERER='http://testserver/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['back_url'], reverse('dashboard'))
        self.assertEqual(response.context['back_label'], 'Back to Dashboard')

    def test_page_refresh_preserves_navigation_context(self):
        """Refreshing a page retains the ?from= parameter in URL and back navigation."""
        self.client.force_login(self.student)
        url = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'}) + '?from=dashboard'
        # First request
        resp1 = self.client.get(url)
        self.assertEqual(resp1.context['back_url'], reverse('dashboard'))
        # Refresh (second request with same URL)
        resp2 = self.client.get(url)
        self.assertEqual(resp2.context['back_url'], reverse('dashboard'))
        self.assertEqual(resp2.context['back_label'], 'Back to Dashboard')

    def test_invalid_external_origin_falls_back_safely(self):
        """External or malicious origin query parameters are rejected and fall back safely to workspace."""
        self.client.force_login(self.student)
        # Untrusted domain in 'from'
        url_evil_from = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'}) + '?from=https://evil.com'
        resp_from = self.client.get(url_evil_from)
        self.assertEqual(resp_from.status_code, 200)
        self.assertEqual(resp_from.context['back_url'], reverse('roadmaps:my_roadmap'))

        # Open redirect attempt via 'return_to'
        url_evil_ret = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'}) + '?return_to=https://evil.com/phish'
        resp_ret = self.client.get(url_evil_ret)
        self.assertEqual(resp_ret.status_code, 200)
        self.assertEqual(resp_ret.context['back_url'], reverse('roadmaps:my_roadmap'))

        # Scheme-relative URL attack
        url_scheme_rel = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'}) + '?return_to=//evil.com'
        resp_scheme = self.client.get(url_scheme_rel)
        self.assertEqual(resp_scheme.status_code, 200)
        self.assertEqual(resp_scheme.context['back_url'], reverse('roadmaps:my_roadmap'))

    def test_anonymous_access_to_private_roadmap_redirects_to_login(self):
        """Anonymous user trying to access private interactive roadmap is redirected to login."""
        url = reverse('roadmaps:learning_detail', kwargs={'slug': 'cloud-architecture'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertIn('next=/dashboard/roadmaps/cloud-architecture/', response.url)

    def test_enrollment_preserves_origin_context(self):
        """Enrolling in a roadmap preserves ?from= origin and redirects to learning console with that context."""
        new_path = CareerPath.objects.create(
            name='DevOps Specialist',
            slug='devops-specialist',
            is_active=True
        )
        self.client.force_login(self.student)
        enroll_url = reverse('roadmaps:enroll', kwargs={'slug': 'devops-specialist'})
        response = self.client.post(enroll_url, {'from': 'public_detail'})
        self.assertEqual(response.status_code, 302)
        expected_redirect = reverse('roadmaps:learning_detail', kwargs={'slug': 'devops-specialist'}) + '?from=public_detail'
        self.assertEqual(response.url, expected_redirect)

        # Follow redirect to verify learning console renders return to public detail
        follow_resp = self.client.get(response.url)
        self.assertEqual(follow_resp.status_code, 200)
        expected_public_url = reverse('roadmaps:path_detail', kwargs={'slug': 'devops-specialist'})
        self.assertEqual(follow_resp.context['back_url'], expected_public_url)
        self.assertEqual(follow_resp.context['back_label'], 'Back to Roadmap Overview')

    def test_my_roadmaps_in_page_back_link_points_to_dashboard(self):
        """My Roadmaps hub in-page Back link returns authenticated student to /dashboard/."""
        self.client.force_login(self.student)
        response = self.client.get(reverse('roadmaps:my_roadmap'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/dashboard/"')
        self.assertContains(response, 'Back to Dashboard')
