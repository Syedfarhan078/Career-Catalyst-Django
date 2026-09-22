from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.management import call_command
import json

from apps.profiles.models import StudentProfile
from .models import (
    QuestionCategory,
    Question,
    UserAttempt,
    UserAttemptDetail,
    MockInterviewSession,
    MockInterviewChat,
    ProctorLog,
)
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
        self.profile = StudentProfile.objects.create(
            user=self.user,
            career_goal='Software Engineer',
            preferred_domain='Web Development'
        )
        self.client.force_login(self.user)

        # Mock category and question
        self.category = QuestionCategory.objects.create(
            name='Aptitude Practice',
            slug='aptitude',
            description='Test category description'
        )
        self.mcq_question = Question.objects.create(
            category=self.category,
            title='Math Logic',
            content='What is 2 + 2?',
            question_type='MCQ',
            difficulty='Easy',
            options=['3', '4', '5', '6'],
            correct_option='B'
        )
        self.coding_category = QuestionCategory.objects.create(
            name='Coding Challenges',
            slug='coding',
            description='Coding track'
        )
        self.coding_challenge = Question.objects.create(
            category=self.coding_category,
            title='Factorial Function',
            content='Implement a factorial function in Python.',
            question_type='Coding',
            difficulty='Easy',
            test_cases=[{"input": "5", "expected": "120", "function": "factorial"}]
        )
        self.behavioral_category = QuestionCategory.objects.create(
            name='HR & Behavioral',
            slug='behavioral',
            description='Behavioral track'
        )
        self.star_question = Question.objects.create(
            category=self.behavioral_category,
            title='Handling Deadlines',
            content='Tell me about a time you faced a challenging project deadline.',
            question_type='STAR',
            difficulty='Medium'
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

    def test_hub_view_rendering_and_sidebar_context(self):
        url = reverse('interviews:hub')
        response = self.client.get(url, HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interviews/hub.html')
        self.assertIn('user_initials', response.context)
        self.assertIn('target_career', response.context)
        self.assertEqual(response.context['target_career'], 'Software Engineer')
        self.assertIn('categories', response.context)
        self.assertIn('total_attempts', response.context)
        self.assertIn('avg_score', response.context)
        # Verify sidebar "Interview Prep" is marked active
        content = response.content.decode('utf-8')
        self.assertIn('Interview Prep', content)
        self.assertIn('active', content)

    def test_unauthenticated_user_redirect(self):
        self.client.logout()
        url = reverse('interviews:hub')
        response = self.client.get(url, HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_quiz_start_and_submission(self):
        start_url = reverse('interviews:start_quiz', args=['aptitude'])
        response = self.client.get(start_url, HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interviews/quiz.html')
        self.assertEqual(len(response.context['questions']), 1)

        # Submit Quiz
        submit_url = reverse('interviews:submit_quiz')
        post_data = {
            f'question_{self.mcq_question.id}': 'B',  # Correct option
            'category_id': self.category.id,
            'proctor_violations': '0'
        }
        submit_response = self.client.post(submit_url, post_data, HTTP_HOST='127.0.0.1')
        self.assertEqual(submit_response.status_code, 200)
        self.assertTemplateUsed(submit_response, 'interviews/quiz_result.html')
        self.assertEqual(submit_response.context['attempt'].score, 100.0)
        self.assertEqual(submit_response.context['correct_count'], 1)

        # Check DB attempt
        self.assertEqual(UserAttempt.objects.filter(user=self.user, category=self.category).count(), 1)
        attempt = UserAttempt.objects.get(user=self.user, category=self.category)
        self.assertEqual(attempt.score, 100.0)
        self.assertEqual(attempt.details.count(), 1)
        self.assertTrue(attempt.details.first().is_correct)

    def test_coding_list_and_detail(self):
        list_url = reverse('interviews:coding_list')
        response = self.client.get(list_url, HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interviews/coding_list.html')
        self.assertIn('solved_challenge_ids', response.context)
        self.assertEqual(response.context['solved_count'], 0)

        detail_url = reverse('interviews:coding_detail', args=[self.coding_challenge.id])
        detail_resp = self.client.get(detail_url, HTTP_HOST='127.0.0.1')
        self.assertEqual(detail_resp.status_code, 200)
        self.assertTemplateUsed(detail_resp, 'interviews/coding_detail.html')
        self.assertEqual(detail_resp.context['challenge'], self.coding_challenge)

    def test_coding_submission(self):
        submit_url = reverse('interviews:submit_code', args=[self.coding_challenge.id])
        valid_code = "def factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n - 1)\n"
        data = {
            "code": valid_code,
            "proctor_violations": 0
        }
        response = self.client.post(
            submit_url,
            data=json.dumps(data),
            content_type='application/json',
            HTTP_HOST='127.0.0.1'
        )
        self.assertEqual(response.status_code, 200)
        resp_json = response.json()
        self.assertTrue(resp_json.get('success'))

        # Check attempt created
        attempt = UserAttempt.objects.filter(user=self.user, details__question=self.coding_challenge).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.score, 100.0)

    def test_behavioral_list_detail_and_star_submission(self):
        list_url = reverse('interviews:behavioral_list')
        response = self.client.get(list_url, HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interviews/behavioral_list.html')
        self.assertEqual(response.context['completed_count'], 0)

        detail_url = reverse('interviews:behavioral_detail', args=[self.star_question.id])
        detail_resp = self.client.get(detail_url, HTTP_HOST='127.0.0.1')
        self.assertEqual(detail_resp.status_code, 200)
        self.assertTemplateUsed(detail_resp, 'interviews/behavioral_detail.html')

        # Submit Full STAR response (all sections >= 40 chars)
        submit_url = reverse('interviews:submit_star', args=[self.star_question.id])
        star_data = {
            'situation': 'During my final year project our 4-person team had to build a cloud deployment pipeline.',
            'task': 'My task was to configure automated unit testing and containerization before sprint review.',
            'action': 'I wrote Dockerfiles, configured GitHub Actions workflows, and debugged test runner failures.',
            'result': 'The pipeline reduced build times by 40% and our team completed the milestone ahead of time.',
            'proctor_violations': '0'
        }
        star_resp = self.client.post(submit_url, star_data, HTTP_HOST='127.0.0.1')
        self.assertEqual(star_resp.status_code, 200)
        self.assertTemplateUsed(star_resp, 'interviews/star_result.html')
        self.assertEqual(star_resp.context['score'], 100)

        # Check attempt
        attempt = UserAttempt.objects.filter(user=self.user, details__question=self.star_question).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.score, 100.0)

    def test_mock_interview_creation_and_reply(self):
        # 1. Start Mock Interview
        start_url = reverse('interviews:start_mock')
        response = self.client.post(start_url, {"role": "Data Scientist"}, HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 302)

        session = MockInterviewSession.objects.first()
        self.assertEqual(session.role, "Data Scientist")
        self.assertEqual(session.chats.count(), 1)  # Opening prompt

        # 2. Reply as candidate (Turn 1)
        reply_url = reverse('interviews:chat_reply', args=[session.id])
        reply_data = {
            "message": "Hi, I have solid experience with python, django, pandas, sql and data modeling algorithms.",
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

        # 3. Candidate Turn 2
        reply_data2 = {
            "message": "For this problem I would use cross-validation, feature engineering, and regularized linear regression.",
            "proctor_violations": 1
        }
        response2 = self.client.post(
            reply_url,
            data=json.dumps(reply_data2),
            content_type='application/json',
            HTTP_HOST='127.0.0.1'
        )
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(session.chats.count(), 5)

        # 4. Candidate Turn 3 (Final turn completes the session)
        reply_data3 = {
            "message": "When disagreements happen in a project, I schedule a 1-on-1 discussion, review metrics, and find a data-driven consensus.",
            "proctor_violations": 1
        }
        response3 = self.client.post(
            reply_url,
            data=json.dumps(reply_data3),
            content_type='application/json',
            HTTP_HOST='127.0.0.1'
        )
        self.assertEqual(response3.status_code, 200)
        resp3_json = response3.json()
        self.assertTrue(resp3_json.get('completed'))
        self.assertIn(reverse('interviews:mock_report', args=[session.id]), resp3_json.get('redirect_url'))

        # Reload session and check completion
        session.refresh_from_db()
        self.assertTrue(session.is_completed)
        self.assertGreater(session.overall_score, 0)

        # 5. Verify Mock Report view renders without errors and computes percentages
        report_url = reverse('interviews:mock_report', args=[session.id])
        report_resp = self.client.get(report_url, HTTP_HOST='127.0.0.1')
        self.assertEqual(report_resp.status_code, 200)
        self.assertTemplateUsed(report_resp, 'interviews/mock_report.html')
        self.assertIn('comm_pct', report_resp.context)
        self.assertIn('keyword_pct', report_resp.context)
        self.assertIn('proctor_pct', report_resp.context)
        self.assertIn('matched_words', report_resp.context)
        self.assertGreaterEqual(report_resp.context['comm_pct'], 0.0)
        self.assertGreaterEqual(report_resp.context['keyword_pct'], 0.0)
        self.assertGreaterEqual(report_resp.context['proctor_pct'], 0.0)

    def test_performance_reports_view(self):
        # Create attempt and proctor violation
        UserAttempt.objects.create(
            user=self.user,
            category=self.category,
            score=85.0,
            proctor_violations_count=0
        )
        ProctorLog.objects.create(
            user=self.user,
            session_type='Quiz',
            session_id=1,
            violation_type='Tab Switch'
        )

        url = reverse('interviews:reports')
        response = self.client.get(url, HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interviews/reports.html')
        self.assertEqual(len(response.context['attempts']), 1)
        self.assertEqual(len(response.context['violations']), 1)
        self.assertIn('mocks', response.context)
        self.assertIn('user_initials', response.context)
