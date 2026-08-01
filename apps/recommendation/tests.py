from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.profiles.models import StudentProfile
from apps.resume.models import Resume, Education, Project, Skill
from apps.roadmaps.models import CareerPath, Milestone, Topic
from .models import CareerAnalysis
from .services import calculate_initial_readiness_score, build_fallback_analysis, generate_career_recommendation

User = get_user_model()

class RecommendationTests(TestCase):
    def setUp(self):
        # 1. Create User
        self.user = User.objects.create_user(
            username='careerstudent',
            email='student@careercatalyst.com',
            password='password123',
            first_name='Career',
            last_name='Student'
        )
        self.client.login(username='careerstudent', password='password123')
        
        # 2. Create StudentProfile
        self.profile = StudentProfile.objects.create(
            user=self.user,
            college='Tech Institute of technology',
            degree='B.Tech',
            branch='Computer Science',
            cgpa=9.20,
            career_goal='Software Engineer',
            skills='Python, Django, Git, SQL'
        )
        
        # 3. Create CareerPath, Milestones and Topics in database
        self.path = CareerPath.objects.create(
            name="Software Engineer",
            slug="software-engineer",
            description="Software Engineer Learning Path",
            difficulty="Intermediate"
        )
        self.ms = Milestone.objects.create(
            career_path=self.path,
            week_number=1,
            title="Programming Basics",
            level="Beginner",
            order=0
        )
        self.topic1 = Topic.objects.create(
            milestone=self.ms,
            title="Python",
            resource_url="http://python.org",
            resource_type="Documentation"
        )
        self.topic2 = Topic.objects.create(
            milestone=self.ms,
            title="Docker",
            resource_url="http://docker.com",
            resource_type="Course"
        )

    def test_calculate_initial_readiness_score(self):
        # CGPA 9.2 (15) + 4 skills (8) = 23
        score = calculate_initial_readiness_score(self.user, self.profile)
        self.assertEqual(score, 23)
        
        # Create a resume and add project/certification/experience to increase score
        resume = Resume.objects.create(user=self.user, title='My Resume', is_default=True)
        Project.objects.create(resume=resume, title='AI Project', description='AI description')
        Skill.objects.create(resume=resume, name='Python')
        
        # CGPA 9.2 (15) + 4 skills (8) + 1 project (5) = 28
        score = calculate_initial_readiness_score(self.user, self.profile)
        self.assertEqual(score, 28)

    def test_build_fallback_analysis(self):
        # Run local fallback parser
        data = build_fallback_analysis(self.user, self.profile, 28, "Software Engineer")
        
        self.assertEqual(data["recommended_career"], "Software Engineer")
        # Python is in student skills (profile), Docker is NOT. So Docker should be in missing_skills!
        self.assertIn("Docker", data["missing_skills"])
        self.assertNotIn("Python", data["missing_skills"])
        self.assertEqual(len(data["roadmap_json"]), 1)
        self.assertEqual(data["roadmap_json"][0]["title"], "Programming Basics")

    def test_generate_career_recommendation(self):
        # Run recommendation generation (saves to database)
        analysis = generate_career_recommendation(self.user, "Software Engineer")
        
        self.assertIsNotNone(analysis.pk)
        self.assertEqual(analysis.recommended_career, "Software Engineer")
        self.assertEqual(CareerAnalysis.objects.count(), 1)
        self.assertIn("Docker", analysis.missing_skills)

    def test_views_dashboard_navigation(self):
        # Access dashboard with no analysis yet (should render landing intro)
        response = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Run Career Analysis")
        
        # Trigger analyze POST
        response = self.client.post(reverse('recommendation:analyze'))
        self.assertEqual(response.status_code, 302) # Redirects back to dashboard
        
        # Access dashboard again (should render recommendations data)
        response = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Career Recommendations")
        self.assertContains(response, "Software Engineer")
        self.assertContains(response, "Docker")
