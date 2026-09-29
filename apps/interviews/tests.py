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


class InterviewSecurityTests(TestCase):
    """
    Exhaustive security and sandbox verification tests.
    Asserts rejection of dangerous imports, filesystem/eval exploits,
    environment leakage, memory/loop DOS, and output flooding.
    """

    def test_dangerous_module_import_rejected(self):
        dangerous_snippets = [
            "import os\ndef solution(): return os.getcwd()",
            "import sys\ndef solution(): return sys.executable",
            "import subprocess\ndef solution(): return subprocess.run(['ls'])",
            "import socket\ndef solution(): return socket.gethostname()",
            "import shutil\ndef solution(): return shutil.rmtree('/')",
            "import ctypes\ndef solution(): return ctypes.CDLL(None)",
            "import urllib.request\ndef solution(): return 'pwned'",
        ]
        test_cases = [{"input": "", "expected": "", "function": "solution"}]
        for snippet in dangerous_snippets:
            result = run_code(snippet, test_cases)
            self.assertFalse(result.get("success"), f"Snippet should have failed: {snippet}")
            self.assertEqual(result.get("status"), "sandbox_error")
            self.assertIn("Security Violation", result.get("error", ""))

    def test_filesystem_open_call_rejected(self):
        code = "def read_db():\n    with open('db.sqlite3', 'r') as f:\n        return f.read()\n"
        test_cases = [{"input": "", "expected": "", "function": "read_db"}]
        result = run_code(code, test_cases)
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("status"), "sandbox_error")

    def test_eval_and_exec_builtins_rejected(self):
        code = "def exploit():\n    return eval('2 + 2')\n"
        test_cases = [{"input": "", "expected": 4, "function": "exploit"}]
        result = run_code(code, test_cases)
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("status"), "sandbox_error")

    def test_reflection_attributes_rejected(self):
        code = "def exploit():\n    return ().__class__.__subclasses__()\n"
        test_cases = [{"input": "", "expected": "", "function": "exploit"}]
        result = run_code(code, test_cases)
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("status"), "sandbox_error")

    def test_infinite_loop_timeout_deterministic(self):
        code = "def infinite_fn():\n    while True:\n        x = 1\n"
        test_cases = [{"input": "", "expected": "", "function": "infinite_fn"}]
        result = run_code(code, test_cases)
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("status"), "timeout")
        self.assertIn("Timeout", result.get("error", ""))

    def test_excessive_stdout_truncated(self):
        code = "def flood():\n    print('A' * 100000)\n    return 42\n"
        test_cases = [{"input": "", "expected": 42, "function": "flood"}]
        result = run_code(code, test_cases)
        self.assertTrue(result.get("success"))
        self.assertLessEqual(len(result.get("stdout", "")), 65536)


