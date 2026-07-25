from django.db import models
from django.conf import settings

# --- FORUM & SHOWCASE MODELS ---

class ForumCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Forum Categories"

    def __str__(self):
        return self.name


class ForumThread(models.Model):
    category = models.ForeignKey(ForumCategory, on_delete=models.CASCADE, related_name='threads')
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_threads')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ForumReply(models.Model):
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, related_name='replies')
    content = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_replies')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name_plural = "Forum Replies"

    def __str__(self):
        return f"Reply by {self.author.username} on {self.thread.title}"


class SharedProject(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    github_link = models.URLField(blank=True)
    live_link = models.URLField(blank=True)
    tags = models.CharField(max_length=255, help_text="Comma-separated tag list")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shared_projects')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_tags_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class ProjectLike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey(SharedProject, on_delete=models.CASCADE, related_name='likes')
    liked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'project']

    def __str__(self):
        return f"{self.user.username} liked {self.project.title}"


class SuccessStory(models.Model):
    title = models.CharField(max_length=200)
    author_name = models.CharField(max_length=100)
    placed_role = models.CharField(max_length=150)
    placed_company = models.CharField(max_length=150)
    content = models.TextField()
    grad_year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Success Stories"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author_name} placed at {self.placed_company}"


class MentorMessage(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_mentor_messages')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_mentor_messages')
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"From {self.sender.username} to {self.recipient.username} - {self.content[:30]}"


# --- MENTOR MARKETPLACE MODELS ---

class MentorProfile(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Blocked', 'Blocked'),
    ]
    
    MENTORSHIP_TYPE_CHOICES = [
        ('Online', 'Online'),
        ('Offline', 'Offline'),
        ('Both', 'Both'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mentor_profile')
    profile_photo = models.ImageField(upload_to='mentor_photos/', blank=True, null=True)
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    company = models.CharField(max_length=150)
    designation = models.CharField(max_length=150)
    experience_years = models.IntegerField(default=1)
    current_location = models.CharField(max_length=150)
    bio = models.TextField(blank=True)
    
    # Stored as comma-separated lists for quick queries, with child skill/availability models for structural relationships
    career_domains = models.CharField(max_length=255, help_text="Comma-separated domains e.g. Frontend, Backend, Data Science")
    skills = models.TextField(help_text="Comma-separated list of skills")
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    resume = models.FileField(upload_to='mentor_resumes/', blank=True, null=True)
    languages = models.CharField(max_length=255, help_text="Comma-separated list of languages known")
    
    available_days = models.CharField(max_length=255, help_text="Comma-separated days e.g. Monday, Wednesday, Friday")
    available_time_slots = models.CharField(max_length=255, help_text="Comma-separated time ranges e.g. 10:00 AM - 12:00 PM")
    max_sessions_per_week = models.IntegerField(default=5)
    mentorship_type = models.CharField(max_length=20, choices=MENTORSHIP_TYPE_CHOICES, default='Online')
    
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_reviews = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.company})"

    def get_skills_list(self):
        if not self.skills:
            return []
        return [s.strip() for s in self.skills.split(",") if s.strip()]

    def get_domains_list(self):
        if not self.career_domains:
            return []
        return [d.strip() for d in self.career_domains.split(",") if d.strip()]

    def get_languages_list(self):
        if not self.languages:
            return []
        return [l.strip() for l in self.languages.split(",") if l.strip()]

    def get_days_list(self):
        if not self.available_days:
            return []
        return [d.strip() for d in self.available_days.split(",") if d.strip()]


class MentorSkill(models.Model):
    mentor = models.ForeignKey(MentorProfile, on_delete=models.CASCADE, related_name='mentor_skills')
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} - {self.mentor.full_name}"


class MentorshipRequest(models.Model):
    PURPOSE_CHOICES = [
        ('Resume Review', 'Resume Review'),
        ('Career Guidance', 'Career Guidance'),
        ('Interview Preparation', 'Interview Preparation'),
        ('Roadmap Discussion', 'Roadmap Discussion'),
        ('Project Review', 'Project Review'),
    ]

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_requests')
    mentor = models.ForeignKey(MentorProfile, on_delete=models.CASCADE, related_name='mentor_requests')
    
    requested_date = models.DateField()
    requested_time = models.TimeField()
    purpose = models.CharField(max_length=50, choices=PURPOSE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    
    student_message = models.TextField()
    mentor_response = models.TextField(blank=True)
    
    meeting_link = models.URLField(blank=True)
    meeting_date = models.DateField(blank=True, null=True)
    meeting_time = models.TimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Request from {self.student.username} to {self.mentor.full_name} - {self.status}"


class MentorReview(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    mentor = models.ForeignKey(MentorProfile, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review ({self.rating}/5) for {self.mentor.full_name} by {self.student.username}"


class MentorAvailability(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    mentor = models.ForeignKey(MentorProfile, on_delete=models.CASCADE, related_name='availabilities')
    day = models.CharField(max_length=20, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_sessions = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.day}: {self.start_time} - {self.end_time} ({self.mentor.full_name})"
