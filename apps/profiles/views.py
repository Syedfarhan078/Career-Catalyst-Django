from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from apps.accounts.forms import UserProfileForm
from .models import StudentProfile, StudentProject, StudentCertification
from .forms import StudentProfileForm, StudentProjectForm, StudentCertificationForm

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
    if active_tab not in ['account', 'profile', 'portfolio', 'security', 'danger']:
        active_tab = 'account'

    account_form = UserProfileForm(instance=request.user)
    profile_form = StudentProfileForm(instance=profile)
    project_form = StudentProjectForm()
    cert_form = StudentCertificationForm()
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

        elif action == 'add_project':
            active_tab = 'portfolio'
            project_form = StudentProjectForm(request.POST)
            if project_form.is_valid():
                new_project = project_form.save(commit=False)
                new_project.profile = profile
                new_project.save()
                messages.success(request, f"Project '{new_project.title}' added to your portfolio.")
                return redirect(f"{reverse('profile_edit')}?tab=portfolio")
            else:
                messages.error(request, "Please correct the errors in your project submission.")

        elif action == 'delete_project':
            active_tab = 'portfolio'
            project_id = request.POST.get('project_id')
            project = get_object_or_404(StudentProject, pk=project_id, profile=profile)
            project_title = project.title
            project.delete()
            messages.success(request, f"Project '{project_title}' removed from your portfolio.")
            return redirect(f"{reverse('profile_edit')}?tab=portfolio")

        elif action == 'add_certification':
            active_tab = 'portfolio'
            cert_form = StudentCertificationForm(request.POST)
            if cert_form.is_valid():
                new_cert = cert_form.save(commit=False)
                new_cert.profile = profile
                new_cert.save()
                messages.success(request, f"Certification '{new_cert.name}' added to your credentials.")
                return redirect(f"{reverse('profile_edit')}?tab=portfolio")
            else:
                messages.error(request, "Please correct the errors in your certification submission.")

        elif action == 'delete_certification':
            active_tab = 'portfolio'
            cert_id = request.POST.get('certification_id')
            cert = get_object_or_404(StudentCertification, pk=cert_id, profile=profile)
            cert_name = cert.name
            cert.delete()
            messages.success(request, f"Certification '{cert_name}' removed from your credentials.")
            return redirect(f"{reverse('profile_edit')}?tab=portfolio")

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
    projects = profile.projects.all()
    certifications = profile.certifications.all()
    from apps.roadmaps.models import RoadmapCertificate
    roadmap_certificates = RoadmapCertificate.objects.filter(user=request.user, is_valid=True).select_related('career_path')

    context = {
        'profile': profile,
        'form': profile_form,
        'profile_form': profile_form,
        'project_form': project_form,
        'cert_form': cert_form,
        'projects': projects,
        'certifications': certifications,
        'roadmap_certificates': roadmap_certificates,
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

    from apps.roadmaps.services import get_user_earned_skills_set
    from apps.roadmaps.models import RoadmapCertificate
    earned_skills = sorted(list(get_user_earned_skills_set(request.user)))
    projects = profile.projects.all()
    certifications = profile.certifications.all()
    roadmap_certificates = RoadmapCertificate.objects.filter(user=profile.user, is_valid=True).select_related('career_path')
    
    context = {
        'profile': profile,
        'earned_skills': earned_skills,
        'projects': projects,
        'certifications': certifications,
        'roadmap_certificates': roadmap_certificates,
        'completion_percentage': completion_percentage,
        'user_initials': user_initials,
        'target_career': target_career,
    }
    return render(request, 'profiles/profile.html', context)


