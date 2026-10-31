from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_history_view, name='history'),
    path('unread-count/', views.unread_count_api, name='unread_count'),
    path('read-all/', views.mark_all_as_read_view, name='mark_all_as_read'),
    path('<int:notification_id>/read/', views.mark_as_read_view, name='mark_as_read'),
]
