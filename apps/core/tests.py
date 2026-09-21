from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.profiles.models import StudentProfile
from apps.ai_resume.models import ResumeAnalysis
from apps.roadmaps.models import CareerPath, Milestone, Topic, UserRoadmap, TopicProgress

User = get_user_model()


class DashboardRefinementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password123'
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            career_goal='Software Engineer',
            skills='Python, Django, PostgreSQL, Docker',
            college='Test University'
        )
        self.client = Client(HTTP_HOST='127.0.0.1')
        self.client.force_login(self.user)

    def test_dashboard_renders_successfully(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_ats_report_recommendation_links_to_analysis_detail(self):
        analysis = ResumeAnalysis.objects.create(
            user=self.user,
            target_role='Software Engineer',
            ats_score=71,
            overall_score=71,
            skill_coverage_score=80,
            keyword_coverage_score=70,
            achievement_score=65,
            completeness_score=70
        )
        
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        
        recommendations = response.context['recommendations']
        # Exactly 3 recommendations: Resume, Interview, Guidance
        self.assertEqual(len(recommendations), 3)
        self.assertEqual([r['badge'] for r in recommendations], ['Resume', 'Interview', 'Guidance'])

        resume_rec = recommendations[0]
        expected_url = reverse('ai_resume:detail', kwargs={'pk': analysis.pk})
        self.assertEqual(resume_rec['action_url'], expected_url)
        self.assertEqual(resume_rec['action_text'], 'View ATS report')
        
        detail_response = self.client.get(resume_rec['action_url'])
        self.assertEqual(detail_response.status_code, 200)

    def test_career_journey_statuses_are_truthful(self):
        # User has 4 skills, profile not 100%, ATS 71%
        analysis = ResumeAnalysis.objects.create(
            user=self.user,
            target_role='Software Engineer',
            ats_score=71,
            overall_score=71,
            skill_coverage_score=80,
            keyword_coverage_score=70,
            achievement_score=65,
            completeness_score=70
        )
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        
        stages = {s['id']: s for s in response.context['career_journey']}
        
        # Target role is complete because user has set it
        self.assertEqual(stages['role']['status'], 'complete')
        
        # Profile is not 100% -> MUST NOT be marked complete
        self.assertEqual(stages['profile']['status'], 'in-progress')
        
        # Skills exist (4 skills) -> MUST NOT be falsely marked complete (must be in-progress)
        self.assertEqual(stages['skills']['status'], 'in-progress')
        
        # Resume ATS is 71% (<85%) -> MUST NOT be marked complete (in-progress)
        self.assertEqual(stages['resume']['status'], 'in-progress')

        # Verify all stage links resolve with 200 or 302
        for stage in stages.values():
            res = self.client.get(stage['url'])
            self.assertIn(res.status_code, [200, 302], f"Stage '{stage['id']}' URL {stage['url']} returned {res.status_code}")

    def test_roadmap_completion_logic_and_cta(self):
        # Create a career path with 2 topics
        path = CareerPath.objects.create(name='Software Engineer', slug='software-engineer')
        milestone = Milestone.objects.create(career_path=path, title='Core Basics', week_number=1, order=1)
        topic1 = Topic.objects.create(milestone=milestone, title='Variables', order=1)
        topic2 = Topic.objects.create(milestone=milestone, title='Functions', order=2)
        
        user_roadmap = UserRoadmap.objects.create(user=self.user, career_path=path, is_active=True)
        prog1 = TopicProgress.objects.create(user_roadmap=user_roadmap, topic=topic1, is_completed=True)
        prog2 = TopicProgress.objects.create(user_roadmap=user_roadmap, topic=topic2, is_completed=False)
        
        # Case 1: In progress (1 of 2 completed)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_roadmap_completed'])
        self.assertContains(response, 'Continue roadmap')
        self.assertNotContains(response, 'Review roadmap')

        # Case 2: 100% Complete (both topics completed)
        prog2.is_completed = True
        prog2.save()
        
        response_completed = self.client.get(reverse('dashboard'))
        self.assertEqual(response_completed.status_code, 200)
        self.assertTrue(response_completed.context['is_roadmap_completed'])
        self.assertContains(response_completed, 'Review roadmap')
        self.assertContains(response_completed, 'Roadmap completed')
        self.assertContains(response_completed, "You've completed all 2 topics in this track.")

    def test_no_fake_percentages_in_next_step(self):
        # When user has completed roadmap or has no active topic progress
        response = self.client.get(reverse('dashboard'))
        next_step = response.context['next_step']
        # Progress must either be a real percentage (active topic) or None
        if next_step['state'] != 'topic_continue':
            self.assertIsNone(next_step['progress'], f"Fake progress found in state: {next_step['state']}")
