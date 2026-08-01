from django import forms
from apps.roadmaps.models import CareerPath

class CareerTargetForm(forms.Form):
    target_career = forms.ModelChoiceField(
        queryset=CareerPath.objects.filter(is_active=True),
        required=False,
        empty_label="Select target career path (Defaults to Profile goal)",
        widget=forms.Select(attrs={'class': 'form-select rounded-pill shadow-sm px-3 py-2'})
    )
