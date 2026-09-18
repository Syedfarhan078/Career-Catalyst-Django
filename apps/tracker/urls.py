from django.urls import path
from . import views

app_name = 'tracker'

urlpatterns = [
    path('', views.kanban_view, name='kanban'),
    path('add/', views.add_application, name='add'),
    path('<int:pk>/edit/', views.edit_application, name='edit'),
    path('<int:pk>/delete/', views.delete_application, name='delete'),
    path('api/update-status/<int:pk>/', views.api_update_status, name='api_update_status'),
    path('api/parse-url/', views.api_parse_url, name='api_parse_url'),
    path('api/followup/<int:pk>/', views.api_generate_followup, name='api_followup'),
]
