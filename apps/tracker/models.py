from django.db import models
from django.conf import settings
from django.utils import timezone


class JobApplication(models.Model):
    STATUS_CHOICES = [
        ('bookmarked', 'Bookmarked'),
        ('applied', 'Applied'),
        ('referral_requested', 'Referral Requested'),
        ('assessment', 'Online Assessment'),
        ('interview', 'Interviewing'),
        ('offer', 'Offer Received'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    JOB_TYPE_CHOICES = [
        ('Full-Time', 'Full-Time'),
        ('Internship', 'Internship'),
        ('Contract', 'Contract'),
        ('Remote', 'Remote'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='job_applications'
    )
    company_name = models.CharField(max_length=200)
    role_title = models.CharField(max_length=200)
    job_type = models.CharField(max_length=50, choices=JOB_TYPE_CHOICES, default='Full-Time')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='applied')
    
    job_url = models.URLField(blank=True, null=True, help_text="Link to the original job posting")
    location = models.CharField(max_length=150, blank=True, default="Remote / Flexible")
    salary_or_stipend = models.CharField(max_length=100, blank=True, help_text="e.g. ₹8-12 LPA or ₹30,000/mo")
    
    applied_date = models.DateField(default=timezone.now)
    interview_date = models.DateTimeField(blank=True, null=True)
    last_contact_date = models.DateField(default=timezone.now)
    
    contact_person = models.CharField(max_length=150, blank=True, help_text="Recruiter or Referral contact name/email")
    notes = models.TextField(blank=True, help_text="Interview rounds, take-home questions, or prep notes")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.role_title} at {self.company_name} ({self.get_status_display()})"

    @property
    def days_since_applied(self):
        if self.applied_date:
            return (timezone.now().date() - self.applied_date).days
        return 0

    @property
    def applied_time_display(self):
        """Human-friendly relative date string: Today, Yesterday, N days ago, or formatted date."""
        if not self.applied_date:
            return "Recently"
        days = self.days_since_applied
        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 30:
            return f"{days} days ago"
        else:
            return self.applied_date.strftime("%b %d, %Y")

    @property
    def needs_follow_up(self):
        """Alert student if 5+ days passed with status 'applied' or 'referral_requested'."""
        return self.status in ['applied', 'referral_requested'] and self.days_since_applied >= 5

    @property
    def is_ghosted(self):
        """Mark as stale/ghosted if 14+ days passed with no updates."""
        return self.status in ['applied', 'referral_requested', 'assessment'] and self.days_since_applied >= 14
