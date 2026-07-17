from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command
import json

from .models import QuestionCategory, Question, UserAttempt, UserAttemptDetail, MockInterviewSession, MockInterviewChat, ProctorLog
from .runner import run_code

User = get_user_model()

class InterviewPrepTests(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            username='candidate1',
            email='candidate1@example.com',
            password='password123'
        )
        self.client.force_login(self.user)

        # Mock category and question
        self.category = QuestionCategory.objects.create(
            name='Test Category',
            slug='test-category',
            description='Test category description'
        )
        self.question = Question.objects.create(
            category=self.category,
            title='Test Question',
            content='What is 2 + 2?',
            question_type='MCQ',
            difficulty='Easy',
            options=['3', '4', '5', '6'],
            correct_option='B'
        )

    def test_database_seeding(self):
        # Delete items so we test clean seeding command
        Question.objects.all().delete()
        QuestionCategory.objects.all().delete()
        
        call_command('seed_interviews')
        
        self.assertGreater(QuestionCategory.objects.count(), 0)
        self.assertGreater(Question.objects.filter(question_type='MCQ').count(), 0)
        self.assertGreater(Question.objects.filter(question_type='Coding').count(), 0)
        self.assertGreater(Question.objects.filter(question_type='STAR').count(), 0)

    def test_code_runner_valid(self):
        code = "def factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n - 1)\n"
        test_cases = [{"input": "5", "expected": "120", "function": "factorial"}]
        result = run_code(code, test_cases)
        self.assertTrue(result.get("success"))
        self.assertEqual(result["results"][0]["output"], 120)

    def test_code_runner_invalid(self):
        code = "def factorial(n):\n    return -99\n"
        test_cases = [{"input": "5", "expected": "120", "function": "factorial"}]
        result = run_code(code, test_cases)
        self.assertFalse(result.get("success"))
        self.assertEqual(result["results"][0]["output"], -99)

    def test_code_runner_infinite_loop(self):
        code = "def factorial(n):\n    while True: pass\n"
        test_cases = [{"input": "5", "expected": "120", "function": "factorial"}]
        result = run_code(code, test_cases)
        self.assertFalse(result.get("success"))
        self.assertIn("Timeout", result.get("error", ""))

    def test_proctor_violation_logging(self):
        url = reverse('interviews:log_proctor_violation')
        data = {
            "session_type": "Quiz",
            "session_id": 1,
            "violation_type": "Tab Switch"
        }
        response = self.client.post(
            url, 
            data=json.dumps(data), 
            content_type='application/json',
            HTTP_HOST='127.0.0.1'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProctorLog.objects.filter(user=self.user, violation_type='Tab Switch').count(), 1)

    def test_mock_interview_creation_and_reply(self):
        # 1. Start Mock Interview
        start_url = reverse('interviews:start_mock')
        response = self.client.post(start_url, {"role": "Data Scientist"}, HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 302)
        
        session = MockInterviewSession.objects.first()
        self.assertEqual(session.role, "Data Scientist")
        self.assertEqual(session.chats.count(), 1)  # Opening prompt
        
        # 2. Reply as candidate
        reply_url = reverse('interviews:chat_reply', args=[session.id])
        reply_data = {
            "message": "Hi, I have standard experience with python, django, pandas and databases.",
            "proctor_violations": 1
        }
        response = self.client.post(
            reply_url,
            data=json.dumps(reply_data),
            content_type='application/json',
            HTTP_HOST='127.0.0.1'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(session.chats.count(), 3)  # Candidate reply + Interviewer next Q
