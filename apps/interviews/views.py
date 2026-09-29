import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.db.models import Avg, Count
from django.urls import reverse
from django.core.exceptions import ValidationError, PermissionDenied

from .models import (
    QuestionCategory, Question, UserAttempt, UserAttemptDetail,
    MockInterviewSession, MockInterviewChat, ProctorLog,
    QuizSession, InterviewCompetencyEvidence
)
from .services.code_execution import CodeExecutionService, run_code
from .services.quiz_engine import QuizEngineService
from .services.star_evaluator import STAREvaluatorService
from .services.mock_engine import MockInterviewEngine, ROLE_QUESTION_BANKS
from .services.proctoring import ProctorAuditService
from .services.competency import CompetencyEvidenceService
from .services.recommendations import InterviewRecommendationService

logger = logging.getLogger(__name__)


def get_user_sidebar_context(user):
    """
    Helper to provide consistent sidebar user badge and career context
    across all Interview Prep views.
    """
    profile = getattr(user, 'studentprofile', None)
    first_initial = (user.first_name[:1] if user.first_name else user.username[:1]).upper()
    last_initial = (user.last_name[:1] if user.last_name else "").upper()
    user_initials = f"{first_initial}{last_initial}" if last_initial else (user.username[:2].upper())
    target_career = profile.career_goal.strip() if (profile and profile.career_goal) else ""
    return {
        'profile': profile,
        'user_initials': user_initials,
        'target_career': target_career,
    }


@method_decorator(login_required, name='dispatch')
class InterviewHubView(TemplateView):
    template_name = "interviews/hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Sidebar context
        context.update(get_user_sidebar_context(user))

        # Fetch categories
        categories = QuestionCategory.objects.all()
        context["categories"] = categories

        # Aggregate user stats
        attempts = UserAttempt.objects.filter(user=user)
        context["total_attempts"] = attempts.count()
        context["avg_score"] = attempts.aggregate(Avg('score'))['score__avg'] or 0

        mocks = MockInterviewSession.objects.filter(user=user, is_completed=True)
        context["total_mocks"] = mocks.count()
        context["avg_mock_score"] = mocks.aggregate(Avg('overall_score'))['overall_score__avg'] or 0

        context["total_violations"] = ProctorLog.objects.filter(user=user).count()

        # Category question counts
        context["coding_count"] = Question.objects.filter(question_type='Coding').count()
        context["behavioral_count"] = Question.objects.filter(question_type='STAR').count()
        context["aptitude_count"] = Question.objects.filter(category__slug='aptitude', question_type='MCQ').count()
        context["technical_count"] = Question.objects.filter(category__slug='technical', question_type='MCQ').count()

        # Recent activity optimized with select_related
        context["recent_attempts"] = attempts.select_related('category').order_by('-attempted_at')[:4]
        context["recent_mocks"] = mocks.order_by('-started_at')[:3]

        # Personalized recommendations derived from real performance
        recommendations_data = InterviewRecommendationService.get_personalized_recommendations(user)
        context["recommendations"] = recommendations_data.get("recommended_focus", [])
        context["weak_categories"] = recommendations_data.get("weak_categories", [])
        context["missing_skills"] = recommendations_data.get("missing_skills", [])

        return context


@login_required
def start_quiz(request, slug):
    category = get_object_or_404(QuestionCategory, slug=slug)
    
    # Delegate to QuizEngineService for balanced selection and persistent QuizSession
    quiz_session, questions, created = QuizEngineService.get_or_create_active_session(
        user=request.user,
        category=category,
        count=5
    )
    
    if not questions:
        # If no MCQs (like coding or behavioral categories), redirect
        if category.slug == 'coding':
            return redirect('interviews:coding_list')
        elif category.slug == 'behavioral':
            return redirect('interviews:behavioral_list')
        return redirect('interviews:hub')

    # Store backward-compatible session keys alongside persistent QuizSession UUID
    request.session['quiz_active_uuid'] = str(quiz_session.session_uuid)
    request.session['quiz_question_ids'] = [q.id for q in questions]
    request.session['quiz_category_id'] = category.id

    context = {
        "category": category,
        "questions": questions,
        "quiz_session": quiz_session,
        "session_uuid": str(quiz_session.session_uuid),
        "remaining_seconds": quiz_session.remaining_seconds,
    }
    context.update(get_user_sidebar_context(request.user))
    return render(request, "interviews/quiz.html", context)


