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
    radar_chart_json = models.JSONField(default=list, blank=True, help_text="Dynamic radar chart categories and topic coverage")
    
    # Resume & Placement metrics
    has_resume = models.BooleanField(default=False)
    ats_resume_score = models.IntegerField(null=True, blank=True, default=None)
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

    @property
    def is_resume_uploaded(self):
        return bool(self.has_resume and self.ats_resume_score is not None and self.ats_resume_score > 0)

    def get_radar_labels(self):
        if self.radar_chart_json:
            return [item.get('name', '') for item in self.radar_chart_json]
        if self.roadmap_json:
            return [step.get('title', f"Milestone {step.get('week', '')}") for step in self.roadmap_json[:6]]
        return ['Milestone 1', 'Milestone 2', 'Milestone 3', 'Milestone 4', 'Milestone 5']

    def get_radar_user_scores(self):
        if self.radar_chart_json:
            return [item.get('user_score', 0) for item in self.radar_chart_json]
        if self.roadmap_json:
            scores = []
            for step in self.roadmap_json[:6]:
                topics = step.get('topics', [])
                matched = step.get('matched_topics', [])
                if topics:
                    scores.append(round((len(matched) / len(topics)) * 10, 1))
                else:
                    scores.append(0)
            return scores
        return [0, 0, 0, 0, 0]

    def get_radar_target_scores(self):
        if self.radar_chart_json:
            return [item.get('target_score', 10) for item in self.radar_chart_json]
        if self.roadmap_json:
            return [10 for _ in self.roadmap_json[:6]]
        return [10, 10, 10, 10, 10]
