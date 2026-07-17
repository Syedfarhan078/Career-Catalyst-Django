from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.db.models import Avg, Count
import json

from .models import QuestionCategory, Question, UserAttempt, UserAttemptDetail, MockInterviewSession, MockInterviewChat, ProctorLog
from .runner import run_code

@method_decorator(login_required, name='dispatch')
class InterviewHubView(TemplateView):
    template_name = "interviews/hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch categories
        categories = QuestionCategory.objects.all()
        context["categories"] = categories

        # Aggregate user stats
        attempts = UserAttempt.objects.filter(user=self.request.user)
        context["total_attempts"] = attempts.count()
        context["avg_score"] = attempts.aggregate(Avg('score'))['score__avg'] or 0

        mocks = MockInterviewSession.objects.filter(user=self.request.user, is_completed=True)
        context["total_mocks"] = mocks.count()
        context["avg_mock_score"] = mocks.aggregate(Avg('overall_score'))['overall_score__avg'] or 0

        context["total_violations"] = ProctorLog.objects.filter(user=self.request.user).count()
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
    
    # Initialize a temporary session attempt for proctoring logs
    # We will save this when they submit
    return render(request, "interviews/quiz.html", {
        "category": category,
        "questions": questions
    })

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

    # Log violations in ProctorLog
    if violations > 0:
        # Create a single summary proctor log or we let JS log them individually
        pass

    # Clear session keys
    del request.session['quiz_category_id']
    del request.session['quiz_question_ids']

    return render(request, "interviews/quiz_result.html", {
        "attempt": attempt,
        "correct_count": correct_count,
        "total": total_questions
    })

@method_decorator(login_required, name='dispatch')
class CodingListView(ListView):
    model = Question
    template_name = "interviews/coding_list.html"
    context_object_name = "challenges"

    def get_queryset(self):
        category = get_object_or_404(QuestionCategory, slug='coding')
        return Question.objects.filter(category=category, question_type='Coding')

@method_decorator(login_required, name='dispatch')
class CodingDetailView(DetailView):
    model = Question
    template_name = "interviews/coding_detail.html"
    context_object_name = "challenge"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch past attempts for this coding challenge
        context["attempts"] = UserAttemptDetail.objects.filter(
            attempt__user=self.request.user,
            question=self.object
        ).order_by('-attempt__attempted_at')
        return context

@login_required
def submit_code(request, pk):
    if request.method != 'POST':
        return JsonResponse({"error": "POST method required"}, status=405)

    question = get_object_or_404(Question, pk=pk, question_type='Coding')
    data = json.loads(request.body)
    code = data.get("code", "")
    violations = int(data.get("proctor_violations", 0))

    if not code.strip():
        return JsonResponse({"success": False, "error": "Code cannot be empty."})

    # Run the code
    result = run_code(code, question.test_cases)

    # Save attempt
    category = get_object_or_404(QuestionCategory, slug='coding')
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
        category = get_object_or_404(QuestionCategory, slug='behavioral')
        return Question.objects.filter(category=category, question_type='STAR')

@method_decorator(login_required, name='dispatch')
class HRBehavioralDetailView(DetailView):
    model = Question
    template_name = "interviews/behavioral_detail.html"
    context_object_name = "question"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["attempts"] = UserAttemptDetail.objects.filter(
            attempt__user=self.request.user,
            question=self.object
        ).order_by('-attempt__attempted_at')
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

    # Grading algorithm
    # 25% weight for each STAR category completed with > 40 chars
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

    category = get_object_or_404(QuestionCategory, slug='behavioral')
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

    return render(request, "interviews/star_result.html", {
        "question": question,
        "score": score,
        "feedback": feedback
    })

@method_decorator(login_required, name='dispatch')
class MockInterviewListView(ListView):
    model = MockInterviewSession
    template_name = "interviews/mock_list.html"
    context_object_name = "sessions"

    def get_queryset(self):
        return MockInterviewSession.objects.filter(user=self.request.user).order_by('-started_at')

@login_required
def start_mock(request):
    if request.method == 'POST':
        role = request.POST.get("role", "").strip()
        if not role:
            role = "Software Developer"
            
        session = MockInterviewSession.objects.create(
            user=request.user,
            role=role
        )
        
        # Interviewer's opening prompt
        initial_msg = f"Hello! Welcome to your simulated technical interview for the {role} role. Let's begin. Can you start by introducing yourself, walking me through your background, and mentioning your key tech stack?"
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
    return render(request, "interviews/mock_session.html", {"session": session})

@login_required
def chat_reply(request, pk):
    if request.method != 'POST':
        return JsonResponse({"error": "POST method required"}, status=405)

    session = get_object_or_404(MockInterviewSession, pk=pk, user=request.user)
    if session.is_completed:
        return JsonResponse({"completed": True})

    data = json.loads(request.body)
    candidate_msg = data.get("message", "").strip()
    violations = int(data.get("proctor_violations", 0))

    if not candidate_msg:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)

    # Update violations count on session
    if violations > session.proctor_violations_count:
        session.proctor_violations_count = violations
        session.save()

    # Save Candidate message
    MockInterviewChat.objects.create(
        session=session,
        sender='Candidate',
        message=candidate_msg
    )

    # Count current candidate replies to find interview stage
    replies = MockInterviewChat.objects.filter(session=session, sender='Candidate').count()

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
        # Grade session local rules
        chats = MockInterviewChat.objects.filter(session=session, sender='Candidate')
        total_score = 0
        feedback_notes = []

        # Rule 1: Check total answer lengths
        total_len = sum(len(c.message) for c in chats)
        if total_len > 600:
            total_score += 40
            feedback_notes.append("Excellent communication volume and detail levels.")
        elif total_len > 300:
            total_score += 25
            feedback_notes.append("Satisfactory answer length, but try providing more descriptive examples.")
        else:
            total_score += 10
            feedback_notes.append("Your answers were too short. Elaborate with projects and specific actions next time.")

        # Rule 2: Keyword match for role
        keywords = ["django", "python", "sql", "cache", "redis", "postgres", "star", "result", "team", "model", "scikit", "pandas", "numpy", "git", "scale", "index", "design"]
        matched_words = []
        for chat in chats:
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

        # Rule 3: Proctor violation penalty
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

from django.urls import reverse

@login_required
def mock_report(request, pk):
    session = get_object_or_404(MockInterviewSession, pk=pk, user=request.user)
    if not session.is_completed:
        return redirect('interviews:mock_session', pk=session.id)
    return render(request, "interviews/mock_report.html", {"session": session})

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
        
        # Attempts history
        context["attempts"] = UserAttempt.objects.filter(user=user).order_by('-attempted_at')
        # Mock interviews history
        context["mocks"] = MockInterviewSession.objects.filter(user=user, is_completed=True).order_by('-started_at')
        # Proctor violations history
        context["proctor_logs"] = ProctorLog.objects.filter(user=user).order_by('-timestamp')
        
        return context
