from django.db import models
from django.conf import settings

class Resume(models.Model):
    TEMPLATE_CHOICES = [
        ('professional', 'Professional'),
        ('modern', 'Modern'),
        ('minimal', 'Minimal'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resumes')
    title = models.CharField(max_length=255, default="My Resume")
    template = models.CharField(max_length=50, choices=TEMPLATE_CHOICES, default='professional')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # If this is marked as default, unset other defaults for this user
            Resume.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

class Education(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='educations')
    college = models.CharField(max_length=255)
    degree = models.CharField(max_length=255)
    branch = models.CharField(max_length=255)
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    start_year = models.IntegerField()
    end_year = models.IntegerField()

    def __str__(self):
        return f"{self.degree} from {self.college}"

class Experience(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='experiences')
    company = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField()

    def __str__(self):
        return f"{self.position} at {self.company}"

class Project(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=255)
    description = models.TextField()
    technologies_used = models.CharField(max_length=255, help_text="Comma-separated (e.g., Python, Django)")
    github_url = models.URLField(blank=True)
    live_demo_url = models.URLField(blank=True)

    def __str__(self):
        return self.title

class Skill(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Certification(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='certifications')
    name = models.CharField(max_length=255)
    organization = models.CharField(max_length=255)
    issue_date = models.DateField(null=True, blank=True)
    credential_url = models.URLField(blank=True)

    def __str__(self):
        return self.name
