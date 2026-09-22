from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.db.models import Avg, Count
from django.urls import reverse
import json

from .models import (
    QuestionCategory, Question, UserAttempt, UserAttemptDetail,
    MockInterviewSession, MockInterviewChat, ProctorLog
)
from .runner import run_code


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

        # Aggregate user stats (real numbers only)
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

        # Recent activity (safe query optimization with select_related)
        context["recent_attempts"] = attempts.select_related('category').order_by('-attempted_at')[:4]
        context["recent_mocks"] = mocks.order_by('-started_at')[:3]

        return context


@login_required
def start_quiz(request, slug):
    category = get_object_or_404(QuestionCategory, slug=slug)
    # Get 5 random MCQs from this category
    questions = Question.objects.filter(category=category, question_type='MCQ').order_by('?')[:5]
    
    if not questions.exists():
        # If no MCQs (like coding or behavioral categories), redirect
        if category.slug == 'coding':
            return redirect('interviews:coding_list')
        elif category.slug == 'behavioral':
            return redirect('interviews:behavioral_list')
        return redirect('interviews:hub')

    # Store question IDs in session so they don't change on refresh
    request.session['quiz_question_ids'] = [q.id for q in questions]
    request.session['quiz_category_id'] = category.id
    
    context = {
        "category": category,
        "questions": questions,
    }
    context.update(get_user_sidebar_context(request.user))
    return render(request, "interviews/quiz.html", context)


