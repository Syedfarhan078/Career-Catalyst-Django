from django.db import models
from django.conf import settings
from apps.resume.models import Resume

class ResumeAnalysis(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='analyses')
    resume = models.ForeignKey(Resume, on_delete=models.SET_NULL, null=True, blank=True, related_name='analyses')
    uploaded_file = models.FileField(upload_to='resumes/', null=True, blank=True)
    raw_text = models.TextField(blank=True)
    target_role = models.CharField(max_length=150)
    job_description = models.TextField(blank=True)
    
    # 5 Explainable ATS Metrics (0 - 100)
    jd_match_score = models.IntegerField(default=0)          # TF-IDF Cosine Similarity against JD/Role
    skill_coverage_score = models.IntegerField(default=0)    # Required vs matched canonical taxonomy skills
    keyword_coverage_score = models.IntegerField(default=0)  # Core domain vocabulary presence
    completeness_score = models.IntegerField(default=0)      # Section completeness & contact formatting
    achievement_score = models.IntegerField(default=0)       # Google XYZ impact formula & metric presence
    
    # Composite / Legacy fields for backwards compatibility
    overall_score = models.IntegerField(default=0)
    ats_score = models.IntegerField(default=0)
    grammar_score = models.IntegerField(default=0)
    keyword_score = models.IntegerField(default=0)
    skill_score = models.IntegerField(default=0)
    
    # Structured Data & AI Cache
    structured_data = models.JSONField(default=dict, blank=True)
    pii_summary = models.JSONField(default=dict, blank=True)
    ai_enhanced = models.BooleanField(default=False)
    ai_feedback = models.JSONField(default=dict, blank=True)
    
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
        ('Impact', 'Impact'),
    ]
    analysis = models.ForeignKey(ResumeAnalysis, on_delete=models.CASCADE, related_name='suggestions')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Content')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    description = models.TextField()

    def __str__(self):
        return f"{self.category} - {self.priority}"
