from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.profiles.models import StudentProfile
from apps.resume.models import Resume, Education, Project, Skill
from apps.roadmaps.models import CareerPath, Milestone, Topic
from .models import CareerAnalysis
from .services import evaluate_student_against_path, generate_career_recommendation

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

    def test_evaluate_readiness_score_with_resume_projects(self):
        # 1. Base test: CGPA 9.2 (15) + 50% skill match (20) = 35%
        data = evaluate_student_against_path(self.user, self.profile, self.path, False, None, None)
        self.assertEqual(data["career_readiness_score"], 35)
        
        # 2. Add resume with a project (1 project = +10 pts) -> 45%
        resume = Resume.objects.create(user=self.user, title='My Resume', is_default=True)
        Project.objects.create(resume=resume, title='AI Project', description='AI description')
        Skill.objects.create(resume=resume, name='Python')
        
        data_with_resume = evaluate_student_against_path(self.user, self.profile, self.path, True, None, resume)
        self.assertEqual(data_with_resume["career_readiness_score"], 45)

    def test_evaluate_student_against_path_matching_role(self):
        # Student has Python, so Python matches (1/2 topics = 50% match)
        data = evaluate_student_against_path(
            user=self.user,
            profile=self.profile,
            career_path=self.path,
            has_resume=False,
            latest_resume_analysis=None,
            default_resume=None
        )
        
        self.assertEqual(data["recommended_career"], "Software Engineer")
        self.assertIn("Docker", data["missing_skills"])
        self.assertFalse(data["has_resume"])
        self.assertIsNone(data["ats_resume_score"])
        # CGPA 9.2 (15) + 50% skill match (20) = 35%
        self.assertEqual(data["career_readiness_score"], 35)

    def test_evaluate_student_against_unmatched_role(self):
        # Create a Product Manager path with PM topics
        pm_path = CareerPath.objects.create(name="Product Manager", slug="product-manager", description="PM path")
        pm_ms = Milestone.objects.create(career_path=pm_path, week_number=1, title="User Research", level="Beginner")
        Topic.objects.create(milestone=pm_ms, title="User Interviews", resource_type="Article")
        Topic.objects.create(milestone=pm_ms, title="Wireframing (Figma)", resource_type="Article")
        
        # Student has Python/Django, 0 PM skills
        data = evaluate_student_against_path(
            user=self.user,
            profile=self.profile,
            career_path=pm_path,
            has_resume=False,
            latest_resume_analysis=None,
            default_resume=None
        )
        
        self.assertEqual(data["recommended_career"], "Product Manager")
        self.assertIn("User Interviews", data["missing_skills"])
        self.assertIn("Wireframing (Figma)", data["missing_skills"])
        # 0 PM skills matched -> Skill score is 0. Only academic score 15.
        self.assertEqual(data["career_readiness_score"], 15)
        self.assertEqual(data["internship_readiness"], "Need Preparation")
        self.assertEqual(data["placement_readiness"], "Need Preparation")

    def test_generate_career_recommendation(self):
        # Run recommendation generation without resume (saves to database)
        analysis = generate_career_recommendation(self.user, "Software Engineer")
        
        self.assertIsNotNone(analysis.pk)
        self.assertEqual(analysis.recommended_career, "Software Engineer")
        self.assertEqual(CareerAnalysis.objects.count(), 1)
        self.assertIn("Docker", analysis.missing_skills)
        self.assertFalse(analysis.has_resume)
        self.assertIsNone(analysis.ats_resume_score)

    def test_views_dashboard_navigation(self):
        # Access dashboard with no analysis yet (should render landing intro)
        response = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Run Career Analysis")
        
        # Trigger analyze POST with company_tier
        response = self.client.post(reverse('recommendation:analyze'), {
            'target_career': str(self.path.pk),
            'company_tier': 'product'
        })
        self.assertEqual(response.status_code, 302) # Redirects back to dashboard
        
        # Access dashboard again (should render recommendations data, tier badge and No Resume Uploaded card)
        response = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Target Career Pathway")
        self.assertContains(response, "Software Engineer")
        self.assertContains(response, "Docker")
        self.assertContains(response, "Product & Startup Calibrated")
        self.assertContains(response, "No Resume Uploaded")

    def test_company_tier_calibration_scoring(self):
        # Evaluate product vs service vs general
        data_prod = evaluate_student_against_path(self.user, self.profile, self.path, False, None, None, company_tier='product')
        data_serv = evaluate_student_against_path(self.user, self.profile, self.path, False, None, None, company_tier='service')
        
        # Both calculate custom weights based on their criteria
        self.assertEqual(data_prod["target_company_tier"], "product")
        self.assertEqual(data_serv["target_company_tier"], "service")
        self.assertTrue(any("Product Tier" in w or "Stack" in w for w in data_prod["weaknesses"]))
        self.assertTrue(any("Core CS" in w or "Academic" in w for w in data_serv["weaknesses"]))

    def test_one_click_roadmap_enroll_and_sync(self):
        from .services import enroll_and_sync_roadmap
        analysis = generate_career_recommendation(self.user, "Software Engineer", company_tier='general')
        result = enroll_and_sync_roadmap(self.user, analysis)
        self.assertIsNotNone(result)
        self.assertEqual(result["career_path"], self.path)
        self.assertIsNotNone(result["user_roadmap"])
        self.assertGreaterEqual(result["progress_percentage"], 0)

    def test_workspace_shell_and_active_sidebar(self):
        response = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(response.status_code, 200)
        # Verify authenticated workspace shell is present
        self.assertContains(response, 'class="dash-shell"')
        self.assertContains(response, 'id="dashboardSidebar"')
        # Verify public navbar and footer are overridden
        self.assertNotContains(response, 'class="navbar navbar-expand-lg')
        self.assertNotContains(response, 'class="landing-footer"')
        # Verify Career Guidance link has active class
        self.assertContains(response, 'href="/recommendation/" class="dash-nav-link active"')

    def test_evaluation_pillars_and_no_fake_checklist(self):
        generate_career_recommendation(self.user, "Software Engineer", company_tier='product')
        response = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # Verify 4 evaluation pillars are present in context
        pillars = response.context.get('pillars')
        self.assertIsNotNone(pillars)
        self.assertEqual(len(pillars), 4)
        pillar_names = [p['name'] for p in pillars]
        self.assertIn('Core Technical Skills', pillar_names)
        self.assertIn('Applied Projects', pillar_names)
        self.assertIn('Academic Benchmark', pillar_names)
        self.assertIn('Experience & Certs', pillar_names)

        # Verify Hiring Benchmark Diagnostics section in HTML
        self.assertContains(response, "Hiring Benchmark Diagnostics")
        
        # Verify NO fake localStorage milestone checklist in template
        self.assertNotContains(response, "milestone-check")
        self.assertNotContains(response, "saveProgress")
        self.assertNotContains(response, "milestone-")

    def test_radar_labels_ascii_safety(self):
        # Create a milestone with a long name (>20 chars)
        Milestone.objects.create(
            career_path=self.path,
            week_number=2,
            title="Advanced Microservices Architecture and Scalability",
            level="Advanced",
            order=1
        )
        analysis = generate_career_recommendation(self.user, "Software Engineer", company_tier='general')
        radar_json = analysis.radar_chart_json
        self.assertTrue(len(radar_json) > 0)
        for item in radar_json:
            name = item.get('name', '')
            # Must NOT contain unicode ellipsis
            self.assertNotIn('\u2026', name)
            # If truncated, should use '...'
            if '...' in name:
                self.assertTrue(name.endswith('...'))

    def test_sidebar_active_state_mutually_exclusive(self):
        # 1. On /recommendation/
        res_rec = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(res_rec.status_code, 200)
        self.assertContains(res_rec, 'href="/recommendation/" class="dash-nav-link active"')
        self.assertNotContains(res_rec, 'href="/dashboard/" class="dash-nav-link active"')
        self.assertNotContains(res_rec, 'href="/roadmaps/" class="dash-nav-link active"')

        # 2. On /dashboard/
        res_dash = self.client.get(reverse('dashboard'))
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, 'href="/dashboard/" class="dash-nav-link active"')
        self.assertNotContains(res_dash, 'href="/recommendation/" class="dash-nav-link active"')
        self.assertNotContains(res_dash, 'href="/roadmaps/" class="dash-nav-link active"')

        # 3. On /roadmaps/
        res_road = self.client.get(reverse('roadmaps:path_list'))
        self.assertEqual(res_road.status_code, 200)
        self.assertContains(res_road, 'href="/roadmaps/" class="dash-nav-link active"')
        self.assertNotContains(res_road, 'href="/dashboard/" class="dash-nav-link active"')
        self.assertNotContains(res_road, 'href="/recommendation/" class="dash-nav-link active"')

    def test_completed_roadmap_state_renders_review_cta(self):
        from apps.roadmaps.models import UserRoadmap, TopicProgress
        analysis = generate_career_recommendation(self.user, "Software Engineer", company_tier='general')
        user_roadmap = UserRoadmap.objects.create(user=self.user, career_path=self.path, is_active=True)
        # Mark all topics in path as completed
        TopicProgress.objects.create(user_roadmap=user_roadmap, topic=self.topic1, is_completed=True)
        TopicProgress.objects.create(user_roadmap=user_roadmap, topic=self.topic2, is_completed=True)
        self.assertEqual(user_roadmap.progress_percentage(), 100)

        response = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get('is_path_completed'))
        self.assertIsNone(response.context.get('next_active_week'))

        # Must contain completed CTAs
        self.assertContains(response, "Review Roadmap")
        self.assertContains(response, "Open Interview Prep")
        self.assertContains(response, "Curriculum Completed")
        self.assertContains(response, "Track is 100% Complete")

        # Must NOT contain contradictory in-progress text or Week 1
        self.assertNotContains(response, "Continue Learning")
        self.assertNotContains(response, "Resume at Week 1")

    def test_incomplete_roadmap_advances_to_first_incomplete_week(self):
        from apps.roadmaps.models import UserRoadmap, TopicProgress
        # Create Week 2 milestone and topics
        ms2 = Milestone.objects.create(
            career_path=self.path,
            week_number=2,
            title="Backend Frameworks",
            level="Intermediate",
            order=1
        )
        Topic.objects.create(milestone=ms2, title="Django", resource_type="Documentation")
        
        generate_career_recommendation(self.user, "Software Engineer", company_tier='general')
        user_roadmap = UserRoadmap.objects.create(user=self.user, career_path=self.path, is_active=True)
        
        # Complete all topics in Week 1 (topic1 and topic2)
        TopicProgress.objects.create(user_roadmap=user_roadmap, topic=self.topic1, is_completed=True)
        TopicProgress.objects.create(user_roadmap=user_roadmap, topic=self.topic2, is_completed=True)
        
        response = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get('is_path_completed'))
        self.assertEqual(response.context.get('next_active_week'), 2)
        
        # Should show Week 2, not default to Week 1
        self.assertContains(response, "Continue Learning (Week 2)")
        self.assertContains(response, "Resume at <strong>Week 2</strong>")
        self.assertNotContains(response, "Continue Learning (Week 1)")

    def test_role_skill_match_and_alignment_labels(self):
        generate_career_recommendation(self.user, "Software Engineer", company_tier='general')
        response = self.client.get(reverse('recommendation:dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # Context must contain role_skill_match_pct
        self.assertIn('role_skill_match_pct', response.context)
        self.assertContains(response, "Role Skill Match:")
        self.assertContains(response, "Role Alignment:")


class CareerRecalibrationDynamicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='recalibrate_user',
            email='recalibrate@example.com',
            password='password123'
        )
        self.client.force_login(self.user)

        # Profile with initial manual skills: Python, Git, SQL
        self.profile = StudentProfile.objects.create(
            user=self.user,
            college='Engineering College',
            degree='B.E.',
            branch='Computer Science',
            cgpa=8.5,
            career_goal='Software Engineer',
            skills='Python, Git, SQL'
        )

        # Create CareerPath: Software Engineer
        self.path = CareerPath.objects.create(
            name='Software Engineer',
            slug='software-engineer',
            description='Software Engineer Learning Path',
            difficulty='Intermediate'
        )
        self.ms1 = Milestone.objects.create(
            career_path=self.path,
            week_number=1,
            title='Core Languages',
            level='Beginner',
            order=1
        )
        self.ms2 = Milestone.objects.create(
            career_path=self.path,
            week_number=2,
            title='Web Frameworks & Containers',
            level='Intermediate',
            order=2
        )

        self.t_python = Topic.objects.create(
            milestone=self.ms1,
            title='Python Fundamentals',
            skills_taught='Python, Object-Oriented Programming'
        )
        self.t_django = Topic.objects.create(
            milestone=self.ms2,
            title='Django Web Framework',
            skills_taught='Django, Python Web Development'
        )
        self.t_docker = Topic.objects.create(
            milestone=self.ms2,
            title='Docker & Containers',
            skills_taught='Docker, Containerization'
        )

        from apps.roadmaps.models import UserRoadmap
        self.user_roadmap = UserRoadmap.objects.create(
            user=self.user,
            career_path=self.path
        )

    def test_extract_student_skills_set_aggregates_all_four_sources(self):
        from .services import extract_student_skills_set
        from apps.roadmaps.models import TopicProgress

        # 1. Profile has: Python, Git, SQL
        # 2. Add Resume skill: Redis
        resume = Resume.objects.create(user=self.user, title='Default Resume', is_default=True)
        Skill.objects.create(resume=resume, name='Redis')

        # 3. Add Resume project technology: PostgreSQL
        Project.objects.create(
            resume=resume,
            title='E-commerce Backend',
            description='Built scalable microservice',
            technologies_used='PostgreSQL, Celery'
        )

        # 4. Complete roadmap topic: Docker & Containers (teaches Docker, Containerization)
        TopicProgress.objects.create(
            user_roadmap=self.user_roadmap,
            topic=self.t_docker,
            is_completed=True
        )

        raw_skills, tokens = extract_student_skills_set(self.user, self.profile, resume, None)

        # Verify source 1 (Profile)
        self.assertIn('Python', raw_skills)
        self.assertIn('Git', raw_skills)
        self.assertIn('SQL', raw_skills)

        # Verify source 2 (Resume Skill)
        self.assertIn('Redis', raw_skills)

        # Verify source 3 (Resume Project tech)
        self.assertIn('PostgreSQL', raw_skills)
        self.assertIn('Celery', raw_skills)

        # Verify source 4 (Completed Roadmap topic)
        self.assertIn('Docker', raw_skills)
        self.assertIn('Containerization', raw_skills)

    def test_manually_entered_profile_skills_remain_independent_and_unmutated(self):
        from apps.roadmaps.models import TopicProgress
        initial_profile_skills = self.profile.skills

        # Complete Django topic
        TopicProgress.objects.create(
            user_roadmap=self.user_roadmap,
            topic=self.t_django,
            is_completed=True
        )

        # Refresh profile from db
        self.profile.refresh_from_db()
        # StudentProfile.skills must NOT be mutated
        self.assertEqual(self.profile.skills, initial_profile_skills)
        self.assertNotIn('Django', self.profile.skills)

    def test_manual_skill_persists_when_roadmap_topic_unchecked(self):
        from .services import extract_student_skills_set
        from apps.roadmaps.models import TopicProgress

        # User has Python in self.profile.skills ('Python, Git, SQL')
        # Complete Python topic
        prog, _ = TopicProgress.objects.get_or_create(
            user_roadmap=self.user_roadmap,
            topic=self.t_python,
            defaults={'is_completed': True}
        )
        prog.is_completed = True
        prog.save()

        # Uncomplete Python topic
        prog.is_completed = False
        prog.save()

        raw_skills, _ = extract_student_skills_set(self.user, self.profile, None, None)
        # Python MUST still be present because it is in profile.skills
        self.assertIn('Python', raw_skills)

    def test_recalibration_score_increases_dynamically_after_topic_completion(self):
        from apps.roadmaps.models import TopicProgress

        # 1. Initial diagnostic before completing roadmap topics
        initial_analysis = generate_career_recommendation(self.user, 'Software Engineer', 'general')
        initial_score = initial_analysis.career_readiness_score
        initial_missing = list(initial_analysis.missing_skills)

        # Django Web Framework and Docker & Containers must be missing
        self.assertIn(self.t_django.title, initial_missing)
        self.assertIn(self.t_docker.title, initial_missing)

        # 2. User completes Django Web Framework topic
        TopicProgress.objects.create(
            user_roadmap=self.user_roadmap,
            topic=self.t_django,
            is_completed=True
        )

        # 3. User recalibrates (triggers POST /recommendation/analyze/)
        response = self.client.post(reverse('recommendation:analyze'), {
            'target_career': str(self.path.pk),
            'company_tier': 'general'
        })
        self.assertEqual(response.status_code, 302)

        # 4. Fetch the latest analysis created by recalibration
        latest_analysis = CareerAnalysis.objects.filter(user=self.user).order_by('-created_at').first()
        self.assertNotEqual(latest_analysis.pk, initial_analysis.pk)

        # The new readiness score must be higher than initial score
        self.assertGreater(latest_analysis.career_readiness_score, initial_score)

        # Django Web Framework must NO LONGER be in missing_skills
        self.assertNotIn(self.t_django.title, latest_analysis.missing_skills)
        self.assertTrue(any(self.t_django.title in s for s in latest_analysis.strengths))

        # Docker remains incomplete, so it should still be in missing_skills
        self.assertIn(self.t_docker.title, latest_analysis.missing_skills)

    def test_radar_chart_output_updates_through_recommendation_pipeline(self):
        from apps.roadmaps.models import TopicProgress

        # Initial analysis
        analysis1 = generate_career_recommendation(self.user, 'Software Engineer', 'general')
        radar1 = analysis1.radar_chart_json

        # Complete both topics in Week 2
        TopicProgress.objects.create(user_roadmap=self.user_roadmap, topic=self.t_django, is_completed=True)
        TopicProgress.objects.create(user_roadmap=self.user_roadmap, topic=self.t_docker, is_completed=True)

        # Recalibrate
        analysis2 = generate_career_recommendation(self.user, 'Software Engineer', 'general')
        radar2 = analysis2.radar_chart_json

        # Radar score for Week 2 milestone should be higher in analysis2 than analysis1
        ms2_score1 = next((item['user_score'] for item in radar1 if 'Frameworks' in item['name']), 0)
        ms2_score2 = next((item['user_score'] for item in radar2 if 'Frameworks' in item['name']), 0)
        self.assertGreater(ms2_score2, ms2_score1)



