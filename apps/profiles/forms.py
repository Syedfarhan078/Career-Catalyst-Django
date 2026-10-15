import re
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import StudentProfile, StudentProject, StudentCertification

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        exclude = ('user',)
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Tell us a bit about yourself...'}),
            'skills': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Python\nDjango\nSQL\nMachine Learning'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add bootstrap styling to all non-textarea/date widgets dynamically
        for name, field in self.fields.items():
            if name not in ['date_of_birth', 'bio', 'skills', 'profile_picture']:
                field.widget.attrs.update({'class': 'form-control'})
            elif name == 'profile_picture':
                field.widget.attrs.update({'class': 'form-control-file'})

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '')
        if phone:
            digits_only = re.sub(r'\D', '', phone)
            if not (10 <= len(digits_only) <= 15):
                raise ValidationError("Phone number must contain between 10 and 15 digits.")
            return digits_only
        return phone

    def clean_cgpa(self):
        cgpa = self.cleaned_data.get('cgpa')
        if cgpa is not None:
            if not (0.0 <= float(cgpa) <= 10.0):
                raise ValidationError("CGPA must be between 0.0 and 10.0.")
        return cgpa

    def clean_graduation_year(self):
        year = self.cleaned_data.get('graduation_year')
        if year is not None:
            current_year = timezone.now().year
            if not (current_year <= year <= current_year + 10):
                raise ValidationError(f"Graduation year must be between {current_year} and {current_year + 10}.")
        return year

    def clean_github(self):
        url = self.cleaned_data.get('github', '')
        if url:
            if not url.startswith('https://github.com/'):
                raise ValidationError("GitHub link must start with https://github.com/")
        return url

    def clean_linkedin(self):
        url = self.cleaned_data.get('linkedin', '')
        if url:
            if not url.startswith('https://linkedin.com/'):
                raise ValidationError("LinkedIn link must start with https://linkedin.com/")
        return url


class StudentProjectForm(forms.ModelForm):
    class Meta:
        model = StudentProject
        exclude = ('profile',)
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Distributed Task Queue'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Describe what you built, architecture decisions, and business impact...'}),
            'technologies_used': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Python, Django, Redis, Celery, Docker'}),
            'github_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://github.com/username/project'}),
            'live_demo_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://myproject.demo.com'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        is_current = cleaned_data.get('is_current')
        if not is_current and start and end and end < start:
            raise ValidationError({'end_date': "End date cannot precede start date."})
        return cleaned_data


class StudentCertificationForm(forms.ModelForm):
    class Meta:
        model = StudentCertification
        exclude = ('profile',)
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. AWS Certified Solutions Architect - Associate'}),
            'organization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Amazon Web Services'}),
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expiration_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'credential_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. AWS-1234567'}),
            'credential_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.credly.com/badges/...'}),
            'skills_validated': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. AWS, Cloud Infrastructure, Docker'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        issue = cleaned_data.get('issue_date')
        exp = cleaned_data.get('expiration_date')
        if issue and exp and exp < issue:
            raise ValidationError({'expiration_date': "Expiration date cannot precede issue date."})
        return cleaned_data

