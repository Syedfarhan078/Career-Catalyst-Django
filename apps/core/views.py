# apps/core/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

def home_view(request): # Ensure this function name is 'home'
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/home.html')

@login_required
def dashboard_view(request):
    # If the user doesn't have a profile completed yet, redirect them to complete it
    if not hasattr(request.user, 'studentprofile'):
        return redirect('profile_create')
        
    profile = request.user.studentprofile
    completion_percentage = profile.calculate_completion_percentage()
    
    context = {
        'profile': profile,
        'completion_percentage': completion_percentage,
    }
    return render(request, 'core/dashboard.html', context)