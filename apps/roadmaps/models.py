from django.db import models
from django.conf import settings
from django.utils import timezone


class CareerPath(models.Model):
    DIFFICULTY_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=50, default='bi-briefcase', help_text='Bootstrap Icon class')
    estimated_weeks = models.IntegerField(default=12)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Beginner')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def total_topics(self):
        return Topic.objects.filter(milestone__career_path=self).count()


class Milestone(models.Model):
    LEVEL_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]
    career_path = models.ForeignKey(CareerPath, on_delete=models.CASCADE, related_name='milestones')
    week_number = models.IntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='Beginner')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'week_number']
        unique_together = ['career_path', 'week_number']

    def __str__(self):
        return f"Week {self.week_number}: {self.title}"


class Topic(models.Model):
    RESOURCE_TYPE_CHOICES = [
        ('Video', 'Video'),
        ('Article', 'Article'),
        ('Course', 'Course'),
        ('Documentation', 'Documentation'),
    ]
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    resource_url = models.URLField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES, default='Article')
    estimated_hours = models.DecimalField(max_digits=4, decimal_places=1, default=2.0)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class UserRoadmap(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='roadmaps')
    career_path = models.ForeignKey(CareerPath, on_delete=models.CASCADE, related_name='enrollments')
    started_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'career_path']

    def __str__(self):
        return f"{self.user.username} → {self.career_path.name}"

    def progress_percentage(self):
        total = Topic.objects.filter(milestone__career_path=self.career_path).count()
        if total == 0:
            return 0
        completed = self.topic_progress.filter(is_completed=True).count()
        return int((completed / total) * 100)

    def completed_count(self):
        return self.topic_progress.filter(is_completed=True).count()


class TopicProgress(models.Model):
    user_roadmap = models.ForeignKey(UserRoadmap, on_delete=models.CASCADE, related_name='topic_progress')
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='progress')
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user_roadmap', 'topic']

    def __str__(self):
        status = "✓" if self.is_completed else "□"
        return f"{status} {self.topic.title}"
