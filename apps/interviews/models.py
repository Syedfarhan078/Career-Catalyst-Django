from django.db import models
from django.conf import settings

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
    test_cases = models.JSONField(null=True, blank=True, help_text="List of test cases: [{'input': 'arg1, arg2', 'expected': 'output'}]")
    sample_solution = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"[{self.get_question_type_display()}] {self.title}"

class UserAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    category = models.ForeignKey(QuestionCategory, on_delete=models.CASCADE, related_name='attempts')
    score = models.IntegerField(default=0)
    attempted_at = models.DateTimeField(auto_now_add=True)
    proctor_violations_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.category.name} ({self.score}%)"

class UserAttemptDetail(models.Model):
    attempt = models.ForeignKey(UserAttempt, on_delete=models.CASCADE, related_name='details')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user_answer = models.TextField()
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.attempt} - {self.question.title}"

class MockInterviewSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mock_interviews')
    role = models.CharField(max_length=100)
    started_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    overall_score = models.IntegerField(default=0)
    feedback = models.TextField(blank=True)
    proctor_violations_count = models.IntegerField(default=0)

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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='proctor_logs')
    session_type = models.CharField(max_length=15, choices=SESSION_CHOICES)
    session_id = models.IntegerField()
    violation_type = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.session_type} ({self.violation_type})"
