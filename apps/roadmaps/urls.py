from django.urls import path
from . import views

app_name = 'roadmaps'

urlpatterns = [
    # Public roadmap catalogue
    path('roadmaps/', views.PublicRoadmapListView.as_view(), name='path_list'),

    # Authenticated user roadmap views
    path('roadmaps/my/', views.CareerPathListView.as_view(), name='my_roadmap'),
    path('roadmaps/certificate/<str:certificate_id>/', views.certificate_view, name='certificate_view'),
    path('roadmaps/certificate/<str:certificate_id>/pdf/', views.certificate_pdf, name='certificate_pdf'),
    path('roadmaps/verify/<str:certificate_id>/', views.verify_certificate, name='verify_certificate'),

    # Enrollment and AJAX progress
    path('roadmaps/<slug:slug>/enroll/', views.enroll_roadmap, name='enroll'),
    path('roadmaps/api/toggle/<int:topic_id>/', views.toggle_topic, name='toggle_topic'),

    # Public roadmap detail (SEO friendly)
    path('roadmaps/<slug:slug>/', views.PublicRoadmapDetailView.as_view(), name='path_detail'),

    # Private interactive learning console
    path('dashboard/roadmaps/<slug:slug>/', views.RoadmapDetailView.as_view(), name='learning_detail'),
]