@login_required
def submit_quiz(request):
    if request.method != 'POST':
        return redirect('interviews:hub')

    session_uuid = request.POST.get('session_uuid') or request.session.get('quiz_active_uuid')
    category_id = request.POST.get('category_id') or request.session.get('quiz_category_id')

    try:
        violations = int(request.POST.get('proctor_violations', 0))
    except (ValueError, TypeError):
        violations = 0

    try:
        result = QuizEngineService.submit_quiz_session(
            user=request.user,
            session_uuid_str=session_uuid,
            category_id=category_id,
            answers_dict=request.POST,
            client_violations_count=violations
        )
    except (ValidationError, PermissionDenied) as e:
        logger.warning(f"Quiz submission rejected: {str(e)}")
        return redirect('interviews:hub')

    # Clean up legacy session keys
    request.session.pop('quiz_category_id', None)
    request.session.pop('quiz_question_ids', None)
    request.session.pop('quiz_active_uuid', None)

    context = {
        "attempt": result["attempt"],
        "category": result["category"],
        "correct_count": result["correct_count"],
        "total": result["total"],
        "is_expired": result.get("is_expired", False),
    }
    context.update(get_user_sidebar_context(request.user))
    return render(request, "interviews/quiz_result.html", context)


@method_decorator(login_required, name='dispatch')
class CodingListView(ListView):
    model = Question
    template_name = "interviews/coding_list.html"
    context_object_name = "challenges"

    def get_queryset(self):
        category = QuestionCategory.objects.filter(slug='coding').first()
        if category:
            return Question.objects.filter(category=category, question_type='Coding')
        return Question.objects.filter(question_type='Coding')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_user_sidebar_context(self.request.user))
        solved_ids = set(
            UserAttemptDetail.objects.filter(
                attempt__user=self.request.user,
                question__question_type='Coding',
                is_correct=True
            ).values_list('question_id', flat=True)
        )
        context["solved_ids"] = solved_ids
        context["solved_challenge_ids"] = solved_ids
        context["solved_count"] = len(solved_ids)
        challenges = context.get("challenges", [])
        context["total_count"] = challenges.count() if hasattr(challenges, 'count') else len(challenges)
        return context


@method_decorator(login_required, name='dispatch')
class CodingDetailView(DetailView):
    model = Question
    template_name = "interviews/coding_detail.html"
    context_object_name = "challenge"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_user_sidebar_context(self.request.user))
        context["attempts"] = UserAttemptDetail.objects.filter(
            attempt__user=self.request.user,
            question=self.object
        ).select_related('attempt').order_by('-attempt__attempted_at')[:5]
        return context


@login_required
def submit_code(request, pk):
    if request.method != 'POST':
        return JsonResponse({"error": "POST method required"}, status=405)

    question = get_object_or_404(Question, pk=pk, question_type='Coding')
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON payload in request."}, status=400)

    code = data.get("code", "")
    try:
        violations = int(data.get("proctor_violations", 0))
    except (ValueError, TypeError):
        violations = 0

    if not code or not code.strip():
        return JsonResponse({"success": False, "error": "Code cannot be empty."})

    # Execute code via isolated CodeExecutionService
    timeout_sec = (question.time_limit_ms / 1000.0) if question.time_limit_ms else 2.0
    mem_limit = question.memory_limit_mb or 128
    
    # Combine public test cases and hidden test cases for execution
    all_tests = list(question.test_cases or [])
    hidden_tests = list(getattr(question, 'hidden_test_cases', []) or [])
    full_test_suite = all_tests + hidden_tests

    exec_result = CodeExecutionService.execute(
        code_str=code,
        test_cases=full_test_suite if full_test_suite else all_tests,
        timeout_seconds=timeout_sec,
        memory_limit_mb=mem_limit
    )

    passed_count = exec_result.get("passed_tests", 0)
    total_count = exec_result.get("total_tests", len(full_test_suite) if full_test_suite else 1)
    
    # Partial scoring: score = passed / total * 100
    score = int(round((passed_count / total_count) * 100)) if total_count > 0 else 0
    is_correct = (score == 100) or exec_result.get("success", False)

    # Filter out hidden test details from client response to prevent leaking test cases
    public_results = []
    for r in exec_result.get("results", []):
        case_idx = r.get("case", 0)
        if case_idx <= len(all_tests):
            public_results.append(r)
        else:
            # Mask hidden test case output
            public_results.append({
                "case": case_idx,
                "passed": r.get("passed", False),
                "output": "[Hidden Test]",
                "expected": "[Hidden Test]",
                "duration_ms": r.get("duration_ms", 0),
                "error": None if r.get("passed") else "Failed hidden test"
            })

    # Save attempt
    category = QuestionCategory.objects.filter(slug='coding').first()
    if not category:
        category, _ = QuestionCategory.objects.get_or_create(slug='coding', defaults={'name': 'Coding Challenges'})

    attempt = UserAttempt.objects.create(
        user=request.user,
        category=category,
        score=score,
        proctor_violations_count=max(0, violations)
    )

    UserAttemptDetail.objects.create(
        attempt=attempt,
        question=question,
        user_answer=code,
        is_correct=is_correct,
        execution_time_ms=exec_result.get("execution_time_ms"),
        memory_used_kb=exec_result.get("memory_used_kb"),
        passed_tests=passed_count,
        total_tests=total_count,
        test_results=public_results,
        execution_status=exec_result.get("status", "")
    )

    # Record interview competency evidence if score >= 80%
    if score >= 80:
        CompetencyEvidenceService.record_coding_evidence(request.user, question, score)

    return JsonResponse({
        "success": exec_result.get("success", False),
        "score": score,
        "passed_tests": passed_count,
        "total_tests": total_count,
        "results": public_results,
        "error": exec_result.get("error", ""),
        "execution_time_ms": exec_result.get("execution_time_ms", 0.0),
        "status": exec_result.get("status", "")
    })


