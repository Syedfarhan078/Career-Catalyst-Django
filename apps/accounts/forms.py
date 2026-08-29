# apps/accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes to all fields
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes to username and password
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})

class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'profile_picture', 'bio', 'github', 'linkedin')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'profile_picture':
                field.widget.attrs.update({'class': 'form-control-file'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
            
            # Make bio input look like a proper text area with size limits
            if name == 'bio':
                field.widget.attrs.update({'rows': 4})

class OTPVerificationForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        label="Enter 6-Digit OTP",
        widget=forms.TextInput(attrs={
            'placeholder': '123456',
            'class': 'form-control text-center font-monospace fs-4',
            'autocomplete': 'off',
            'maxlength': '6'
        })
    )