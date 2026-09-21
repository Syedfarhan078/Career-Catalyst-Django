from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from apps.resume.models import Resume, Skill, Project, Experience, Education
from apps.profiles.models import StudentProfile
from .models import ResumeAnalysis, MissingSkill, ImprovementSuggestion
from .services import analyze_resume_data
from .nlp_engine import extract_skills_from_text, compute_tfidf_similarity
from .xyz_evaluator import evaluate_bullet_point, evaluate_achievement_strength
from .pii_sanitizer import sanitize_resume_text
from .ai_service import enhance_with_ai
from .views import resume_to_text

User = get_user_model()

class HybridATSTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='hybrid_user',
            email='user@example.com',
            password='password123',
            first_name='Syed',
            last_name='Ahmed'
        )
        self.client.login(username='hybrid_user', password='password123')
        
        self.resume = Resume.objects.create(
            user=self.user,
            title='Software Engineer Resume',
            template='professional'
        )
        Skill.objects.create(resume=self.resume, name='Python')
        Skill.objects.create(resume=self.resume, name='Django')
        Skill.objects.create(resume=self.resume, name='PostgreSQL')
        Skill.objects.create(resume=self.resume, name='Docker')
        Project.objects.create(
            resume=self.resume,
            title='Career Platform',
            description='Engineered a Django SaaS application with PostgreSQL, reducing latency by 40% for 1,000+ students.',
            technologies_used='Python, Django, PostgreSQL'
        )

    def test_nlp_skill_extraction_and_alias(self):
        sample = "Proficient in React.js, Python, PostgreSQL, k8s, Tailwind, and Django REST API."
        res = extract_skills_from_text(sample)
        skills = res["skills"]
        
        # Test alias resolution
        self.assertIn("react", skills)
        self.assertIn("python", skills)
        self.assertIn("postgresql", skills)
        self.assertIn("kubernetes", skills)
        self.assertIn("django", skills)

    def test_tfidf_cosine_similarity(self):
        doc1 = "Python developer experienced in Django, PostgreSQL, Docker, and REST APIs."
        doc2 = "Seeking a Backend Engineer with Python, Django, REST APIs, and Docker experience."
        score, kws = compute_tfidf_similarity(doc1, doc2)
        
        self.assertGreater(score, 50)
        self.assertIn("python", [k.lower() for k in kws])

    def test_xyz_bullet_evaluator(self):
        # Strong bullet with action verb + metric + tech
        strong_bullet = "Architected a scalable Django REST API with Redis caching, reducing server response latency by 45% for 10,000+ daily users."
        res1 = evaluate_bullet_point(strong_bullet)
        self.assertEqual(res1["verb_strength"], "strong")
        self.assertTrue(res1["has_metric"])
        self.assertTrue(res1["has_tech"])
        self.assertGreaterEqual(res1["score"], 80)

        # Weak bullet
        weak_bullet = "Worked on website bugs and did some python coding."
        res2 = evaluate_bullet_point(weak_bullet)
        self.assertEqual(res2["verb_strength"], "weak")
        self.assertFalse(res2["has_metric"])
        self.assertLess(res2["score"], 50)

    def test_pii_sanitizer(self):
        raw = (
            "Syed Farhan Ahmed\n"
            "Email: farhan@example.com | Phone: +91 98765 43210\n"
            "LinkedIn: https://linkedin.com/in/farhan | GitHub: https://github.com/farhan\n"
            "Stanford University - B.Sc Computer Science\n"
            "Built a distributed database system."
        )
        res = sanitize_resume_text(raw)
        sanitized = res["sanitized_text"]
        
        self.assertNotIn("farhan@example.com", sanitized)
        self.assertNotIn("+91 98765 43210", sanitized)
        self.assertNotIn("https://linkedin.com/in/farhan", sanitized)
        self.assertIn("[EMAIL_REDACTED]", sanitized)
        self.assertIn("[PHONE_REDACTED]", sanitized)
        self.assertIn("[LINKEDIN_URL]", sanitized)

    def test_complete_services_5_metrics(self):
        mock_text = """
        John Doe
        Email: candidate@example.com
        Phone: +1 555 123 4567
        LinkedIn: https://linkedin.com/in/candidate
        GitHub: https://github.com/candidate

        EDUCATION
        B.S. in Computer Science - University of Technology

        EXPERIENCE
        • Engineered high-throughput Django microservices handling 50,000+ daily requests with 99.9% uptime.
        • Optimized SQL database queries in PostgreSQL, reducing query latency by 35%.

        PROJECTS
        • Developed full-stack SaaS platform using React, Python, Docker, and AWS EC2.

        SKILLS
        Python, Django, PostgreSQL, Docker, AWS, React, Git, REST API, SQL
        """
        analysis = analyze_resume_data(
            text=mock_text,
            target_role="Backend Developer",
            user=self.user,
            resume=self.resume,
            job_description="Seeking a Backend Developer skilled in Python, Django, PostgreSQL, Redis, Docker, and Microservices."
        )
        
        self.assertEqual(ResumeAnalysis.objects.count(), 1)
        self.assertGreater(analysis.jd_match_score, 40)
        self.assertGreater(analysis.skill_coverage_score, 50)
        # Mock resume contains 6 out of 13 role/benchmark keywords = 46.15% (rounds to 46)
        self.assertGreater(analysis.keyword_coverage_score, 40)
        self.assertGreater(analysis.completeness_score, 80)
        self.assertGreater(analysis.achievement_score, 50)
        self.assertGreater(analysis.overall_score, 60)

    @patch('apps.ai_resume.ai_service.get_groq_api_key', return_value='')
    @patch('apps.ai_resume.ai_service.get_gemini_api_key', return_value='')
    def test_ai_graceful_offline_fallback(self, mock_gemini, mock_groq):
        # When no API key is provided, returns offline status without crashing
        res = enhance_with_ai("Anonymized text", "Software Engineer")
        self.assertFalse(res["ai_available"])
        self.assertEqual(res["status"], "offline_mode")

    def test_views_flow(self):
        # 1. History view
        resp = self.client.get(reverse('ai_resume:history'))
        self.assertEqual(resp.status_code, 200)

        # 2. Analyze view (GET)
        resp = self.client.get(reverse('ai_resume:analyze'))
        self.assertEqual(resp.status_code, 200)

        # 3. Analyze view (POST with internal resume)
        resp = self.client.post(reverse('ai_resume:analyze'), {
            'target_role': 'Software Engineer',
            'job_description': 'Python and Django developer',
            'resume': self.resume.pk
        })
        self.assertEqual(resp.status_code, 302)
        
        analysis = ResumeAnalysis.objects.first()
        self.assertIsNotNone(analysis)
        
        # 4. Detail view
        detail_resp = self.client.get(reverse('ai_resume:detail', args=[analysis.pk]))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, 'ATS Resume Report')
        self.assertContains(detail_resp, 'ATS Score')

    def test_resume_to_text_studentprofile_contact_regression(self):
        # StudentProfile fields must be included in text serialization
        StudentProfile.objects.create(
            user=self.user,
            college="University of Engineering",
            degree="B.Tech",
            branch="CSE",
            phone_number="+1-555-987-6543",
            linkedin="https://linkedin.com/in/syedahmed",
            github="https://github.com/syedahmed"
        )
        text = resume_to_text(self.resume)
        self.assertIn("+1-555-987-6543", text)
        self.assertIn("https://linkedin.com/in/syedahmed", text)
        self.assertIn("https://github.com/syedahmed", text)

    def test_history_select_related_efficiency(self):
        # Create analyses to test query efficiency
        ResumeAnalysis.objects.create(
            user=self.user,
            resume=self.resume,
            target_role="Software Engineer",
            overall_score=75,
            ats_score=75
        )
        response = self.client.get(reverse('ai_resume:history'))
        self.assertEqual(response.status_code, 200)
        # Ensure resume is select_related in queryset
        qs = response.context['analyses']
        self.assertIn('resume', qs.query.select_related)
