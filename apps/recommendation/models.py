from django.db import models
from django.conf import settings

class CareerAnalysis(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='career_analyses'
    )
    
    # Career metrics
    career_readiness_score = models.IntegerField(default=0)
    recommended_career = models.CharField(max_length=255)
    confidence_score = models.IntegerField(default=0)
    overall_feedback = models.TextField()
    
    # Arrays stored as JSONField
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    missing_skills = models.JSONField(default=list, blank=True)
    recommended_certifications = models.JSONField(default=list, blank=True)
    recommended_projects = models.JSONField(default=list, blank=True)
    interview_topics = models.JSONField(default=list, blank=True)
    
    # JSON structures
    roadmap_json = models.JSONField(default=list, blank=True, help_text="Weekly roadmap details")
    learning_resources_json = models.JSONField(default=list, blank=True, help_text="List of learning resources")
    
    # Resume & Placement metrics
    ats_resume_score = models.IntegerField(default=0)
    resume_suggestions = models.JSONField(default=list, blank=True)
    internship_readiness = models.CharField(max_length=100, default="Not Ready")
    placement_readiness = models.CharField(max_length=100, default="Not Ready")
    
    # Execution plans
    thirty_day_plan = models.JSONField(default=list, blank=True)
    ninety_day_plan = models.JSONField(default=list, blank=True)
    
    motivational_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Career Analyses"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.recommended_career} ({self.career_readiness_score}%)"
