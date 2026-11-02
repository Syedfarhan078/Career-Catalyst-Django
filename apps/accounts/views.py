import logging
logger = logging.getLogger(__name__)
import secrets
import time
from .google_auth import (
    get_google_authorization_url,
    get_google_redirect_uri,
    exchange_code_for_tokens,
    verify_google_id_token,
    authenticate_or_register_google_user,
)
# apps/accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.urls import reverse_lazy

from django.core.exceptions import ValidationError
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm, OTPVerificationForm, CustomPasswordResetForm
from .services import create_user_with_otp, verify_user_otp, resend_user_otp, get_role_based_redirect_url

def register_view(request):
    if request.user.is_authenticated:
        return redirect(get_role_based_redirect_url(request.user))
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = create_user_with_otp(form.cleaned_data)
                request.session['verify_user_id'] = user.id
                messages.info(request, "An OTP verification code has been sent to your email. Please enter it below to activate your account.")
                return redirect('verify_otp')
            except Exception as e:
                messages.error(request, f"Error generating verification code: {str(e)}")
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})

def verify_otp_view(request):
    if request.user.is_authenticated:
        return redirect(get_role_based_redirect_url(request.user))
        
    user_id = request.session.get('verify_user_id')
    if not user_id:
        messages.error(request, "Please register first.")
        return redirect('register')
        
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']
            try:
                user = verify_user_otp(user_id, otp_code)
                if 'verify_user_id' in request.session:
                    del request.session['verify_user_id']
                login(request, user)
                messages.success(request, "Email verified successfully! Welcome to Career Catalyst.")
                return redirect(get_role_based_redirect_url(user))
            except ValidationError as e:
                form.add_error('otp_code', e.message)
    else:
        form = OTPVerificationForm()
    return render(request, 'accounts/verify_otp.html', {'form': form})

def resend_otp_view(request):
    if request.user.is_authenticated:
        return redirect(get_role_based_redirect_url(request.user))
        
    user_id = request.session.get('verify_user_id')
    if not user_id:
        messages.error(request, "Please register first.")
        return redirect('register')
        
    try:
        resend_user_otp(user_id)
        messages.success(request, "A new OTP code has been sent to your email.")
    except ValidationError as e:
        messages.error(request, e.message)
        
    return redirect('verify_otp')

def login_view(request):
    if request.user.is_authenticated:
        return redirect(get_role_based_redirect_url(request.user))
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(get_role_based_redirect_url(user))
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = UserLoginForm()
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('home')

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            try:
                updated_user = form.save()
                if 'profile_picture' in request.FILES and updated_user.profile_picture:
                    if hasattr(updated_user, 'studentprofile'):
                        student_prof = updated_user.studentprofile
                        student_prof.profile_picture.name = updated_user.profile_picture.name
                        student_prof.save(update_fields=['profile_picture'])
                messages.success(request, "Your profile has been updated successfully!")
                return redirect(f"{reverse_lazy('profile_edit')}?tab=account")
            except Exception as e:
                logger.exception("Failed to update profile view: %s", e)
                messages.error(request, f"Unable to save profile picture: {e}. Please check your Cloudinary configuration.")
        else:
            messages.error(request, "There was an error updating your profile. Please check the fields below.")
    else:
        return redirect(f"{reverse_lazy('profile_edit')}?tab=account")
        
    profile = getattr(request.user, 'studentprofile', None)
    user_initials = f"{request.user.first_name[:1]}{request.user.last_name[:1]}".upper() or request.user.username[:2].upper()
    target_career = profile.career_goal if profile and profile.career_goal else "Engineering Student"
    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
        'user_initials': user_initials,
        'target_career': target_career,
    })

@login_required
def delete_account_view(request):
    if request.method == 'POST':
        confirm_username = request.POST.get('confirm_username', '').strip()
        if confirm_username == request.user.username:
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, "Your account has been permanently deleted. We're sorry to see you go!")
            return redirect('home')
        else:
            messages.error(request, "The entered username does not match. Account deletion has been cancelled.")
            return redirect('delete_account')
            
    profile = getattr(request.user, 'studentprofile', None)
    user_initials = f"{request.user.first_name[:1]}{request.user.last_name[:1]}".upper() or request.user.username[:2].upper()
    target_career = profile.career_goal if profile and profile.career_goal else "Engineering Student"
    return render(request, 'accounts/delete_account.html', {
        'profile': profile,
        'user_initials': user_initials,
        'target_career': target_career,
    })

