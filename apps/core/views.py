# apps/core/views.py
from django.shortcuts import render, redirect

def home_view(request): # Ensure this function name is 'home'
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/home.html')

def dashboard_view(request):
    return render(request, 'core/dashboard.html')