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

import os
import requests
import logging
from django.template import loader
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm

logger = logging.getLogger(__name__)

class CustomPasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        """
        Sends password reset email via Brevo HTTP API if configured (bypassing Render/cloud SMTP blocks),
        or falls back to Django send_mail with safety error handling.
        """
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        html_message = None
        if html_email_template_name:
            html_message = loader.render_to_string(html_email_template_name, context)

        # 1. Try Brevo HTTP API if key configured
        brevo_api_key = os.getenv('BREVO_API_KEY')
        if brevo_api_key:
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "accept": "application/json",
                "api-key": brevo_api_key,
                "content-type": "application/json"
            }
            payload = {
                "sender": {
                    "email": getattr(settings, 'DEFAULT_FROM_EMAIL', 'verification@careercatalyst.com'),
                    "name": "Career Catalyst"
                },
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": body,
            }
            if html_message:
                payload["htmlContent"] = html_message
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                response.raise_for_status()
                return
            except Exception as e:
                logger.warning(f"Brevo API dispatch failed for password reset: {e}. Falling back to standard mailer.")

        # 2. Standard Django mail dispatch with safe fallback
        try:
            email_message = EmailMultiAlternatives(
                subject, body, from_email, [to_email]
            )
            if html_message:
                email_message.attach_alternative(html_message, "text/html")
            email_message.send(fail_silently=False)
        except Exception as e:
            logger.error(f"Failed to dispatch password reset email to {to_email}: {e}")
            reset_url = f"{context.get('protocol')}://{context.get('domain')}/accounts/reset/{context.get('uid')}/{context.get('token')}/"
            print(f"\n[PASSWORD RESET LINK for {to_email}]: {reset_url}\n")