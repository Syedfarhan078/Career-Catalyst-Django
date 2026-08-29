import random
import os
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import EmailOTP
from django.db import transaction

User = get_user_model()

def generate_otp_code():
    """Generates a secure 6-digit numeric string."""
    return "".join(random.choices("0123456789", k=6))

import requests

def send_otp_email(user, otp_code):
    """Sends OTP verification code. Uses Brevo HTTP API if configured (bypassing Render SMTP block)."""
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
                "email": settings.DEFAULT_FROM_EMAIL,
                "name": "Career Catalyst"
            },
            "to": [{"email": user.email, "name": user.username}],
            "subject": "Confirm your Career Catalyst account activation",
            "textContent": (
                f"Hello {user.first_name or user.username},\n\n"
                f"Thank you for creating an account with Career Catalyst, your personalized portal for career guidance and interview preparation.\n\n"
                f"To complete your registration and activate your account, please enter the following verification code on the registration page:\n\n"
                f"Verification Code: {otp_code}\n\n"
                f"This code is valid for 5 minutes. If you did not register for a Career Catalyst account, you can safely ignore this email.\n\n"
                f"Best regards,\n"
                f"The Career Catalyst Team"
            )
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return
        except Exception as e:
            # Fallback to standard Django mailer if API call fails
            pass

    subject = "Confirm your Career Catalyst account activation"
    message = (
        f"Hello {user.first_name or user.username},\n\n"
        f"Thank you for creating an account with Career Catalyst, your personalized portal for career guidance and interview preparation.\n\n"
        f"To complete your registration and activate your account, please enter the following verification code on the registration page:\n\n"
        f"Verification Code: {otp_code}\n\n"
        f"This code is valid for 5 minutes. If you did not register for a Career Catalyst account, you can safely ignore this email.\n\n"
        f"Best regards,\n"
        f"The Career Catalyst Team"
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

def create_user_with_otp(form_cleaned_data):
    """
    Saves a newly registered inactive user, generates a random 6-digit OTP,
    hashes the OTP in the database, and fires the code to the user's email.
    Uses transaction.atomic to roll back user creation if email dispatch fails.
    """
    password = form_cleaned_data.pop('password', None)
    password1 = form_cleaned_data.pop('password1', None)
    form_cleaned_data.pop('password2', None)
    
    active_password = password1 or password

    with transaction.atomic():
        user = User(**form_cleaned_data)
        if active_password:
            user.set_password(active_password)
        user.is_active = False
        user.save()

        # Generate, hash, and store OTP
        otp_code = generate_otp_code()
        otp_hash = make_password(otp_code)
        EmailOTP.objects.create(user=user, otp_hash=otp_hash)
        
        # Send email (throws connection errors if SMTP is down, rolling back creation)
        send_otp_email(user, otp_code)
        
    return user

def verify_user_otp(user_id, input_code):
    """
    Checks the user's input OTP code. Marks the user active if validated.
    Tracks and limits incorrect tries to 5 max, and checks expiration.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise ValidationError("User not found.")

    otp = EmailOTP.objects.filter(user=user, is_verified=False).last()
    if not otp:
        raise ValidationError("No active OTP code found. Please request a new one.")

    if otp.is_expired():
        raise ValidationError("This OTP code has expired. Please request a new one.")

    if otp.attempt_count >= 5:
        otp.delete()
        raise ValidationError("Too many incorrect attempts. This OTP has been invalidated. Please request a new one.")

    # Validate hashed OTP
    if not check_password(input_code, otp.otp_hash):
        otp.attempt_count += 1
        otp.save()
        remaining = 5 - otp.attempt_count
        if remaining <= 0:
            otp.delete()
            raise ValidationError("Too many incorrect attempts. This OTP has been invalidated. Please request a new one.")
        raise ValidationError(f"Incorrect OTP code. You have {remaining} attempts remaining.")

    # Success path
    otp.is_verified = True
    otp.save()

    user.is_active = True
    user.save()

    # Clear user OTPs
    EmailOTP.objects.filter(user=user).delete()
    return user

def resend_user_otp(user_id):
    """
    Enforces a 60-second throttling limit, invalidates older verification codes,
    generates a new active OTP, hashes it, and fires it to the user's email.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise ValidationError("User not found.")

    last_otp = EmailOTP.objects.filter(user=user).last()
    if last_otp:
        elapsed = (timezone.now() - last_otp.created_at).total_seconds()
        if elapsed < 60:
            wait_time = int(60 - elapsed)
            raise ValidationError(f"Please wait {wait_time} seconds before requesting a new code.")

    # Delete all outstanding user codes
    EmailOTP.objects.filter(user=user).delete()

    # Generate and send new OTP
    otp_code = generate_otp_code()
    otp_hash = make_password(otp_code)
    EmailOTP.objects.create(user=user, otp_hash=otp_hash)
    send_otp_email(user, otp_code)
