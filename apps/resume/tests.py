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