class QuizSessionTests(TestCase):
    """
    Persistent server-managed QuizSession tests.
    Verifies multi-tab isolation, server-side countdown timestamps,
    anti-clash session tracking, and idempotent atomic submissions.
    """

    def setUp(self):
        self.user_a = User.objects.create_user(username='cand_a', email='cand_a@example.com', password='password123')
        self.user_b = User.objects.create_user(username='cand_b', email='cand_b@example.com', password='password123')
        self.client.force_login(self.user_a)

        self.category = QuestionCategory.objects.create(name='Computer Architecture', slug='comp-arch')
        for i in range(8):
            Question.objects.create(
                category=self.category,
                title=f'Arch Q{i}',
                content=f'Question content {i}',
                question_type='MCQ',
                difficulty='Easy' if i < 3 else ('Medium' if i < 6 else 'Hard'),
                options=['A1', 'B2', 'C3', 'D4'],
                correct_option='A'
            )

    def test_quiz_session_created_and_resumed(self):
        from apps.interviews.services.quiz_engine import QuizEngineService
        from apps.interviews.models import QuizSession

        session1, questions1, created1 = QuizEngineService.get_or_create_active_session(
            user=self.user_a, category=self.category, count=5
        )
        self.assertTrue(created1)
        self.assertEqual(len(questions1), 5)
        self.assertFalse(session1.is_submitted)

        # Calling again should resume the active session without regenerating questions
        session2, questions2, created2 = QuizEngineService.get_or_create_active_session(
            user=self.user_a, category=self.category, count=5
        )
        self.assertFalse(created2)
        self.assertEqual(session1.id, session2.id)
        self.assertEqual([q.id for q in questions1], [q.id for q in questions2])

    def test_multi_tab_isolation_distinct_categories(self):
        from apps.interviews.services.quiz_engine import QuizEngineService

        cat2 = QuestionCategory.objects.create(name='Operating Systems', slug='os')
        for i in range(5):
            Question.objects.create(
                category=cat2,
                title=f'OS Q{i}',
                content=f'OS Content {i}',
                question_type='MCQ',
                options=['A', 'B', 'C', 'D'],
                correct_option='B'
            )

        session_arch, _, _ = QuizEngineService.get_or_create_active_session(self.user_a, self.category)
        session_os, _, _ = QuizEngineService.get_or_create_active_session(self.user_a, cat2)

        # Both sessions coexist independently with distinct UUIDs and question sets
        self.assertNotEqual(session_arch.session_uuid, session_os.session_uuid)
        self.assertNotEqual(session_arch.category_id, session_os.category_id)

    def test_duplicate_submission_idempotency(self):
        from apps.interviews.services.quiz_engine import QuizEngineService

        session, questions, _ = QuizEngineService.get_or_create_active_session(self.user_a, self.category)
        answers = {f'question_{q.id}': 'A' for q in questions}

        # First submission
        res1 = QuizEngineService.submit_quiz_session(
            user=self.user_a,
            session_uuid_str=str(session.session_uuid),
            category_id=self.category.id,
            answers_dict=answers
        )
        self.assertFalse(res1['already_submitted'])
        self.assertEqual(res1['score'], 100)

        # Second submission of the same session must return existing attempt without creating new records
        attempt_count_before = UserAttempt.objects.filter(user=self.user_a).count()
        res2 = QuizEngineService.submit_quiz_session(
            user=self.user_a,
            session_uuid_str=str(session.session_uuid),
            category_id=self.category.id,
            answers_dict=answers
        )
        self.assertTrue(res2['already_submitted'])
        self.assertEqual(res2['score'], 100)
        self.assertEqual(UserAttempt.objects.filter(user=self.user_a).count(), attempt_count_before)

    def test_unauthorized_user_cannot_submit_others_quiz(self):
        from apps.interviews.services.quiz_engine import QuizEngineService
        from django.core.exceptions import PermissionDenied

        session, questions, _ = QuizEngineService.get_or_create_active_session(self.user_a, self.category)
        answers = {f'question_{q.id}': 'A' for q in questions}

        # User B attempts to submit User A's session
        with self.assertRaises(PermissionDenied):
            QuizEngineService.submit_quiz_session(
                user=self.user_b,
                session_uuid_str=str(session.session_uuid),
                category_id=self.category.id,
                answers_dict=answers
            )


class CodingEngineTests(TestCase):
    """
    Modernized Coding Challenge evaluation tests.
    Tests partial test scoring, hidden test protection, runtime errors, and competency evidence.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='coder1', email='coder1@example.com', password='password123')
        self.client.force_login(self.user)
        self.category = QuestionCategory.objects.create(name='Algorithms', slug='algorithms')
        self.challenge = Question.objects.create(
            category=self.category,
            title='Two Sum',
            content='Find indices of elements that sum to target.',
            question_type='Coding',
            difficulty='Easy',
            test_cases=[
                {"input": "[2, 7, 11, 15], 9", "expected": "[0, 1]", "function": "two_sum"},
                {"input": "[3, 2, 4], 6", "expected": "[1, 2]", "function": "two_sum"}
            ],
            hidden_test_cases=[
                {"input": "[3, 3], 6", "expected": "[0, 1]", "function": "two_sum"}
            ],
            skills_evaluated='Algorithms, Python, Data Structures'
        )

    def test_partial_test_scoring(self):
        # Passes test 1 and hidden test, fails test 2
        code = """
def two_sum(nums, target):
    if nums == [2, 7, 11, 15]:
        return [0, 1]
    if nums == [3, 3]:
        return [0, 1]
    return [-1, -1]