@method_decorator(login_required, name='dispatch')
class HRBehavioralListView(ListView):
    model = Question
    template_name = "interviews/behavioral_list.html"
    context_object_name = "questions"

    def get_queryset(self):
        category = QuestionCategory.objects.filter(slug='behavioral').first()
        if category:
            return Question.objects.filter(category=category, question_type='STAR')
        return Question.objects.filter(question_type='STAR')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_user_sidebar_context(self.request.user))
        completed_ids = set(
            UserAttemptDetail.objects.filter(
                attempt__user=self.request.user,
                question__question_type='STAR',
                is_correct=True
            ).values_list('question_id', flat=True)
        )
        context["completed_ids"] = completed_ids
        context["completed_question_ids"] = completed_ids
        context["completed_count"] = len(completed_ids)
        questions = context.get("questions", [])
        context["total_count"] = questions.count() if hasattr(questions, 'count') else len(questions)
        return context


@method_decorator(login_required, name='dispatch')
class HRBehavioralDetailView(DetailView):
    model = Question
    template_name = "interviews/behavioral_detail.html"
    context_object_name = "question"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_user_sidebar_context(self.request.user))
        context["attempts"] = UserAttemptDetail.objects.filter(
            attempt__user=self.request.user,
            question=self.object
        ).select_related('attempt').order_by('-attempt__attempted_at')[:5]
        return context


@login_required
def submit_star(request, pk):
    if request.method != 'POST':
        return redirect('interviews:hub')

    question = get_object_or_404(Question, pk=pk, question_type='STAR')
    situation = request.POST.get("situation", "").strip()
    task = request.POST.get("task", "").strip()
    action = request.POST.get("action", "").strip()
    result = request.POST.get("result", "").strip()

    # Evaluate via STAREvaluatorService
    eval_result = STAREvaluatorService.evaluate(situation, task, action, result)
    score = eval_result["score"]
    feedback = " ".join(eval_result["overall_feedback"])

    category = QuestionCategory.objects.filter(slug='behavioral').first()
    if not category:
        category, _ = QuestionCategory.objects.get_or_create(slug='behavioral', defaults={'name': 'HR & Behavioral'})

    attempt = UserAttempt.objects.create(
        user=request.user,
        category=category,
        score=score,
        proctor_violations_count=0
    )

    combined_answer = json.dumps({
        "Situation": situation,
        "Task": task,
        "Action": action,
        "Result": result
    })

    UserAttemptDetail.objects.create(
        attempt=attempt,
        question=question,
        user_answer=combined_answer,
        is_correct=(score >= 75)
    )

    if score >= 75:
        CompetencyEvidenceService.record_star_evidence(request.user, question, score)

    context = {
        "question": question,
        "score": score,
        "feedback": feedback,
        "attempt": attempt,
        "star_sections": eval_result.get("sections", {})
    }
    context.update(get_user_sidebar_context(request.user))
    return render(request, "interviews/star_result.html", context)


