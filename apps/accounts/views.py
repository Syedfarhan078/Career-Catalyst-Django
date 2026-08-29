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
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm, OTPVerificationForm
from .services import create_user_with_otp, verify_user_otp, resend_user_otp

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
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
        return redirect('dashboard')
        
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
                return redirect('dashboard')
            except ValidationError as e:
                form.add_error('otp_code', e.message)
    else:
        form = OTPVerificationForm()
    return render(request, 'accounts/verify_otp.html', {'form': form})

def resend_otp_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
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
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('dashboard')
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
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('profile')
        else:
            messages.error(request, "There was an error updating your profile. Please check the fields below.")
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})

class CustomPasswordResetView(SuccessMessageMixin, auth_views.PasswordResetView):
    template_name = 'accounts/forgot_password.html'
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('login')
    success_message = "We have emailed you instructions for resetting your password. If an account exists with this email, you will receive it shortly."

class CustomPasswordResetConfirmView(SuccessMessageMixin, auth_views.PasswordResetConfirmView):
    template_name = 'accounts/reset_password.html'
    success_url = reverse_lazy('login')
    success_message = "Your password has been successfully reset. You may now log in with your new password."