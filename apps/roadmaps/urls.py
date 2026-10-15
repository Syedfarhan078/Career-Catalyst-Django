from django.urls import path
from . import views

app_name = 'roadmaps'

urlpatterns = [
    path('', views.CareerPathListView.as_view(), name='path_list'),
    path('my/', views.MyRoadmapView.as_view(), name='my_roadmap'),
    path('certificate/<str:certificate_id>/', views.certificate_view, name='certificate_view'),
    path('certificate/<str:certificate_id>/pdf/', views.certificate_pdf, name='certificate_pdf'),
    path('verify/<str:certificate_id>/', views.verify_certificate, name='verify_certificate'),
    path('<slug:slug>/', views.RoadmapDetailView.as_view(), name='path_detail'),
    path('<slug:slug>/enroll/', views.enroll_roadmap, name='enroll'),
    path('api/toggle/<int:topic_id>/', views.toggle_topic, name='toggle_topic'),
]

