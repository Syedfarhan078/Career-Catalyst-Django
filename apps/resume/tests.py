from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Resume, Education, Experience

User = get_user_model()

class ResumeBuilderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='password123')
        self.client.login(username='testuser', password='password123')
        
        self.resume = Resume.objects.create(
            user=self.user,
            title='Test Resume',
            template='professional'
        )

    def test_resume_list_view(self):
        response = self.client.get(reverse('resume:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Resume')

    def test_resume_create_view(self):
        response = self.client.post(reverse('resume:create'), {
            'title': 'New Dev Resume',
            'template': 'modern'
        })
        self.assertEqual(response.status_code, 302) # Redirects to builder
        self.assertEqual(Resume.objects.count(), 2)
        
    def test_resume_builder_view(self):
        response = self.client.get(reverse('resume:builder', args=[self.resume.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Live Preview')

    def test_add_education_api(self):
        response = self.client.post(
            reverse('resume:api_add_section', args=[self.resume.id, 'education']),
            {
                'college': 'Test University',
                'degree': 'B.Sc',
                'branch': 'CS',
                'start_year': 2020,
                'end_year': 2024,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)
        self.assertEqual(Education.objects.filter(resume=self.resume).count(), 1)
        
    def test_delete_education_api(self):
        edu = Education.objects.create(
            resume=self.resume, college='Test', degree='B.Sc', branch='CS', start_year=2020, end_year=2024
        )
        response = self.client.post(
            reverse('resume:api_delete_section', args=[self.resume.id, 'education', edu.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)
        self.assertEqual(Education.objects.filter(resume=self.resume).count(), 0)

    def test_download_pdf(self):
        response = self.client.get(reverse('resume:download', args=[self.resume.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
    def test_security_other_user_resume(self):
        # Create a second user and resume
        other_user = User.objects.create_user(username='hacker', password='123')
        other_resume = Resume.objects.create(user=other_user, title='Hacker Resume')
        
        # Current logged in user tries to view it
        response = self.client.get(reverse('resume:builder', args=[other_resume.id]))
        # Should be 404 because get_object_or_404 uses user=request.user
        self.assertEqual(response.status_code, 404)

    def test_import_profile_autofill_api(self):
        from apps.profiles.models import StudentProfile
        # Create StudentProfile
        StudentProfile.objects.create(
            user=self.user,
            college='Autofill Tech University',
            degree='B.Tech',
            branch='AI & ML',
            graduation_year=2027,
            cgpa=9.5,
            skills='Python, Django, SQL'
        )
        
        response = self.client.post(
            reverse('resume:api_import_profile', args=[self.resume.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['success'], True)
        self.assertEqual(self.resume.educations.count(), 1)
        self.assertEqual(self.resume.skills.count(), 3)
        self.assertEqual(self.resume.educations.first().college, 'Autofill Tech University')

    def test_download_pdf_all_templates(self):
        for tpl in ['professional', 'modern', 'minimal']:
            self.resume.template = tpl
            self.resume.save()
            response = self.client.get(reverse('resume:download', args=[self.resume.id]))
            self.assertEqual(response.status_code, 200, f"Failed for template {tpl}")
            self.assertEqual(response['Content-Type'], 'application/pdf', f"Not a PDF for template {tpl}")

    def test_resume_preview_all_templates(self):
        for tpl in ['professional', 'modern', 'minimal']:
            self.resume.template = tpl
            self.resume.save()
            response = self.client.get(reverse('resume:preview', args=[self.resume.id]))
            self.assertEqual(response.status_code, 200, f"Preview failed for template {tpl}")

    def test_resume_hub_context_and_empty_states(self):
        # With 1 resume
        response = self.client.get(reverse('resume:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['default_resume'], self.resume)
        self.assertContains(response, 'Resume Hub')
        self.assertContains(response, 'ATS Scanner')
        
        # Delete all resumes to test empty state
        self.resume.delete()
        response_empty = self.client.get(reverse('resume:list'))
        self.assertEqual(response_empty.status_code, 200)
        self.assertIsNone(response_empty.context['default_resume'])
        self.assertContains(response_empty, 'No Resumes Created Yet')

    def test_resume_hub_sidebar_active_state(self):
        response = self.client.get(reverse('resume:list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Ensure Resume link is active
        self.assertIn('dash-nav-link active', content)
        # Check that the active link is specifically the Resume link
        self.assertTrue(
            '/resume/' in content and 'active' in content,
            "Resume link must be marked active on /resume/"
        )

    def test_resume_delete_view(self):
        response = self.client.post(reverse('resume:delete', args=[self.resume.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Resume.objects.filter(id=self.resume.id).count(), 0)

    def test_resume_update_settings_api(self):
        response = self.client.post(
            reverse('resume:api_update_settings', args=[self.resume.id]),
            {
                'title': 'Renamed Senior Engineer Resume',
                'template': 'minimal'
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.resume.refresh_from_db()
        self.assertEqual(self.resume.title, 'Renamed Senior Engineer Resume')
        self.assertEqual(self.resume.template, 'minimal')

