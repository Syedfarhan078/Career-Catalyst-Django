from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.resume.models import Resume
from .models import ResumeAnalysis, MissingSkill, ImprovementSuggestion
from .services import analyze_resume_data

User = get_user_model()

class ResumeAnalysisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='analyzer_user',
            email='user@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        self.client.login(username='analyzer_user', password='password123')
        
        # Create an internal resume
        self.resume = Resume.objects.create(
            user=self.user,
            title='Software Engineer Resume',
            template='professional'
        )

    def test_services_grading(self):
        # Resume text containing 3 sections (Education, Projects, Skills) and some keywords
        mock_text = """
        Test User
        Email: user@example.com
        Phone: +92 300 1234567
        LinkedIn: linkedin.com/in/testuser
        GitHub: github.com/testuser

        EDUCATION
        B.Sc Computer Science

        PROJECTS
        Built a python application using django and sql databases. Managed source control with git.

        SKILLS
        Python, Git, SQL, React, HTML, CSS, Docker, Django
        """
        analysis = analyze_resume_data(
            text=mock_text,
            target_role="Software Engineer",
            user=self.user,
            resume=self.resume
        )
        
        # Check that analysis is saved
        self.assertEqual(ResumeAnalysis.objects.count(), 1)
        self.assertEqual(analysis.target_role, "Software Engineer")
        
        # Ensure we have subscores calculated
        self.assertGreater(analysis.overall_score, 0)
        self.assertGreater(analysis.keyword_score, 0)
        self.assertGreater(analysis.skill_score, 0)
        
        # Missing skills and suggestions should be populated
        self.assertTrue(MissingSkill.objects.filter(analysis=analysis).exists())
        self.assertTrue(ImprovementSuggestion.objects.filter(analysis=analysis).exists())

    def test_analysis_history_view(self):
        # Create an analysis record
        ResumeAnalysis.objects.create(
            user=self.user,
            target_role='Software Engineer',
            overall_score=85
        )
        response = self.client.get(reverse('ai_resume:history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Software Engineer')
        self.assertContains(response, '85%')

    def test_detail_view_security(self):
        # Create a report for self.user
        analysis = ResumeAnalysis.objects.create(
            user=self.user,
            target_role='Data Scientist',
            overall_score=75
        )
        
        # Create a hacker user
        other_user = User.objects.create_user(username='hacker_user', password='password123')
        self.client.login(username='hacker_user', password='password123')
        
        # Accessing other user's report should give 404
        response = self.client.get(reverse('ai_resume:detail', args=[analysis.pk]))
        self.assertEqual(response.status_code, 404)

    def test_upload_invalid_file_extension(self):
        # Uploading a text file instead of PDF/DOCX
        bad_file = SimpleUploadedFile("resume.txt", b"Mock resume contents", content_type="text/plain")
        response = self.client.post(reverse('ai_resume:analyze'), {
            'target_role': 'Product Manager',
            'uploaded_file': bad_file
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('uploaded_file', form.errors)
        self.assertIn('Only PDF and DOCX files are supported.', form.errors['uploaded_file'])

    def test_upload_large_file(self):
        # File > 5MB
        huge_content = b"0" * (6 * 1024 * 1024) # 6MB
        large_file = SimpleUploadedFile("resume.pdf", huge_content, content_type="application/pdf")
        response = self.client.post(reverse('ai_resume:analyze'), {
            'target_role': 'ML Engineer',
            'uploaded_file': large_file
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('uploaded_file', form.errors)
        self.assertIn('The uploaded file size must not exceed 5MB.', form.errors['uploaded_file'])
