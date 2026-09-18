from django import forms
from .models import JobApplication


class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = [
            'company_name',
            'role_title',
            'job_type',
            'status',
            'job_url',
            'location',
            'salary_or_stipend',
            'applied_date',
            'interview_date',
            'contact_person',
            'notes',
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-control rounded-3',
                'placeholder': 'e.g. Zepto, Google, Razorpay',
                'required': 'true'
            }),
            'role_title': forms.TextInput(attrs={
                'class': 'form-control rounded-3',
                'placeholder': 'e.g. SDE-1, Frontend Intern, Data Analyst',
                'required': 'true'
            }),
            'job_type': forms.Select(attrs={'class': 'form-select rounded-3'}),
            'status': forms.Select(attrs={'class': 'form-select rounded-3'}),
            'job_url': forms.URLInput(attrs={
                'class': 'form-control rounded-3',
                'placeholder': 'https://jobs.lever.co/company/...'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control rounded-3',
                'placeholder': 'e.g. Bangalore, Remote, Pune'
            }),
            'salary_or_stipend': forms.TextInput(attrs={
                'class': 'form-control rounded-3',
                'placeholder': 'e.g. ₹8-12 LPA or ₹30,000/mo'
            }),
            'applied_date': forms.DateInput(attrs={
                'class': 'form-control rounded-3',
                'type': 'date'
            }),
            'interview_date': forms.DateTimeInput(attrs={
                'class': 'form-control rounded-3',
                'type': 'datetime-local'
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control rounded-3',
                'placeholder': 'e.g. Priya Sharma (Tech Recruiter)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control rounded-3',
                'rows': 3,
                'placeholder': 'Interview rounds, take-home questions, or key requirements...'
            }),
        }
