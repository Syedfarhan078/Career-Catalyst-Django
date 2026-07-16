from django.urls import path
from . import views

app_name = 'ai_resume'

urlpatterns = [
    path('', views.AnalysisHistoryView.as_view(), name='history'),
    path('analyze/', views.AnalyzeResumeView.as_view(), name='analyze'),
    path('analysis/<int:pk>/', views.AnalysisDetailView.as_view(), name='detail'),
]
