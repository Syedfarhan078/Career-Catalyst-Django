from django.urls import path
from . import views

app_name = 'recommendation'

urlpatterns = [
    path('', views.career_dashboard, name='dashboard'),
    path('analyze/', views.run_analysis, name='analyze'),
    path('activate-roadmap/<int:analysis_id>/', views.activate_roadmap_from_analysis, name='activate_roadmap'),
]