@login_required
def submit_quiz(request):
    if request.method != 'POST':
        return redirect('interviews:hub')

    category_id = request.session.get('quiz_category_id')
    question_ids = request.session.get('quiz_question_ids')
    violations = int(request.POST.get('proctor_violations', 0))

    if not category_id or not question_ids:
        return redirect('interviews:hub')

    category = get_object_or_404(QuestionCategory, pk=category_id)
    questions = Question.objects.filter(pk__in=question_ids)

    # Calculate score
    correct_count = 0
    total_questions = len(question_ids)
    details_to_create = []

    # Create the attempt first
    attempt = UserAttempt.objects.create(
        user=request.user,
        category=category,
        proctor_violations_count=violations
    )

    for q in questions:
        user_ans = request.POST.get(f"question_{q.id}", "").strip()
        is_correct = (user_ans == q.correct_option)
        if is_correct:
            correct_count += 1
            
        details_to_create.append(
            UserAttemptDetail(
                attempt=attempt,
                question=q,
                user_answer=user_ans,
                is_correct=is_correct
            )
        )

    UserAttemptDetail.objects.bulk_create(details_to_create)

    # Update score
    attempt.score = int((correct_count / total_questions) * 100) if total_questions > 0 else 0
    attempt.save()

    # Clear session keys
    request.session.pop('quiz_category_id', None)
    request.session.pop('quiz_question_ids', None)

    context = {
        "attempt": attempt,
        "category": category,
        "correct_count": correct_count,
        "total": total_questions,
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
        # Solved challenge IDs for visual checkmark
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
        # Fetch past attempts for this coding challenge with select_related to fix N+1
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
        data = {}
        
    code = data.get("code", "")
    violations = int(data.get("proctor_violations", 0))

    if not code.strip():
        return JsonResponse({"success": False, "error": "Code cannot be empty."})

    # Run the code via sandbox runner
    result = run_code(code, question.test_cases)

    # Save attempt
    category = QuestionCategory.objects.filter(slug='coding').first()
    if not category:
        category, _ = QuestionCategory.objects.get_or_create(slug='coding', defaults={'name': 'Coding Challenges'})

    attempt = UserAttempt.objects.create(
        user=request.user,
        category=category,
        score=100 if result.get("success", False) else 0,
        proctor_violations_count=violations
    )
    UserAttemptDetail.objects.create(
        attempt=attempt,
        question=question,
        user_answer=code,
        is_correct=result.get("success", False)
    )

    return JsonResponse({
        "success": result.get("success", False),
        "results": result.get("results", []),
        "error": result.get("error", "")
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
        # Fetch past attempts with select_related to fix N+1
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

    # Grading algorithm: 25% weight for each STAR section completed with >= 40 chars
    score = 0
    feedback_parts = []

    if len(situation) >= 40:
        score += 25
    else:
        feedback_parts.append("Flesh out the 'Situation' block with more context on the conflict/role.")
        
    if len(task) >= 40:
        score += 25
    else:
        feedback_parts.append("Add more details to the 'Task' block regarding target deliverables.")
        
    if len(action) >= 40:
        score += 25
    else:
        feedback_parts.append("Expand the 'Action' block to specify what communication or technical steps you took.")
        
    if len(result) >= 40:
        score += 25
    else:
        feedback_parts.append("Enhance the 'Result' block by demonstrating measurable impact and lessons learned.")

    if score == 100:
        feedback = "Excellent! You followed the STAR structure perfectly with deep descriptive answers."
    else:
        feedback = "STAR Structure feedback: " + " ".join(feedback_parts)

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

    context = {
        "question": question,
        "score": score,
        "feedback": feedback,
        "attempt": attempt,
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
        
        # Suggested role derived from StudentProfile.career_goal where available
        profile = context.get('profile')
        suggested_role = ""
        if profile and profile.career_goal:
            suggested_role = profile.career_goal.strip()
        context["suggested_role"] = suggested_role
        
        # Standard role choices
        context["default_roles"] = [
            "Software Developer",
            "Data Scientist",
            "ML Engineer",
            "DevOps Engineer",
            "Product Manager"
        ]
        return context


@login_required
def start_mock(request):
    if request.method == 'POST':
        role = request.POST.get("role", "").strip()
        if not role:
            # Fall back to student profile career_goal if present, otherwise default
            profile = getattr(request.user, 'studentprofile', None)
            if profile and profile.career_goal:
                role = profile.career_goal.strip()
            else:
                role = "Software Developer"
            
        session = MockInterviewSession.objects.create(
            user=request.user,
            role=role
        )
        
        # Interviewer's opening prompt
        initial_msg = (
            f"Hello! Welcome to your simulated technical interview for the {role} role. "
            f"Let's begin. Can you start by introducing yourself, walking me through your background, "
            f"and mentioning your key tech stack?"
        )
        MockInterviewChat.objects.create(
            session=session,
            sender='Interviewer',
            message=initial_msg
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
        return JsonResponse({"completed": True})

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    candidate_msg = data.get("message", "").strip()
    violations = int(data.get("proctor_violations", 0))

    if not candidate_msg:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)

    # Update violations count on session if increased
    if violations > session.proctor_violations_count:
        session.proctor_violations_count = violations
        session.save(update_fields=['proctor_violations_count'])

    # Save Candidate message
    MockInterviewChat.objects.create(
        session=session,
        sender='Candidate',
        message=candidate_msg
    )

    # Fetch candidate replies once to prevent duplicate queries
    candidate_chats = list(MockInterviewChat.objects.filter(session=session, sender='Candidate'))
    replies = len(candidate_chats)

    # Interviewer Dynamic Dialog System
    # Stage 1: Candidate intro -> Ask Technical scenario
    # Stage 2: Candidate tech scenario -> Ask STAR conflict/project
    # Stage 3: Candidate conflict -> End & Evaluate
    interviewer_msg = ""
    is_done = False

    role_lower = session.role.lower()

    if replies == 1:
        if "data" in role_lower or "science" in role_lower or "ml" in role_lower:
            interviewer_msg = "Excellent. In data science, managing noisy datasets is a common challenge. Can you explain how you handle missing values, anomalies, and feature scaling in your typical preprocessing pipeline?"
        else:
            interviewer_msg = "Great intro. Let's move to a technical design scenario. How would you design a scalable notification system that pushes alerts to millions of users globally in real-time, and what database/caching layer would you choose?"
    elif replies == 2:
        interviewer_msg = "Understood, nice structural reasoning. Let's pivot to team dynamics. Tell me about a time you faced a heavy technical disagreement or conflict within a project group. How did you resolve it, and what did you learn?"
    else:
        is_done = True
        interviewer_msg = "Thank you! That concludes our mock interview. I will now analyze your communication metrics, answer structure, and keyword completeness to prepare your scorecard."

    # Save Interviewer reply
    MockInterviewChat.objects.create(
        session=session,
        sender='Interviewer',
        message=interviewer_msg
    )

    if is_done:
        # Grade session local deterministic rules
        total_score = 0
        feedback_notes = []

        # Rule 1: Check total answer lengths (max 40 pts)
        total_len = sum(len(c.message) for c in candidate_chats)
        if total_len > 600:
            total_score += 40
            feedback_notes.append("Excellent communication volume and detail levels.")
        elif total_len > 300:
            total_score += 25
            feedback_notes.append("Satisfactory answer length, but try providing more descriptive examples.")
        else:
            total_score += 10
            feedback_notes.append("Your answers were too short. Elaborate with projects and specific actions next time.")

        # Rule 2: Keyword match for role (max 40 pts)
        keywords = ["django", "python", "sql", "cache", "redis", "postgres", "star", "result", "team", "model", "scikit", "pandas", "numpy", "git", "scale", "index", "design"]
        matched_words = []
        for chat in candidate_chats:
            text = chat.message.lower()
            for kw in keywords:
                if kw in text and kw not in matched_words:
                    matched_words.append(kw)
        
        keyword_score = min(len(matched_words) * 6, 40)
        total_score += keyword_score
        
        if len(matched_words) >= 5:
            feedback_notes.append(f"Strong industry jargon keyword presence: {', '.join(matched_words)}.")
        else:
            feedback_notes.append("Consider integrating more technical terms and tool names in your responses.")

        # Rule 3: Proctor violation penalty (max 20 pt impact)
        proctor_penalty = min(session.proctor_violations_count * 10, 20)
        total_score = max(total_score + (20 - proctor_penalty), 0)
        
        if proctor_penalty > 0:
            feedback_notes.append(f"Penalized {proctor_penalty} points due to focus/fullscreen switches detected by proctoring.")

        session.is_completed = True
        session.overall_score = min(total_score, 100)
        session.feedback = " ".join(feedback_notes)
        session.save()

    return JsonResponse({
        "message": interviewer_msg,
        "completed": is_done,
        "redirect_url": reverse('interviews:mock_report', args=[session.id]) if is_done else ""
    })


@login_required
def mock_report(request, pk):
    session = get_object_or_404(MockInterviewSession, pk=pk, user=request.user)
    if not session.is_completed:
        return redirect('interviews:mock_session', pk=session.id)

    # Compute actual breakdown scores directly from session data (no fake numbers, no broken multiply filter)
    candidate_chats = list(MockInterviewChat.objects.filter(session=session, sender='Candidate'))
    total_len = sum(len(c.message) for c in candidate_chats)
    
    # 1. Communication volume (max 40 pts -> percentage of 40)
    if total_len > 600:
        comm_pts = 40
    elif total_len > 300:
        comm_pts = 25
    else:
        comm_pts = 10
    comm_pct = int(round((comm_pts / 40) * 100))

    # 2. Keywords presence (max 40 pts -> percentage of 40)
    keywords = ["django", "python", "sql", "cache", "redis", "postgres", "star", "result", "team", "model", "scikit", "pandas", "numpy", "git", "scale", "index", "design"]
    matched_words = []
    for chat in candidate_chats:
        text = chat.message.lower()
        for kw in keywords:
            if kw in text and kw not in matched_words:
                matched_words.append(kw)
    keyword_pts = min(len(matched_words) * 6, 40)
    keyword_pct = int(round((keyword_pts / 40) * 100))

    # 3. Proctor score (base 20 pts minus penalty -> percentage of 20)
    proctor_penalty = min(session.proctor_violations_count * 10, 20)
    proctor_pts = max(20 - proctor_penalty, 0)
    proctor_pct = int(round((proctor_pts / 20) * 100))

    context = {
        "session": session,
        "total_len": total_len,
        "comm_pct": comm_pct,
        "keyword_pct": keyword_pct,
        "matched_words": matched_words,
        "proctor_pct": proctor_pct,
        "candidate_chats_count": len(candidate_chats),
    }
    context.update(get_user_sidebar_context(request.user))
    return render(request, "interviews/mock_report.html", context)


@login_required
def log_proctor_violation(request):
    if request.method != 'POST':
        return JsonResponse({"error": "POST method required"}, status=405)
    
    try:
        data = json.loads(request.body)
        session_type = data.get("session_type")
        session_id = data.get("session_id")
        violation_type = data.get("violation_type")
        
        if not session_type or not session_id or not violation_type:
            return JsonResponse({"error": "Missing params"}, status=400)
            
        ProctorLog.objects.create(
            user=request.user,
            session_type=session_type,
            session_id=session_id,
            violation_type=violation_type
        )
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@method_decorator(login_required, name='dispatch')
class PerformanceReportView(TemplateView):
    template_name = "interviews/reports.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(get_user_sidebar_context(user))
        
        # Attempts history with select_related to fix N+1 on category
        context["attempts"] = UserAttempt.objects.filter(user=user).select_related('category').order_by('-attempted_at')
        # Mock interviews history
        context["mocks"] = MockInterviewSession.objects.filter(user=user, is_completed=True).order_by('-started_at')
        # Proctor violations history
        violations_qs = ProctorLog.objects.filter(user=user).order_by('-timestamp')
        context["violations"] = violations_qs
        context["proctor_logs"] = violations_qs
        
        return context