"""
        url = reverse('interviews:submit_code', args=[self.challenge.id])
        resp = self.client.post(url, data=json.dumps({"code": code}), content_type='application/json', HTTP_HOST='127.0.0.1')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # 2 of 3 tests passed -> 67%
        self.assertEqual(data['passed_tests'], 2)
        self.assertEqual(data['total_tests'], 3)
        self.assertEqual(data['score'], 67)
        self.assertFalse(data['success'])

    def test_hidden_test_case_masked_in_client_response(self):
        code = "def two_sum(nums, target): return [0, 1]"
        url = reverse('interviews:submit_code', args=[self.challenge.id])
        resp = self.client.post(url, data=json.dumps({"code": code}), content_type='application/json', HTTP_HOST='127.0.0.1')
        data = resp.json()
        # Case 3 is the hidden test case, verify its output and expected values are masked
        hidden_res = next((r for r in data['results'] if r.get('case') == 3), None)
        self.assertIsNotNone(hidden_res)
        self.assertEqual(hidden_res['output'], '[Hidden Test]')
        self.assertEqual(hidden_res['expected'], '[Hidden Test]')

    def test_malformed_json_submission_rejected(self):
        url = reverse('interviews:submit_code', args=[self.challenge.id])
        resp = self.client.post(url, data="NOT_JSON", content_type='application/json', HTTP_HOST='127.0.0.1')
        self.assertEqual(resp.status_code, 400)

    def test_empty_code_submission_rejected(self):
        url = reverse('interviews:submit_code', args=[self.challenge.id])
        resp = self.client.post(url, data=json.dumps({"code": "   "}), content_type='application/json', HTTP_HOST='127.0.0.1')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['success'])


class STARBehavioralTests(TestCase):
    """
    STAR Behavioral Evaluator tests.
    Verifies rubric scoring, anti-gaming detection, and feedback generation.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='star_cand', email='star_cand@example.com', password='password123')
        self.client.force_login(self.user)
        self.category = QuestionCategory.objects.create(name='Behavioral', slug='behavioral')
        self.question = Question.objects.create(
            category=self.category,
            title='Leadership Under Pressure',
            content='Tell me about leading a project under high stakes.',
            question_type='STAR',
            skills_evaluated='Leadership, Communication'
        )

    def test_star_repetitive_characters_rejected(self):
        from apps.interviews.services.star_evaluator import STAREvaluatorService
        res = STAREvaluatorService.evaluate(
            situation="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            task="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            action="cccccccccccccccccccccccccccccccccccccccc",
            result="dddddddddddddddddddddddddddddddddddddddd"
        )
        self.assertEqual(res['score'], 0)
        self.assertIn("repeated characters", res['sections']['situation']['feedback'][0])

    def test_star_repeated_word_spam_rejected(self):
        from apps.interviews.services.star_evaluator import STAREvaluatorService
        res = STAREvaluatorService.evaluate(
            situation="project project project project project project project",
            task="task task task task task task task task",
            action="action action action action action action action",
            result="result result result result result result result"
        )
        self.assertEqual(res['score'], 0)
        self.assertIn("vocabulary diversity", res['sections']['situation']['feedback'][0])

    def test_star_weak_result_section_penalized(self):
        from apps.interviews.services.star_evaluator import STAREvaluatorService
        res = STAREvaluatorService.evaluate(
            situation="During our final semester, the e-commerce client had a major production database outage.",
            task="My responsibility was to investigate database deadlocks and restore system reliability.",
            action="I analyzed query execution plans, refactored queries, and configured connection pooling.",
            result="Everything was okay afterwards."  # Weak result lacking metrics
        )
        # Result section should not get full 25 points due to missing measurable impact
        self.assertLess(res['sections']['result']['score'], 25)
        self.assertTrue(any("Quantify results" in fb for fb in res['sections']['result']['feedback']))