class CustomPasswordResetView(SuccessMessageMixin, auth_views.PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = 'accounts/forgot_password.html'
    email_template_name = 'accounts/password_reset_email.txt'
    html_email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('login')
    success_message = "We have emailed you instructions for resetting your password. If an account exists with this email, you will receive it shortly."

class CustomPasswordResetConfirmView(SuccessMessageMixin, auth_views.PasswordResetConfirmView):
    template_name = 'accounts/reset_password.html'
    success_url = reverse_lazy('login')
    success_message = "Your password has been successfully reset. You may now log in with your new password."

OAUTH_SESSION_KEYS = (
    'oauth_state',
    'oauth_code_verifier',
    'oauth_nonce',
    'oauth_pending_role',
    'oauth_created_at',
    'oauth_pending_user',
)


def clear_oauth_session(request):
    """Safely cleans up all temporary Google OAuth session data without affecting other session keys."""
    for key in OAUTH_SESSION_KEYS:
        request.session.pop(key, None)


def google_login_view(request):
    """Initiates Google OAuth 2.0 flow with state, PKCE, and optional pending role."""
    if request.user.is_authenticated:
        return redirect(get_role_based_redirect_url(request.user))

    role = request.GET.get('role') or request.POST.get('role')
    if role not in ['student', 'mentor']:
        role = None

    try:
        auth_url = get_google_authorization_url(request, role=role)
        return redirect(auth_url)
    except Exception as e:
        messages.error(request, f'Failed to initiate Google sign-in: {str(e)}')
        return redirect('login')


def google_callback_view(request):
    """Handles Google OAuth callback, validates state and PKCE, verifies ID token, and authenticates."""
    if request.user.is_authenticated:
        return redirect(get_role_based_redirect_url(request.user))

    # Handle cancelled or denied consent from Google
    if request.GET.get('error'):
        clear_oauth_session(request)
        messages.warning(request, 'Google sign-in was cancelled.')
        return redirect('login')

    code = request.GET.get('code')
    state = request.GET.get('state')

    session_state = request.session.pop('oauth_state', None)
    code_verifier = request.session.pop('oauth_code_verifier', None)
    session_nonce = request.session.pop('oauth_nonce', None)
    pending_role = request.session.pop('oauth_pending_role', None)
    created_at = request.session.pop('oauth_created_at', None)

    # State validation and replay protection
    if not state or not session_state or not secrets.compare_digest(state, session_state):
        clear_oauth_session(request)
        messages.error(request, 'Invalid or expired session state. Please try signing in again.')
        return redirect('login')

    # Expiration check (10 minutes)
    if created_at and (time.time() - created_at > 600):
        clear_oauth_session(request)
        messages.error(request, 'Authentication session timed out. Please try signing in again.')
        return redirect('login')

    if not code or not code_verifier:
        clear_oauth_session(request)
        messages.error(request, 'Missing authorization code or verifier from Google.')
        return redirect('login')

    redirect_uri = get_google_redirect_uri(request)

    try:
        tokens = exchange_code_for_tokens(code, code_verifier, redirect_uri)
        id_token = tokens['id_token']
        claims = verify_google_id_token(id_token, expected_nonce=session_nonce)
    except ValidationError as e:
        clear_oauth_session(request)
        msg = e.message if hasattr(e, 'message') else str(e)
        messages.error(request, msg)
        return redirect('login')
    except Exception:
        clear_oauth_session(request)
        messages.error(request, 'Google authentication verification failed. Please try again.')
        return redirect('login')

    status, user, err = authenticate_or_register_google_user(request, claims, role=pending_role)

    if status == 'error':
        clear_oauth_session(request)
        messages.error(request, err or 'Google authentication failed.')
        return redirect('login')

    if status == 'needs_role':
        request.session['oauth_pending_user'] = {
            'sub': claims['sub'],
            'email': claims['email'],
            'given_name': claims.get('given_name', ''),
            'family_name': claims.get('family_name', ''),
            'timestamp': time.time(),
        }
        return redirect('google_choose_role')

    if status == 'created':
        messages.success(request, f'Welcome to Career Catalyst, {user.username}!')
        return redirect(get_role_based_redirect_url(user))

    if status == 'authenticated':
        messages.success(request, f'Welcome back, {user.username}!')
        return redirect(get_role_based_redirect_url(user))

    messages.error(request, 'Unexpected authentication status.')
    return redirect('login')


def google_choose_role_view(request):
    """Dedicated role-selection view for new users who initiated Google sign-in from login."""
    if request.user.is_authenticated:
        return redirect(get_role_based_redirect_url(request.user))

    pending_data = request.session.get('oauth_pending_user')
    if not pending_data:
        clear_oauth_session(request)
        messages.error(request, 'No pending Google sign-in found. Please sign in again.')
        return redirect('login')

    # Expiration check (10 minutes)
    if time.time() - pending_data.get('timestamp', 0) > 600:
        clear_oauth_session(request)
        messages.error(request, 'Role selection session expired. Please sign in with Google again.')
        return redirect('login')

    if request.method == 'POST':
        role = request.POST.get('role', '').strip()
        if role not in ['student', 'mentor']:
            messages.error(request, 'Please select whether you want to join as a Student or Mentor.')
            return render(request, 'accounts/choose_role.html', {
                'pending_email': pending_data.get('email'),
                'given_name': pending_data.get('given_name')
            })

        status, user, err = authenticate_or_register_google_user(request, pending_data, role=role)
        clear_oauth_session(request)

        if status == 'error':
            messages.error(request, err or 'Account creation failed.')
            return redirect('login')

        if status in ['created', 'authenticated']:
            messages.success(request, f'Welcome to Career Catalyst, {user.username}!')
            return redirect(get_role_based_redirect_url(user))

        messages.error(request, 'Failed to complete registration.')
        return redirect('login')

    return render(request, 'accounts/choose_role.html', {
        'pending_email': pending_data.get('email'),
        'given_name': pending_data.get('given_name')
    })
