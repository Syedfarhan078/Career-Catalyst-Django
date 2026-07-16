from django.db import models
from django.conf import settings

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
