from django.urls import path
from . import views

app_name = 'community'

urlpatterns = [
    # Community Hub (Threads/Projects/Stories feed)
    path('', views.CommunityHubView.as_view(), name='hub'),

    # Forum Discussion
    path('forum/', views.ForumListView.as_view(), name='forum_list'),
    path('forum/new/', views.create_thread, name='create_thread'),
    path('forum/thread/<int:pk>/', views.ForumThreadDetailView.as_view(), name='forum_detail'),
    path('forum/thread/<int:pk>/reply/', views.add_reply, name='add_reply'),

    # Share Projects
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/new/', views.share_project, name='share_project'),
    path('projects/like/<int:pk>/', views.toggle_like_project, name='toggle_like_project'),

    # Placement Success Stories
    path('stories/', views.SuccessStoryListView.as_view(), name='story_list'),

    # --- MENTOR MARKETPLACE PATHS ---
    path('mentors/', views.MarketplaceListView.as_view(), name='mentor_list'),
    path('mentors/register/', views.mentor_register, name='mentor_register'),
    path('mentors/<int:pk>/', views.MentorDetailView.as_view(), name='mentor_detail'),
    path('mentors/<int:mentor_id>/book/', views.book_mentorship_session, name='book_session'),
    
    # Mentor Dashboard Management
    path('mentors/dashboard/', views.mentor_dashboard, name='mentor_dashboard'),
    path('mentors/dashboard/profile/', views.edit_mentor_profile, name='edit_profile'),
    path('mentors/dashboard/availability/', views.manage_availability, name='manage_availability'),
    path('mentors/dashboard/availability/delete/<int:pk>/', views.delete_availability, name='delete_availability'),
    path('mentors/dashboard/requests/', views.mentor_requests_list, name='mentor_requests'),
    path('mentors/dashboard/requests/<int:pk>/respond/', views.respond_to_request, name='respond_request'),
    
    # Student Booking logs
    path('student/bookings/', views.student_bookings_list, name='student_bookings'),
    path('student/bookings/<int:pk>/cancel/', views.cancel_student_booking, name='cancel_booking'),
    path('student/bookings/<int:mentor_id>/review/', views.submit_mentor_review, name='submit_review'),
    
    # Staff / Admin Panel reviews
    path('admin/verify/', views.admin_verification_dashboard, name='admin_verify'),
    path('admin/verify/<int:pk>/<str:action>/', views.admin_action_mentor, name='admin_action'),
    
    # Direct Chat Console (Bonus Integration)
    path('mentors/chat/<int:mentor_id>/', views.mentor_chat_view, name='mentor_chat'),
    path('mentors/chat/<int:mentor_id>/send/', views.send_mentor_message, name='send_mentor_message'),
]
