from django.db import models
from django.conf import settings
from apps.resume.models import Resume

class ResumeAnalysis(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='analyses')
    resume = models.ForeignKey(Resume, on_delete=models.SET_NULL, null=True, blank=True, related_name='analyses')
    uploaded_file = models.FileField(upload_to='resumes/', null=True, blank=True)
    raw_text = models.TextField(blank=True)
    target_role = models.CharField(max_length=150)
    
    # Scores (0 - 100)
    overall_score = models.IntegerField(default=0)
    ats_score = models.IntegerField(default=0)
    grammar_score = models.IntegerField(default=0)  # We will map "Readability" to this to preserve schema
    keyword_score = models.IntegerField(default=0)
    skill_score = models.IntegerField(default=0)
    
    feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.target_role} ({self.overall_score}%)"

class MissingSkill(models.Model):
    IMPORTANCE_CHOICES = [
        ('High', 'High'),
        ('Medium', 'Medium'),
        ('Low', 'Low'),
    ]
    analysis = models.ForeignKey(ResumeAnalysis, on_delete=models.CASCADE, related_name='missing_skills')
    skill_name = models.CharField(max_length=100)
    importance = models.CharField(max_length=10, choices=IMPORTANCE_CHOICES, default='Medium')
    recommendation = models.TextField()

    def __str__(self):
        return f"{self.skill_name} ({self.importance})"

class ImprovementSuggestion(models.Model):
    PRIORITY_CHOICES = [
        ('High', 'High'),
        ('Medium', 'Medium'),
        ('Low', 'Low'),
    ]
    CATEGORY_CHOICES = [
        ('Content', 'Content'),
        ('Projects', 'Projects'),
        ('Skills', 'Skills'),
        ('Experience', 'Experience'),
        ('Education', 'Education'),
    ]
    analysis = models.ForeignKey(ResumeAnalysis, on_delete=models.CASCADE, related_name='suggestions')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Content')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    description = models.TextField()

    def __str__(self):
        return f"{self.category} - {self.priority}"
