from django.urls import path
from . import views

app_name = 'resume'

urlpatterns = [
    path('', views.resume_list, name='list'),
    path('create/', views.resume_create, name='create'),
    path('<int:pk>/edit/', views.resume_builder, name='builder'),
    path('<int:pk>/preview/', views.resume_preview, name='preview'),
    path('<int:pk>/download/', views.resume_download_pdf, name='download'),
    path('<int:pk>/delete/', views.delete_resume, name='delete'),
    
    # AJAX API Endpoints
    path('<int:pk>/api/add/<str:section>/', views.add_section, name='api_add_section'),
    path('<int:pk>/api/delete/<str:section>/<int:item_id>/', views.delete_section, name='api_delete_section'),
    path('<int:pk>/api/settings/', views.update_resume_settings, name='api_update_settings'),
]
