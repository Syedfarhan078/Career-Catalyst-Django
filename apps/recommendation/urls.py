from django.urls import path
from . import views

app_name = 'recommendation'

urlpatterns = [
    path('', views.career_dashboard, name='dashboard'),
    path('analyze/', views.run_analysis, name='analyze'),
]
