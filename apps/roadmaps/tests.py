from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.management import call_command

from .models import CareerPath, Milestone, Topic, UserRoadmap, TopicProgress

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
