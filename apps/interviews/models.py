import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class QuestionCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Question Categories"

    def __str__(self):
        return self.name


class Question(models.Model):
    TYPE_CHOICES = [
        ('MCQ', 'Multiple Choice'),
        ('Coding', 'Coding Challenge'),
        ('STAR', 'STAR/Behavioral'),
    ]
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]
    category = models.ForeignKey(QuestionCategory, on_delete=models.CASCADE, related_name='questions')
    title = models.CharField(max_length=255)
    content = models.TextField()
    question_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='MCQ')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='Medium')
    
    # MCQ fields
    options = models.JSONField(null=True, blank=True, help_text="List of choices: ['Option A', 'Option B', ...]")
    correct_option = models.CharField(max_length=10, null=True, blank=True, help_text="e.g. A, B, C, or D")
    
    # Coding fields
    starter_code = models.TextField(blank=True, default='', help_text="Initial starter template code for candidates.")
    entry_point = models.CharField(max_length=100, blank=True, default='', help_text="Primary function name to evaluate.")
    test_cases = models.JSONField(null=True, blank=True, help_text="List of public test cases: [{'input': '...', 'expected': '...', 'function': '...'}]")
    hidden_test_cases = models.JSONField(null=True, blank=True, default=list, help_text="List of hidden test cases evaluated only on submission.")
    time_limit_ms = models.IntegerField(default=2000, help_text="Execution time limit in milliseconds.")
    memory_limit_mb = models.IntegerField(default=128, help_text="Memory limit in megabytes.")
    sample_solution = models.TextField(null=True, blank=True)
    skills_evaluated = models.CharField(max_length=255, blank=True, default='', help_text="Comma-separated competencies tested by this question.")

    class Meta:
        indexes = [
            models.Index(fields=['category', 'question_type', 'difficulty']),
            models.Index(fields=['question_type', 'difficulty']),
        ]

    def __str__(self):
        return f"[{self.get_question_type_display()}] {self.title}"


class UserAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    category = models.ForeignKey(QuestionCategory, on_delete=models.CASCADE, related_name='attempts')
    score = models.IntegerField(default=0)
    attempted_at = models.DateTimeField(auto_now_add=True)
    proctor_violations_count = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'attempted_at']),
            models.Index(fields=['category', 'attempted_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.category.name} ({self.score}%)"


class UserAttemptDetail(models.Model):
    attempt = models.ForeignKey(UserAttempt, on_delete=models.CASCADE, related_name='details')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user_answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    
    # Enhanced execution and evaluation telemetry
    execution_time_ms = models.FloatField(null=True, blank=True)
    memory_used_kb = models.FloatField(null=True, blank=True)
    passed_tests = models.IntegerField(null=True, blank=True)
    total_tests = models.IntegerField(null=True, blank=True)
    test_results = models.JSONField(default=dict, blank=True)
    execution_status = models.CharField(max_length=50, blank=True, default='')

    def __str__(self):
        return f"{self.attempt} - {self.question.title}"


class QuizSession(models.Model):
    """
    Persistent server-managed quiz attempt state.
    Provides anti-clash multi-tab isolation, server-side countdown timestamps,
    and idempotent atomic submissions.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_sessions')
    category = models.ForeignKey(QuestionCategory, on_delete=models.CASCADE, related_name='quiz_sessions')
    session_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_submitted = models.BooleanField(default=False)
    score = models.IntegerField(null=True, blank=True)
    question_ids = models.JSONField(default=list, help_text="Ordered list of question IDs selected for this quiz session.")
    proctor_violations_count = models.IntegerField(default=0)
    attempt = models.OneToOneField(UserAttempt, null=True, blank=True, on_delete=models.SET_NULL, related_name='quiz_session')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_submitted']),
            models.Index(fields=['session_uuid']),
            models.Index(fields=['user', 'category', 'is_submitted']),
        ]

    def __str__(self):
        status = "Submitted" if self.is_submitted else "Active"
        return f"QuizSession({self.user.username}, {self.category.slug}, {status})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def remaining_seconds(self) -> int:
        if self.is_submitted:
            return 0
        rem = int((self.expires_at - timezone.now()).total_seconds())
        return max(0, rem)


class MockInterviewSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mock_interviews')
    role = models.CharField(max_length=100)
    career_path = models.ForeignKey('roadmaps.CareerPath', null=True, blank=True, on_delete=models.SET_NULL, related_name='mock_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    overall_score = models.IntegerField(default=0)
    feedback = models.TextField(blank=True)
    proctor_violations_count = models.IntegerField(default=0)
    
    # State machine and rubric telemetry
    current_phase = models.CharField(max_length=30, default='INTRODUCTION')
    current_turn = models.IntegerField(default=0)
    dimension_scores = models.JSONField(default=dict, blank=True, help_text="Scores across technical, problem solving, role relevance, communication, structure")

    class Meta:
        indexes = [
            models.Index(fields=['user', 'started_at']),
            models.Index(fields=['user', 'is_completed']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role} ({self.overall_score}%)"


class MockInterviewChat(models.Model):
    SENDER_CHOICES = [
        ('Interviewer', 'Interviewer'),
        ('Candidate', 'Candidate'),
    ]
    session = models.ForeignKey(MockInterviewSession, on_delete=models.CASCADE, related_name='chats')
    sender = models.CharField(max_length=15, choices=SENDER_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    phase = models.CharField(max_length=30, blank=True, default='')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender}: {self.message[:30]}"


class ProctorLog(models.Model):
    SESSION_CHOICES = [
        ('Quiz', 'Quiz'),
        ('MockInterview', 'MockInterview'),
        ('Coding', 'Coding'),
    ]
    SOURCE_CHOICES = [
        ('CLIENT_REPORTED', 'Client Reported'),
        ('SERVER_VERIFIED', 'Server Verified'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='proctor_logs')
    session_type = models.CharField(max_length=15, choices=SESSION_CHOICES)
    session_id = models.IntegerField(db_index=True)
    violation_type = models.CharField(max_length=100)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='CLIENT_REPORTED')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['session_type', 'session_id']),
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.session_type} ({self.violation_type})"


class InterviewCompetencyEvidence(models.Model):
    """
    Evidence record for skills demonstrated through interview preparation.
    Bridges interview performance cautiously into CareerCatalyst's learning loop.
    """
    SOURCE_CHOICES = [
        ('CODING_CHALLENGE', 'Coding Challenge'),
        ('TECHNICAL_QUIZ', 'Technical Quiz'),
        ('MOCK_INTERVIEW', 'Mock Interview'),
        ('BEHAVIORAL_STAR', 'Behavioral STAR'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interview_evidence')
    skill_name = models.CharField(max_length=100, db_index=True)
    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    score = models.IntegerField()
    confidence_weight = models.FloatField(default=1.0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'skill_name']),
            models.Index(fields=['user', 'created_at']),
        ]
        verbose_name_plural = "Interview Competency Evidence"

    def __str__(self):
        return f"{self.user.username} - {self.skill_name} ({self.score}%)"
