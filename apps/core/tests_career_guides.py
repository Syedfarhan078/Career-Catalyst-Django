import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.core.guides_data import get_all_guides, get_guide_by_slug
from apps.profiles.models import StudentProfile
from apps.roadmaps.models import CareerPath

User = get_user_model()


class CareerGuidesHubTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            username='guidestudent',
            email='student@example.com',
            password='Password123!',
            role='student'
        )
        StudentProfile.objects.create(
            user=cls.student,
            college='Engineering Institute',
            degree='B.Tech',
            branch='Computer Science',
            career_goal='Data Scientist'
        )
        cls.path = CareerPath.objects.create(
            name='Data Scientist',
            slug='data-scientist',
            description='Data science curriculum',
            is_active=True
        )
        cls.all_guides = get_all_guides()

    def test_all_five_guides_exist_in_data_foundation(self):
        """Verify the data repository contains exactly the 5 required pillar guides."""
        self.assertEqual(len(self.all_guides), 5)
        expected_slugs = {
            'how-to-become-a-data-scientist',
            'data-analyst-vs-data-scientist-vs-ml-engineer',
            'essential-technical-skills-for-fresh-engineers',
            'how-to-build-an-industry-ready-portfolio',
            'technical-interview-preparation-guide',
        }
        actual_slugs = {g['slug'] for g in self.all_guides}
        self.assertEqual(actual_slugs, expected_slugs)

    def test_guide_listing_anonymous_access(self):
        """Anonymous visitor receives HTTP 200 on the career guides listing page."""
        response = self.client.get(reverse('guide_list'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        # Title and branding
        self.assertIn('Career Guides & Engineering Career Paths | CareerCatalyst', content)
        self.assertIn('Career Guides for Engineering Students & Graduates', content)

        # SEO indexing directives and canonical
        self.assertIn('<meta name="robots" content="index, follow">', content)
        self.assertIn('<link rel="canonical" href="https://career-catalyst-ad5m.onrender.com/career-guides/">', content)

        # All 5 guides present
        for guide in self.all_guides:
            self.assertIn(guide['title'], content)
            self.assertIn(f'href="/career-guides/{guide["slug"]}/"', content)

        # Breadcrumbs
        self.assertIn('>Career Guides<', content)

    def test_guide_listing_authenticated_access_no_redirect(self):
        """Authenticated student visiting /career-guides/ is NOT redirected to dashboard."""
        self.client.force_login(self.student)
        response = self.client.get(reverse('guide_list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('<meta name="robots" content="index, follow">', content)
        self.assertIn('Career Guides for Engineering Students & Graduates', content)

    def test_all_five_detail_pages_resolve_and_render_correctly(self):
        """Every individual guide detail page resolves with HTTP 200 and renders its content."""
        for guide in self.all_guides:
            slug = guide['slug']
            url = reverse('guide_detail', kwargs={'slug': slug})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Failed to load guide {slug}")

            content = response.content.decode('utf-8')

            # Verify title, H1, meta description
            self.assertIn(guide['h1'], content)
            self.assertIn(f'<meta name="description" content="{guide["meta_description"]}">', content)
            self.assertIn('<meta name="robots" content="index, follow">', content)

            # Canonical link
            expected_canonical = f'<link rel="canonical" href="https://career-catalyst-ad5m.onrender.com/career-guides/{slug}/">'
            self.assertIn(expected_canonical, content)

            # Table of contents anchors exist in the page body
            for toc in guide['table_of_contents']:
                self.assertIn(f'href="#{toc["id"]}"', content)
                self.assertIn(f'id="{toc["id"]}"', content)

            # Back to guides link
            self.assertIn('href="/career-guides/"', content)
            self.assertIn('Back to Career Guides', content)

            # Key takeaways present
            self.assertIn('Key Takeaways', content)
            for takeaway in guide['key_takeaways']:
                self.assertIn(takeaway, content)

            # Related roadmaps point to public routes
            for roadmap in guide.get('related_roadmaps', []):
                self.assertIn(f'href="/roadmaps/{roadmap["slug"]}/"', content)
                self.assertNotIn(f'href="/dashboard/roadmaps/{roadmap["slug"]}/"', content)

    def test_invalid_slug_returns_404(self):
        """Non-existent guide slug returns HTTP 404."""
        response = self.client.get(reverse('guide_detail', kwargs={'slug': 'non-existent-career-guide'}))
        self.assertEqual(response.status_code, 404)

    def test_structured_data_itemlist_on_listing(self):
        """Listing page contains valid ItemList JSON-LD."""
        response = self.client.get(reverse('guide_list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Find JSON-LD block
        start_marker = '<script type="application/ld+json">'
        end_marker = '</script>'
        start_idx = content.find(start_marker)
        self.assertNotEqual(start_idx, -1)
        end_idx = content.find(end_marker, start_idx)
        json_str = content[start_idx + len(start_marker):end_idx].strip()

        data = json.loads(json_str)
        self.assertEqual(data['@type'], 'ItemList')
        self.assertEqual(data['numberOfItems'], 5)
        self.assertEqual(len(data['itemListElement']), 5)
        self.assertTrue(data['itemListElement'][0]['url'].startswith('https://career-catalyst-ad5m.onrender.com/career-guides/'))

    def test_structured_data_techarticle_and_breadcrumbs_on_detail(self):
        """Detail page contains valid TechArticle and BreadcrumbList JSON-LD."""
        url = reverse('guide_detail', kwargs={'slug': 'how-to-become-a-data-scientist'})
        response = self.client.get(url)
        content = response.content.decode('utf-8')

        # Find JSON-LD block
        start_marker = '<script type="application/ld+json">'
        end_marker = '</script>'
        start_idx = content.find(start_marker)
        self.assertNotEqual(start_idx, -1)
        end_idx = content.find(end_marker, start_idx)
        json_str = content[start_idx + len(start_marker):end_idx].strip()

        data = json.loads(json_str)
        self.assertIn('@graph', data)
        types = [item['@type'] for item in data['@graph']]
        self.assertIn('BreadcrumbList', types)
        self.assertIn('TechArticle', types)

        article = next(item for item in data['@graph'] if item['@type'] == 'TechArticle')
        self.assertEqual(article['headline'], 'How to Become a Data Scientist: Complete Skills, Roadmap, and Career Guide')
        self.assertEqual(article['author']['name'], 'CareerCatalyst Editorial Team')
        self.assertEqual(article['publisher']['name'], 'CareerCatalyst')

        breadcrumbs = next(item for item in data['@graph'] if item['@type'] == 'BreadcrumbList')
        self.assertEqual(len(breadcrumbs['itemListElement']), 3)
        self.assertEqual(breadcrumbs['itemListElement'][1]['name'], 'Career Guides')

    def test_sitemap_includes_career_guides(self):
        """Sitemap index includes /career-guides/ listing and all 5 individual guides."""
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Career Guides Catalogue
        self.assertIn('<loc>https://career-catalyst-ad5m.onrender.com/career-guides/</loc>', content)

        # All 5 published guide URLs
        for guide in self.all_guides:
            expected_loc = f'<loc>https://career-catalyst-ad5m.onrender.com/career-guides/{guide["slug"]}/</loc>'
            self.assertIn(expected_loc, content)

        # Existing roadmaps must still be present
        self.assertIn('<loc>https://career-catalyst-ad5m.onrender.com/roadmaps/</loc>', content)
        self.assertIn('<loc>https://career-catalyst-ad5m.onrender.com/roadmaps/data-scientist/</loc>', content)

    def test_robots_txt_permits_career_guides(self):
        """robots.txt explicitly allows /career-guides/ and /career-guides/*."""
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Allow: /career-guides/$', content)
        self.assertIn('Allow: /career-guides/*', content)
        self.assertIn('Disallow: /dashboard/', content)

    def test_public_navbar_contains_career_guides_link(self):
        """Public navbar displays Career Guides link for anonymous visitors."""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('href="/career-guides/"', content)
        self.assertIn('>Career Guides<', content)

    def test_public_footer_contains_career_guides_link(self):
        """Public footer displays Career Guides link in Explore column."""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('href="/career-guides/"', content)
