from django import forms
from django.core.exceptions import ValidationError
from .models import MentorProfile, MentorshipRequest, MentorReview, MentorAvailability
import re

class MentorRegistrationForm(forms.ModelForm):
    agreement = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the mentorship terms and conditions.'},
        label="I agree to the Mentorship Terms & Conditions"
    )
    
    # Custom fields for profile setup
    skills_csv = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Python, Django, REST API'}),
        label="Skills (Comma-separated)",
        help_text="Provide at least 3 skills separated by commas."
    )

    class Meta:
        model = MentorProfile
        fields = [
            'full_name', 'email', 'phone_number', 'company', 'designation', 
            'experience_years', 'current_location', 'bio', 'career_domains',
            'linkedin_url', 'github_url', 'portfolio_url', 'resume',
            'languages', 'available_days', 'available_time_slots', 
            'max_sessions_per_week', 'mentorship_type'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your professional background, milestones, and what you offer to students...'}),
            'career_domains': forms.TextInput(attrs={'placeholder': 'e.g. Backend, Devops, System Design'}),
            'languages': forms.TextInput(attrs={'placeholder': 'e.g. English'}),
            'available_days': forms.TextInput(attrs={'placeholder': 'e.g. Monday, Wednesday, Saturday'}),
            'available_time_slots': forms.TextInput(attrs={'placeholder': 'e.g. 09:00 AM - 11:00 AM, 04:00 PM - 06:00 PM'}),
        }

    def clean_skills_csv(self):
        skills_raw = self.cleaned_data.get('skills_csv', '')
        skills_list = [s.strip() for s in skills_raw.split(',') if s.strip()]
        if len(skills_list) < 1:
            raise ValidationError("You must list at least one skill.")
        return ",".join(skills_list)

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '')
        if not re.match(r'^\+?[0-9\s\-()]{7,20}$', phone):
            raise ValidationError("Please enter a valid phone number.")
        return phone


class MentorProfileEditForm(forms.ModelForm):
    skills_csv = forms.CharField(
        required=True,
        widget=forms.TextInput(),
        label="Skills (Comma-separated)"
    )

    class Meta:
        model = MentorProfile
        fields = [
            'full_name', 'email', 'phone_number', 'company', 'designation', 
            'experience_years', 'current_location', 'bio', 'career_domains',
            'linkedin_url', 'github_url', 'portfolio_url',
            'languages', 'available_days', 'available_time_slots', 
            'max_sessions_per_week', 'mentorship_type'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_skills_csv(self):
        skills_raw = self.cleaned_data.get('skills_csv', '')
        skills_list = [s.strip() for s in skills_raw.split(',') if s.strip()]
        return ",".join(skills_list)


class MentorshipBookingForm(forms.ModelForm):
    class Meta:
        model = MentorshipRequest
        fields = ['requested_date', 'requested_time', 'purpose', 'student_message']
        widgets = {
            'requested_date': forms.DateInput(attrs={'type': 'date'}),
            'requested_time': forms.TimeInput(attrs={'type': 'time'}),
            'student_message': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe what you would like to discuss during this session...'}),
        }


class MentorReviewForm(forms.ModelForm):
    class Meta:
        model = MentorReview
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, f"{i} Star{'s' if i > 1 else ''}") for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your feedback here...'}),
        }


class MentorAvailabilityForm(forms.ModelForm):
    class Meta:
        model = MentorAvailability
        fields = ['day', 'start_time', 'end_time', 'max_sessions']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        if start and end and start >= end:
            raise ValidationError("End time must be after start time.")
        return cleaned_data
