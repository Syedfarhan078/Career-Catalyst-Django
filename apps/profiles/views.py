from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
        
    return render(request, 'profiles/create_profile.html', {'form': form})

@login_required
def profile_update_view(request):
    # Check if profile exists; if not, force create
    if not hasattr(request.user, 'studentprofile'):
        return redirect('profile_create')
        
    profile = request.user.studentprofile
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('profile_detail')
        else:
            messages.error(request, "There was an error updating your profile. Please check the fields below.")
    else:
        form = StudentProfileForm(instance=profile)
        
    return render(request, 'profiles/edit_profile.html', {'form': form, 'profile': profile})

@login_required
def profile_detail_view(request):
    if not hasattr(request.user, 'studentprofile'):
        return redirect('profile_create')
        
    profile = request.user.studentprofile
    completion_percentage = profile.calculate_completion_percentage()
    
    context = {
        'profile': profile,
        'completion_percentage': completion_percentage,
    }
    return render(request, 'profiles/profile.html', context)
