from django import forms
from apps.roadmaps.models import CareerPath
from .models import CareerAnalysis

class CareerTargetForm(forms.Form):
    target_career = forms.ModelChoiceField(
        queryset=CareerPath.objects.filter(is_active=True),
        required=False,
        empty_label="Select target career path (Defaults to Profile goal)",
        widget=forms.Select(attrs={'class': 'form-select rounded-pill shadow-sm px-3 py-2'})
    )
    company_tier = forms.ChoiceField(
        choices=CareerAnalysis.COMPANY_TIER_CHOICES,
        required=False,
        initial='general',
        widget=forms.Select(attrs={'class': 'form-select rounded-pill shadow-sm px-3 py-2'})
    )

