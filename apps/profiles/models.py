from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class StudentProfile(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
        ('Prefer not to say', 'Prefer not to say'),
    ]

    SKILL_LEVEL_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='studentprofile')
    
    # Personal Information
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    bio = models.TextField(blank=True)
    
    # Academic Information
    college = models.CharField(max_length=255, blank=True)
    university = models.CharField(max_length=255, blank=True)
    degree = models.CharField(max_length=100, blank=True)
    branch = models.CharField(max_length=100, blank=True)
    semester = models.IntegerField(blank=True, null=True)
    graduation_year = models.IntegerField(blank=True, null=True)
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    
    # Career Information
    career_goal = models.CharField(max_length=255, blank=True)
    current_skill_level = models.CharField(max_length=50, choices=SKILL_LEVEL_CHOICES, blank=True)
    preferred_domain = models.CharField(max_length=100, blank=True)
    expected_salary = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    preferred_location = models.CharField(max_length=100, blank=True)
    
    # Skills (stored as text/newline-separated)
    skills = models.TextField(blank=True, help_text="List your skills, each on a new line or separated by commas.")
    
    # Social Links
    github = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    portfolio = models.URLField(blank=True)
    leetcode = models.URLField(blank=True)
    hackerrank = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def calculate_completion_percentage(self):
        from django.db.models.fields.files import FieldFile
        fields_to_check = [
            'profile_picture', 'phone_number', 'date_of_birth', 'gender', 'bio',
            'college', 'university', 'degree', 'branch', 'semester', 'graduation_year', 'cgpa',
            'career_goal', 'current_skill_level', 'preferred_domain', 'expected_salary', 'preferred_location',
            'skills', 'github', 'linkedin', 'portfolio', 'leetcode', 'hackerrank'
        ]
        filled_count = 0
        for field in fields_to_check:
            val = getattr(self, field)
            if val is not None and val != "":
                # Exclude empty file fields
                if isinstance(val, FieldFile) and not val:
                    continue
                filled_count += 1
        return int((filled_count / len(fields_to_check)) * 100)

    @property
    def get_skills_list(self):
        if not self.skills:
            return []
        # Split by comma or newline and clean whitespace
        import re
        parts = re.split(r'[,\n\r]+', self.skills)
        return [p.strip() for p in parts if p.strip()]


class StudentProject(models.Model):
    profile = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='projects',
        db_index=True
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    technologies_used = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated tools and technologies (e.g. Django, React, PostgreSQL)"
    )
    github_url = models.URLField(max_length=500, blank=True)
    live_demo_url = models.URLField(max_length=500, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-end_date', '-created_at']
        indexes = [
            models.Index(fields=['profile', '-created_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.profile.user.username})"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': "End date cannot precede start date."})
        if self.github_url and not self.github_url.startswith(('http://', 'https://')):
            raise ValidationError({'github_url': "GitHub URL must start with http:// or https://"})
        if self.live_demo_url and not self.live_demo_url.startswith(('http://', 'https://')):
            raise ValidationError({'live_demo_url': "Live demo URL must start with http:// or https://"})

    @property
    def technologies_list(self):
        if not self.technologies_used:
            return []
        return [t.strip() for t in self.technologies_used.split(',') if t.strip()]


class StudentCertification(models.Model):
    profile = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name='certifications',
        db_index=True
    )
    name = models.CharField(max_length=255, verbose_name="Certification Name")
    organization = models.CharField(max_length=255, verbose_name="Issuing Organization")
    issue_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    credential_id = models.CharField(max_length=150, blank=True, verbose_name="Credential ID")
    credential_url = models.URLField(max_length=500, blank=True, verbose_name="Credential Verification URL")
    skills_validated = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated competencies validated (e.g. AWS, Cloud Computing, Docker)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date', '-created_at']
        indexes = [
            models.Index(fields=['profile', '-created_at']),
        ]

    def __str__(self):
        return f"{self.name} - {self.organization} ({self.profile.user.username})"

    def clean(self):
        super().clean()
        if self.issue_date and self.expiration_date and self.expiration_date < self.issue_date:
            raise ValidationError({'expiration_date': "Expiration date cannot precede issue date."})
        if self.credential_url and not self.credential_url.startswith(('http://', 'https://')):
            raise ValidationError({'credential_url': "Credential verification URL must start with http:// or https://"})

    @property
    def skills_list(self):
        if not self.skills_validated:
            return []
        return [s.strip() for s in self.skills_validated.split(',') if s.strip()]