class MockInterviewStateEngineTests(TestCase):
    """
    Mock Interview State Machine & Role Awareness tests.
    Verifies state transitions, role-track question banks, and multi-dimensional rubrics.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='mock_user', email='mock_user@example.com', password='password123')
        self.client.force_login(self.user)

    def test_role_track_matching_canonical(self):
        from apps.interviews.services.mock_engine import MockInterviewEngine
        self.assertEqual(MockInterviewEngine.match_role_track("React Frontend Engineer"), "frontend")
        self.assertEqual(MockInterviewEngine.match_role_track("Django Backend Developer"), "backend")
        self.assertEqual(MockInterviewEngine.match_role_track("Data Scientist & Analyst"), "data")
        self.assertEqual(MockInterviewEngine.match_role_track("Machine Learning Engineer"), "ml")
        self.assertEqual(MockInterviewEngine.match_role_track("DevOps & Cloud Specialist"), "devops")
        self.assertEqual(MockInterviewEngine.match_role_track("Full Stack Developer"), "backend")

    def test_empty_candidate_reply_rejected(self):
        session = MockInterviewSession.objects.create(user=self.user, role="Software Engineer")
        url = reverse('interviews:chat_reply', args=[session.id])
        resp = self.client.post(url, data=json.dumps({"message": "   "}), content_type='application/json', HTTP_HOST='127.0.0.1')
        self.assertEqual(resp.status_code, 400)

    def test_proctor_violations_do_not_dock_mock_score(self):
        session = MockInterviewSession.objects.create(user=self.user, role="Backend Developer")
        url = reverse('interviews:chat_reply', args=[session.id])

        # Candidate turns with focus violations reported
        turns = [
            "Hi, I am a backend developer experienced with Django, PostgreSQL, Redis, and building high-scale REST APIs.",
            "For high throughput, I configure connection pooling, use Redis caching with LRU eviction, and optimize database indexing because query latency directly impacts system throughput.",
            "During a release conflict, I organized a design review with stakeholders to evaluate latency vs. storage tradeoffs, ensuring our team maintained zero downtime."
        ]
        for msg in turns:
            resp = self.client.post(
                url,
                data=json.dumps({"message": msg, "proctor_violations": 4}),
                content_type='application/json',
                HTTP_HOST='127.0.0.1'
            )
            self.assertEqual(resp.status_code, 200)

        session.refresh_from_db()
        self.assertTrue(session.is_completed)
        # Score is evaluated from rubric and NOT docked by 40 points
        self.assertGreaterEqual(session.overall_score, 70)


class ProctorAuditTests(TestCase):
    """
    Proctoring audit & rate-limiting tests.
    Verifies that proctoring functions as an integrity audit stream rather than direct score deduction.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='proctor_user', email='proctor_user@example.com', password='password123')
        self.client.force_login(self.user)

    def test_proctor_logging_valid(self):
        url = reverse('interviews:log_proctor_violation')
        data = {"session_type": "Quiz", "session_id": 1, "violation_type": "Window Blur"}
        resp = self.client.post(url, data=json.dumps(data), content_type='application/json', HTTP_HOST='127.0.0.1')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    def test_proctor_invalid_session_type_rejected(self):
        url = reverse('interviews:log_proctor_violation')
        data = {"session_type": "HackingAttempt", "session_id": 1, "violation_type": "Tab Switch"}
        resp = self.client.post(url, data=json.dumps(data), content_type='application/json', HTTP_HOST='127.0.0.1')
        self.assertEqual(resp.status_code, 400)


class CareerIntegrationAndRecommendationTests(TestCase):
    """
    Integration tests linking Interview Prep to CareerCatalyst's skill and recommendation ecosystem.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='career_user', email='career_user@example.com', password='password123')
        self.client.force_login(self.user)
        self.profile = StudentProfile.objects.create(
            user=self.user,
            career_goal='Backend Developer',
            skills='Python, SQL'
        )

    def test_competency_evidence_recorded_and_retrieved(self):
        from apps.interviews.services.competency import CompetencyEvidenceService

        CompetencyEvidenceService.record_evidence(
            user=self.user,
            skill_name='Django',
            source_type='TECHNICAL_QUIZ',
            score=90
        )
        skills = CompetencyEvidenceService.get_user_verified_interview_skills(self.user)
        self.assertIn('Django', skills)

    def test_hub_recommendations_generation(self):
        from apps.interviews.services.recommendations import InterviewRecommendationService

        recs = InterviewRecommendationService.get_personalized_recommendations(self.user)
        self.assertEqual(recs['target_career'], 'Backend Developer')
        self.assertIsInstance(recs['recommended_focus'], list)

