from django import forms
from apps.resume.models import Resume
from .models import ResumeAnalysis

class ResumeAnalysisForm(forms.ModelForm):
    resume = forms.ModelChoiceField(
        queryset=Resume.objects.none(),
        required=False,
        label="Select a resume built in Career Catalyst",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    uploaded_file = forms.FileField(
        required=False,
        label="Upload Resume File (PDF or DOCX)",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.docx'})
    )
    raw_text_input = forms.CharField(
        required=False,
        label="Or Paste Resume Text Directly",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Paste your resume content, experience, and project bullet points directly here...'
        })
    )
    job_description = forms.CharField(
        required=False,
        label="Target Job Description (Optional)",
        help_text="Paste a real Job Description from LinkedIn/Indeed to compute an exact TF-IDF match score and custom skill gaps.",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Paste job posting requirements, responsibilities, or tech stack here (optional)...'
        })
    )

    class Meta:
        model = ResumeAnalysis
        fields = ['target_role', 'job_description', 'resume', 'uploaded_file']
        widgets = {
            'target_role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Software Engineer, Data Scientist, QA Manual Tester'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['resume'].queryset = Resume.objects.filter(user=user)

    def clean_uploaded_file(self):
        uploaded_file = self.cleaned_data.get('uploaded_file')
        if uploaded_file:
            if uploaded_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("The uploaded file size must not exceed 5MB.")
            ext = uploaded_file.name.split('.')[-1].lower()
            if ext not in ['pdf', 'docx']:
                raise forms.ValidationError("Only PDF and DOCX files are supported.")
            if hasattr(uploaded_file, 'seek'):
                uploaded_file.seek(0)
        return uploaded_file

    def clean(self):
        cleaned_data = super().clean()
        resume = cleaned_data.get('resume')
        uploaded_file = cleaned_data.get('uploaded_file')
        raw_text_input = cleaned_data.get('raw_text_input')

        options_provided = sum([bool(resume), bool(uploaded_file), bool(raw_text_input)])

        if options_provided == 0:
            raise forms.ValidationError("Please provide your resume by uploading a PDF/DOCX file, selecting a built resume, or pasting text directly.")

        return cleaned_data
