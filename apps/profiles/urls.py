# apps/profiles/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.profile_create_view, name='profile_create'),
    path('edit/', views.profile_update_view, name='profile_edit'),
    path('view/', views.profile_detail_view, name='profile_detail'),
]