@method_decorator(login_required, name='dispatch')
class MockInterviewListView(ListView):
    model = MockInterviewSession
    template_name = "interviews/mock_list.html"
    context_object_name = "sessions"

    def get_queryset(self):
        return MockInterviewSession.objects.filter(user=self.request.user).order_by('-started_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_user_sidebar_context(self.request.user))
        profile = context.get('profile')
        suggested_role = ""
        if profile and profile.career_goal:
            suggested_role = profile.career_goal.strip()
        context["suggested_role"] = suggested_role
        context["default_roles"] = [
            "Software Developer",
            "Frontend Developer",
            "Backend Developer",
            "Data Scientist",
            "ML Engineer",
            "DevOps Engineer"
        ]
        return context


@login_required
def start_mock(request):
    if request.method == 'POST':
        role = request.POST.get("role", "").strip()
        if not role:
            profile = getattr(request.user, 'studentprofile', None)
            if profile and profile.career_goal:
                role = profile.career_goal.strip()
            else:
                role = "Software Developer"

        session = MockInterviewSession.objects.create(
            user=request.user,
            role=role,
            current_phase='INTRODUCTION',
            current_turn=0
        )

        initial_msg = MockInterviewEngine.get_initial_greeting(role)
        MockInterviewChat.objects.create(
            session=session,
            sender='Interviewer',
            message=initial_msg,
            phase='INTRODUCTION'
        )
        return redirect('interviews:mock_session', pk=session.id)
    return redirect('interviews:mock_list')


@login_required
def mock_session(request, pk):
    session = get_object_or_404(MockInterviewSession, pk=pk, user=request.user)
    if session.is_completed:
        return redirect('interviews:mock_report', pk=session.id)
    context = {"session": session}
    context.update(get_user_sidebar_context(request.user))
    return render(request, "interviews/mock_session.html", context)


@login_required
def chat_reply(request, pk):
    if request.method != 'POST':
        return JsonResponse({"error": "POST method required"}, status=405)

    session = get_object_or_404(MockInterviewSession, pk=pk, user=request.user)
    if session.is_completed:
        return JsonResponse({
            "completed": True,
            "message": "Session already completed.",
            "redirect_url": reverse('interviews:mock_report', args=[session.id])
        })

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)

    candidate_msg = data.get("message", "").strip()
    try:
        violations = int(data.get("proctor_violations", 0))
    except (ValueError, TypeError):
        violations = 0

    if not candidate_msg:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)

    # Process turn via MockInterviewEngine state machine
    result = MockInterviewEngine.process_candidate_turn(
        session=session,
        candidate_msg=candidate_msg,
        proctor_violations_count=violations
    )

    if "error" in result:
        return JsonResponse({"error": result["error"]}, status=400)

    return JsonResponse({
        "message": result["message"],
        "completed": result["completed"],
        "phase": result.get("phase", ""),
        "turn": result.get("turn", 0),
        "redirect_url": reverse('interviews:mock_report', args=[session.id]) if result.get("completed") else ""
    })


@login_required
def mock_report(request, pk):
    session = get_object_or_404(MockInterviewSession, pk=pk, user=request.user)
    if not session.is_completed:
        return redirect('interviews:mock_session', pk=session.id)

    candidate_chats = list(MockInterviewChat.objects.filter(session=session, sender='Candidate'))
    total_len = sum(len(c.message) for c in candidate_chats)

    # Retrieve dimension breakdown
    dims = session.dimension_scores or {}
    comm_pct = dims.get('communication', {}).get('percentage', 50)
    keyword_pct = dims.get('technical_depth', {}).get('percentage', 50)

    # Recognized keywords
    all_text = " ".join(c.message.lower() for c in candidate_chats)
    track_key = MockInterviewEngine.match_role_track(session.role)
    track_keywords = ROLE_QUESTION_BANKS.get(track_key, {}).get('keywords', set())
    matched_words = [kw for kw in track_keywords if kw in all_text]

    # Audit proctoring report (does not dock score)
    integrity_report = ProctorAuditService.get_session_integrity_report(request.user, 'MockInterview', session.id)
    proctor_pct = 100 if session.proctor_violations_count == 0 else max(100 - (session.proctor_violations_count * 10), 40)

    context = {
        "session": session,
        "total_len": total_len,
        "comm_pct": comm_pct,
        "keyword_pct": keyword_pct,
        "matched_words": matched_words,
        "proctor_pct": proctor_pct,
        "candidate_chats_count": len(candidate_chats),
        "integrity_report": integrity_report,
        "dimension_scores": dims
    }
    context.update(get_user_sidebar_context(request.user))
    return render(request, "interviews/mock_report.html", context)


@login_required
def log_proctor_violation(request):
    if request.method != 'POST':
        return JsonResponse({"error": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    session_type = data.get("session_type")
    session_id = data.get("session_id")
    violation_type = data.get("violation_type")

    success, msg = ProctorAuditService.record_violation(
        user=request.user,
        session_type=session_type,
        session_id=session_id,
        violation_type=violation_type,
        source='CLIENT_REPORTED'
    )

    if not success:
        return JsonResponse({"error": msg}, status=400 if "Invalid" in msg else 429)

    return JsonResponse({"success": True, "message": msg})


@method_decorator(login_required, name='dispatch')
class PerformanceReportView(TemplateView):
    template_name = "interviews/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(get_user_sidebar_context(user))

        # Query optimization with select_related
        context["attempts"] = UserAttempt.objects.filter(user=user).select_related('category').order_by('-attempted_at')
        context["mocks"] = MockInterviewSession.objects.filter(user=user, is_completed=True).order_by('-started_at')
        violations_qs = ProctorLog.objects.filter(user=user).order_by('-timestamp')
        context["violations"] = violations_qs
        context["proctor_logs"] = violations_qs
        context["evidence"] = InterviewCompetencyEvidence.objects.filter(user=user).order_by('-created_at')

        return context
