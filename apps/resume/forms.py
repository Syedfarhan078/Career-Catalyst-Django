from django import forms
from .models import Resume, Education, Experience, Project, Skill, Certification

class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ['title', 'template', 'is_default']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Software Engineer Resume'}),
            'template': forms.Select(attrs={'class': 'form-select'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = ['college', 'degree', 'branch', 'cgpa', 'start_year', 'end_year']
        widgets = {
            'college': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'University Name'}),
            'degree': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. B.Tech, B.Sc'}),
            'branch': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Computer Science'}),
            'cgpa': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'start_year': forms.NumberInput(attrs={'class': 'form-control'}),
            'end_year': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ExperienceForm(forms.ModelForm):
    class Meta:
        model = Experience
        fields = ['company', 'position', 'location', 'start_date', 'end_date', 'is_current', 'description']
        widgets = {
            'company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company Name'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Job Title'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City, Country'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe your responsibilities and achievements...'}),
        }

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description', 'technologies_used', 'github_url', 'live_demo_url']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Project Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'technologies_used': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Python, Django, React'}),
            'github_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://github.com/...', 'required': False}),
            'live_demo_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...', 'required': False}),
        }

class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Python'}),
        }

class CertificationForm(forms.ModelForm):
    class Meta:
        model = Certification
        fields = ['name', 'organization', 'issue_date', 'credential_url']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Certificate Name'}),
            'organization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Issuing Organization'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'credential_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...', 'required': False}),
        }
