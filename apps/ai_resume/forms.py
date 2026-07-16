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
        label="Or upload a resume file (PDF or DOCX)",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.docx'})
    )

    class Meta:
        model = ResumeAnalysis
        fields = ['target_role', 'resume', 'uploaded_file']
        widgets = {
            'target_role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Software Engineer, Data Scientist'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['resume'].queryset = Resume.objects.filter(user=user)

    def clean_uploaded_file(self):
        uploaded_file = self.cleaned_data.get('uploaded_file')
        if uploaded_file:
            # Validate file size (max 5MB)
            if uploaded_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("The uploaded file size must not exceed 5MB.")
            
            # Validate extension
            ext = uploaded_file.name.split('.')[-1].lower()
            if ext not in ['pdf', 'docx']:
                raise forms.ValidationError("Only PDF and DOCX files are supported.")
        return uploaded_file

    def clean(self):
        cleaned_data = super().clean()
        resume = cleaned_data.get('resume')
        uploaded_file = cleaned_data.get('uploaded_file')

        if not resume and not uploaded_file:
            raise forms.ValidationError("You must either select a saved resume or upload a PDF/DOCX file.")

        if resume and uploaded_file:
            raise forms.ValidationError("Please choose only one option: select a saved resume OR upload a file.")

        return cleaned_data
