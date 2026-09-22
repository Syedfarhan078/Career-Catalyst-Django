from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from apps.accounts.forms import UserProfileForm
from .models import StudentProfile
from .forms import StudentProfileForm

@login_required
def profile_create_view(request):
    # Check if profile already exists
    if hasattr(request.user, 'studentprofile'):
        return redirect('profile_detail')
        
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, "Your profile has been created successfully! Welcome onboarding completed.")
            return redirect('dashboard')
        else:
            messages.error(request, "There was an error creating your profile. Please check the fields below.")
    else:
        form = StudentProfileForm()
        
    user_initials = f"{request.user.first_name[:1]}{request.user.last_name[:1]}".upper() or request.user.username[:2].upper()
    context = {
        'form': form,
        'profile': None,
        'user_initials': user_initials,
        'target_career': "Engineering Student",
    }
    return render(request, 'profiles/create_profile.html', context)

@login_required
def profile_update_view(request):
    # Check if profile exists; if not, force create
    if not hasattr(request.user, 'studentprofile'):
        return redirect('profile_create')
        
    profile = request.user.studentprofile
    active_tab = request.GET.get('tab', 'account')
    if active_tab not in ['account', 'profile', 'security', 'danger']:
        active_tab = 'account'

    account_form = UserProfileForm(instance=request.user)
    profile_form = StudentProfileForm(instance=profile)
    password_form = PasswordChangeForm(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_account':
            active_tab = 'account'
            account_form = UserProfileForm(request.POST, request.FILES, instance=request.user)
            if account_form.is_valid():
                account_form.save()
                messages.success(request, "Account settings updated successfully.")
                return redirect(f"{reverse('profile_edit')}?tab=account")
            else:
                messages.error(request, "Please correct the errors in your account settings.")

        elif action == 'update_profile':
            active_tab = 'profile'
            profile_form = StudentProfileForm(request.POST, request.FILES, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Career & student profile updated successfully.")
                return redirect(f"{reverse('profile_edit')}?tab=profile")
            else:
                messages.error(request, "Please correct the errors in your career profile.")

        elif action == 'change_password':
            active_tab = 'security'
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password has been changed successfully.")
                return redirect(f"{reverse('profile_edit')}?tab=security")
            else:
                messages.error(request, "Please correct the errors below to change your password.")

        else:
            # Fallback for standard or legacy form submission
            profile_form = StudentProfileForm(request.POST, request.FILES, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Your profile has been updated successfully!")
                return redirect('profile_detail')
            else:
                active_tab = 'profile'
                messages.error(request, "There was an error updating your profile. Please check the fields below.")

    completion_percentage = profile.calculate_completion_percentage()
    user_initials = f"{request.user.first_name[:1]}{request.user.last_name[:1]}".upper() or request.user.username[:2].upper()
    target_career = profile.career_goal or "Engineering Student"

    context = {
        'profile': profile,
        'form': profile_form,
        'profile_form': profile_form,
        'account_form': account_form,
        'password_form': password_form,
        'active_tab': active_tab,
        'completion_percentage': completion_percentage,
        'user_initials': user_initials,
        'target_career': target_career,
    }
    return render(request, 'profiles/edit_profile.html', context)

@login_required
def profile_detail_view(request):
    if not hasattr(request.user, 'studentprofile'):
        return redirect('profile_create')
        
    profile = request.user.studentprofile
    completion_percentage = profile.calculate_completion_percentage()
    user_initials = f"{request.user.first_name[:1]}{request.user.last_name[:1]}".upper() or request.user.username[:2].upper()
    target_career = profile.career_goal or "Engineering Student"
    
    context = {
        'profile': profile,
        'completion_percentage': completion_percentage,
        'user_initials': user_initials,
        'target_career': target_career,
    }
    return render(request, 'profiles/profile.html', context)

