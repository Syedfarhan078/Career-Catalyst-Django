from django.urls import path
from . import views

app_name = 'interviews'

urlpatterns = [
    path('', views.InterviewHubView.as_view(), name='hub'),
    
    # Quiz routes
    path('quiz/<slug:slug>/start/', views.start_quiz, name='start_quiz'),
    path('quiz/submit/', views.submit_quiz, name='submit_quiz'),
    
    # Coding routes
    path('coding/', views.CodingListView.as_view(), name='coding_list'),
    path('coding/<int:pk>/', views.CodingDetailView.as_view(), name='coding_detail'),
    path('coding/<int:pk>/submit/', views.submit_code, name='submit_code'),
    
    # HR & Behavioral STAR routes
    path('behavioral/', views.HRBehavioralListView.as_view(), name='behavioral_list'),
    path('behavioral/<int:pk>/', views.HRBehavioralDetailView.as_view(), name='behavioral_detail'),
    path('behavioral/<int:pk>/submit/', views.submit_star, name='submit_star'),
    
    # Mock interview routes
    path('mock/', views.MockInterviewListView.as_view(), name='mock_list'),
    path('mock/start/', views.start_mock, name='start_mock'),
    path('mock/<int:pk>/', views.mock_session, name='mock_session'),
    path('mock/<int:pk>/reply/', views.chat_reply, name='chat_reply'),
    path('mock/<int:pk>/report/', views.mock_report, name='mock_report'),
    
    # Proctor violation logger API
    path('api/proctor-log/', views.log_proctor_violation, name='log_proctor_violation'),
    
    # Combined performance report
    path('reports/', views.PerformanceReportView.as_view(), name='reports'),
]
