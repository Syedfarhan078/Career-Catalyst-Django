from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.management import call_command

from .models import CareerPath, Milestone, Topic, UserRoadmap, TopicProgress
from apps.profiles.models import StudentProfile

User = get_user_model()

class CareerRoadmapTests(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            username='student1',
            email='student1@example.com',
            password='password123'
        )
        self.client.force_login(self.user)

        # Create mock career path for manual model testing
        self.path = CareerPath.objects.create(
            name='Test Engineer',
            slug='test-engineer',
            description='Test description',
            icon='bi-bug',
            estimated_weeks=4,
            difficulty='Beginner'
        )
        self.milestone = Milestone.objects.create(
            career_path=self.path,
            week_number=1,
            title='Introduction to Testing',
            level='Beginner',
            order=1
        )
        self.topic1 = Topic.objects.create(
            milestone=self.milestone,
            title='Unit Testing Basics',
            description='Learn unit testing fundamentals',
            resource_type='Article',
            estimated_hours=2.0,
            order=1
        )
        self.topic2 = Topic.objects.create(
            milestone=self.milestone,
            title='Integration Testing Basics',
            description='Learn integration testing fundamentals',
            resource_type='Video',
            estimated_hours=3.0,
            order=2
        )

    def test_roadmap_seeding_command(self):
        # Delete test engineer so we can test clean seed
        CareerPath.objects.all().delete()
        
        # Call the seed command
        call_command('seed_roadmaps')
        
        # Verify seeding populated paths, milestones, and topics
        self.assertGreater(CareerPath.objects.count(), 0)
        self.assertGreater(Milestone.objects.count(), 0)
        self.assertGreater(Topic.objects.count(), 0)

    def test_path_list_view(self):
        response = self.client.get(reverse('roadmaps:path_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Engineer')

    def test_enrollment_workflow(self):
        # Verify no roadmap exists yet
        self.assertEqual(UserRoadmap.objects.filter(user=self.user).count(), 0)

        # Enroll in the path
        response = self.client.post(reverse('roadmaps:enroll', args=[self.path.slug]))
        self.assertEqual(response.status_code, 302)  # Redirects to detail view
        
        # Verify enrollment and progress items were generated
        user_roadmap = UserRoadmap.objects.get(user=self.user, career_path=self.path)
        self.assertIsNotNone(user_roadmap)
        self.assertEqual(user_roadmap.topic_progress.count(), 2)

    def test_topic_progress_toggle(self):
        # Enroll first
        self.client.post(reverse('roadmaps:enroll', args=[self.path.slug]))
        user_roadmap = UserRoadmap.objects.get(user=self.user, career_path=self.path)
        progress = TopicProgress.objects.get(user_roadmap=user_roadmap, topic=self.topic1)
        self.assertFalse(progress.is_completed)

        # Toggle completed status (POST request)
        response = self.client.post(reverse('roadmaps:toggle_topic', args=[self.topic1.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_completed'])
        self.assertEqual(data['progress_percentage'], 50) # 1 of 2 completed
        
        # Verify database record updated
        progress.refresh_from_db()
        self.assertTrue(progress.is_completed)

        # Toggle back to incomplete
        response = self.client.post(reverse('roadmaps:toggle_topic', args=[self.topic1.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['is_completed'])
        self.assertEqual(data['progress_percentage'], 0)


class RoadmapsRedesignTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='learner',
            email='learner@example.com',
            password='password123'
        )
        self.profile = StudentProfile.objects.create(
            user=self.user,
            career_goal='Backend Developer',
            college='Tech University'
        )
        self.client.force_login(self.user)

        # Create two CareerPaths
        self.path_backend = CareerPath.objects.create(
            name='Backend Developer',
            slug='backend-developer',
            description='Master backend services and APIs.',
            estimated_weeks=6,
            difficulty='Intermediate'
        )
        self.path_frontend = CareerPath.objects.create(
            name='Frontend Developer',
            slug='frontend-developer',
            description='Master modern web interfaces.',
            estimated_weeks=6,
            difficulty='Beginner'
        )

        # Add 2 milestones and topics to backend path
        self.ms1 = Milestone.objects.create(career_path=self.path_backend, week_number=1, title='Python OOP', order=1)
        self.ms2 = Milestone.objects.create(career_path=self.path_backend, week_number=2, title='Django APIs', order=2)

        self.t1_1 = Topic.objects.create(milestone=self.ms1, title='Classes & Objects', order=1, estimated_hours=2.0)
        self.t1_2 = Topic.objects.create(milestone=self.ms1, title='Inheritance', order=2, estimated_hours=2.0)
        self.t2_1 = Topic.objects.create(milestone=self.ms2, title='REST Principles', order=1, estimated_hours=3.0)

    def test_hub_empty_state_when_not_enrolled(self):
        response = self.client.get(reverse('roadmaps:path_list'))
        self.assertEqual(response.status_code, 200)
        # Uses workspace shell
        self.assertContains(response, 'dash-shell')
        self.assertContains(response, 'dash-sidebar')
        # Shows empty state
        self.assertContains(response, "You haven't started a roadmap yet")
        # Recommends target career
        self.assertContains(response, 'Backend Developer')

    def test_deterministic_active_roadmap_selection_with_multiple_enrollments(self):
        # Enroll in both Frontend (first) and Backend (second)
        # Even though Frontend was enrolled first, Backend matches user's career_goal
        enr_front = UserRoadmap.objects.create(user=self.user, career_path=self.path_frontend)
        enr_back = UserRoadmap.objects.create(user=self.user, career_path=self.path_backend)

        response = self.client.get(reverse('roadmaps:path_list'))
        self.assertEqual(response.status_code, 200)
        
        # Primary enrollment must be Backend Developer
        primary = response.context['primary_enrollment']
        self.assertIsNotNone(primary)
        self.assertEqual(primary.career_path.slug, 'backend-developer')
        
        # Frontend must be in secondary_enrollments
        secondary = response.context['secondary_enrollments']
        self.assertEqual(len(secondary), 1)
        self.assertEqual(secondary[0].career_path.slug, 'frontend-developer')

    def test_milestone_journey_and_continue_learning_anchor(self):
        enr_back = UserRoadmap.objects.create(user=self.user, career_path=self.path_backend)
        # Populate topic progress
        TopicProgress.objects.create(user_roadmap=enr_back, topic=self.t1_1, is_completed=True)
        TopicProgress.objects.create(user_roadmap=enr_back, topic=self.t1_2, is_completed=False)
        TopicProgress.objects.create(user_roadmap=enr_back, topic=self.t2_1, is_completed=False)

        response = self.client.get(reverse('roadmaps:path_list'))
        self.assertEqual(response.status_code, 200)

        # Current milestone should be Week 1 because t1_2 is incomplete
        current_ms = response.context['current_milestone']
        self.assertIsNotNone(current_ms)
        self.assertEqual(current_ms.week_number, 1)

        # Check that Continue Learning anchor matches milestone ID
        expected_anchor = f"#milestone-week-{current_ms.week_number}"
        self.assertContains(response, expected_anchor)
        self.assertContains(response, 'Continue Learning')

        # Check detail page renders the exact matching ID (Constraint 3)
        detail_response = self.client.get(reverse('roadmaps:path_detail', kwargs={'slug': 'backend-developer'}))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, f'id="milestone-week-{current_ms.week_number}"')
        self.assertContains(detail_response, f'href="#milestone-week-{current_ms.week_number}"')

    def test_completed_roadmap_state(self):
        enr_back = UserRoadmap.objects.create(user=self.user, career_path=self.path_backend)
        TopicProgress.objects.create(user_roadmap=enr_back, topic=self.t1_1, is_completed=True)
        TopicProgress.objects.create(user_roadmap=enr_back, topic=self.t1_2, is_completed=True)
        TopicProgress.objects.create(user_roadmap=enr_back, topic=self.t2_1, is_completed=True)

        response = self.client.get(reverse('roadmaps:path_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_roadmap_completed'])
        self.assertContains(response, 'Review Roadmap')
        self.assertNotContains(response, 'Continue Learning')

    def test_dynamic_path_count_not_hardcoded(self):
        # Test Constraint 1: dynamic count rendered from queryset
        response = self.client.get(reverse('roadmaps:path_list'))
        self.assertEqual(response.status_code, 200)
        paths_count = len(response.context['paths'])
        self.assertContains(response, f'{paths_count} career tracks curated')

    def test_sidebar_active_link_on_roadmaps(self):
        response = self.client.get(reverse('roadmaps:path_list'))
        self.assertEqual(response.status_code, 200)
        # My Roadmap sidebar link should have the active class
        self.assertContains(response, 'class="dash-nav-link active">\n                <i class="bi bi-map"></i>\n                <span>My Roadmap</span>')


class RoadmapEarnedSkillsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='skilluser',
            email='skilluser@example.com',
            password='password123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='password123'
        )
        self.client.force_login(self.user)

        self.path_backend = CareerPath.objects.create(
            name='Backend Engineering',
            slug='backend-eng',
            description='Backend track',
            estimated_weeks=4
        )
        self.ms_backend = Milestone.objects.create(
            career_path=self.path_backend,
            week_number=1,
            title='Python & Django Basics'
        )
        self.topic_django = Topic.objects.create(
            milestone=self.ms_backend,
            title='Django Fundamentals',
            skills_taught='Django, Python Web Development'
        )
        self.topic_rest = Topic.objects.create(
            milestone=self.ms_backend,
            title='Building REST APIs',
            skills_taught='REST APIs, Django REST Framework'
        )
        self.topic_django_adv = Topic.objects.create(
            milestone=self.ms_backend,
            title='Advanced Django',
            skills_taught='Django, ORM Optimization'
        )
        self.topic_empty_skills = Topic.objects.create(
            milestone=self.ms_backend,
            title='Generic Reading',
            skills_taught=''
        )
        self.topic_malformed = Topic.objects.create(
            milestone=self.ms_backend,
            title='Malformed Test',
            skills_taught=' Docker , , containerization, Docker '
        )

        self.path_devops = CareerPath.objects.create(
            name='DevOps Track',
            slug='devops-track',
            description='DevOps track',
            estimated_weeks=4
        )
        self.ms_devops = Milestone.objects.create(
            career_path=self.path_devops,
            week_number=1,
            title='Containers'
        )
        self.topic_docker = Topic.objects.create(
            milestone=self.ms_devops,
            title='Docker Basics',
            skills_taught='Docker, Containerization'
        )

        # Enrolls
        self.enr_backend = UserRoadmap.objects.create(
            user=self.user,
            career_path=self.path_backend
        )
        self.enr_devops = UserRoadmap.objects.create(
            user=self.user,
            career_path=self.path_devops
        )

    def test_completing_topic_resolves_skills_taught(self):
        from .services import get_topic_skills
        skills = get_topic_skills(self.topic_django)
        self.assertEqual(skills, ['Django', 'Python Web Development'])

    def test_completing_topic_produces_roadmap_earned_skills(self):
        from .services import get_user_earned_skills_set
        # Initially 0
        self.assertEqual(get_user_earned_skills_set(self.user), set())

        # Complete Django topic
        response = self.client.post(reverse('roadmaps:toggle_topic', args=[self.topic_django.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_completed'])
        self.assertIn('Django', data['earned_skills'])
        self.assertIn('Python Web Development', data['earned_skills'])

        # Check service output
        earned = get_user_earned_skills_set(self.user)
        self.assertIn('Django', earned)
        self.assertIn('Python Web Development', earned)

    def test_completing_same_topic_repeatedly_does_not_duplicate_skills(self):
        from .services import get_user_earned_skills_set
        prog, _ = TopicProgress.objects.get_or_create(
            user_roadmap=self.enr_backend,
            topic=self.topic_django,
            defaults={'is_completed': True}
        )
        prog.is_completed = True
        prog.save()

        earned = get_user_earned_skills_set(self.user)
        self.assertEqual(len([s for s in earned if s == 'Django']), 1)

    def test_two_topics_teaching_same_skill_produce_one_normalized_skill(self):
        from .services import get_user_earned_skills_set
        # topic_django and topic_django_adv both teach 'Django'
        TopicProgress.objects.create(user_roadmap=self.enr_backend, topic=self.topic_django, is_completed=True)
        TopicProgress.objects.create(user_roadmap=self.enr_backend, topic=self.topic_django_adv, is_completed=True)

        earned = get_user_earned_skills_set(self.user)
        # 'Django' should only exist once in the set
        django_skills = [s for s in earned if s.lower() == 'django']
        self.assertEqual(len(django_skills), 1)

    def test_uncompleting_topic_retains_skill_if_another_completed_topic_teaches_it(self):
        from .services import get_user_earned_skills_set
        TopicProgress.objects.create(user_roadmap=self.enr_backend, topic=self.topic_django, is_completed=True)
        TopicProgress.objects.create(user_roadmap=self.enr_backend, topic=self.topic_django_adv, is_completed=True)

        # Uncheck topic_django
        response = self.client.post(reverse('roadmaps:toggle_topic', args=[self.topic_django.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['is_completed'])
        # 'Django' was NOT lost because topic_django_adv is still complete
        self.assertNotIn('Django', data['lost_skills'])

        earned = get_user_earned_skills_set(self.user)
        self.assertIn('Django', earned)

    def test_uncompleting_final_topic_removes_from_earned_skills(self):
        from .services import get_user_earned_skills_set
        # Complete only topic_rest
        TopicProgress.objects.create(user_roadmap=self.enr_backend, topic=self.topic_rest, is_completed=True)
        self.assertIn('REST APIs', get_user_earned_skills_set(self.user))

        # Uncomplete topic_rest
        response = self.client.post(reverse('roadmaps:toggle_topic', args=[self.topic_rest.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['is_completed'])
        self.assertIn('REST APIs', data['lost_skills'])

        # Now REST APIs is gone from roadmap-earned skills
        self.assertNotIn('REST APIs', get_user_earned_skills_set(self.user))

    def test_empty_skills_taught_awards_no_skill(self):
        from .services import get_topic_skills, get_user_earned_skills_set
        self.assertEqual(get_topic_skills(self.topic_empty_skills), [])

        response = self.client.post(reverse('roadmaps:toggle_topic', args=[self.topic_empty_skills.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['earned_skills'], [])
        self.assertEqual(get_user_earned_skills_set(self.user), set())

    def test_malformed_and_duplicate_skills_taught_normalized(self):
        from .services import get_topic_skills
        skills = get_topic_skills(self.topic_malformed)
        # ' Docker , , containerization, Docker ' -> ['Docker', 'containerization']
        self.assertEqual(len(skills), 2)
        self.assertIn('Docker', skills)
        self.assertIn('containerization', skills)

    def test_multiple_roadmaps_contribute_skills(self):
        from .services import get_user_earned_skills_set
        # Complete Django from backend roadmap
        TopicProgress.objects.create(user_roadmap=self.enr_backend, topic=self.topic_django, is_completed=True)
        # Complete Docker from devops roadmap
        TopicProgress.objects.create(user_roadmap=self.enr_devops, topic=self.topic_docker, is_completed=True)

        earned = get_user_earned_skills_set(self.user)
        self.assertIn('Django', earned)
        self.assertIn('Docker', earned)

    def test_unauthorized_user_cannot_toggle_another_users_topic(self):
        # other_user has no enrollment in backend path
        self.client.force_login(self.other_user)
        response = self.client.post(reverse('roadmaps:toggle_topic', args=[self.topic_django.id]))
        # get_object_or_404 returns 404 because user_roadmap for other_user does not exist
        self.assertEqual(response.status_code, 404)

