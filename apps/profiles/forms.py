import re
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import StudentProfile

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
