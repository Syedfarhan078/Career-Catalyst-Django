from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('career-guides/', views.guide_list_view, name='guide_list'),
    path('career-guides/<slug:slug>/', views.guide_detail_view, name='guide_detail'),
]
