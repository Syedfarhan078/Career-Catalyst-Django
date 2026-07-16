from django.contrib import admin
from .models import StudentProfile

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'college', 'degree', 'branch', 'graduation_year', 'cgpa', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'college', 'university')
    list_filter = ('branch', 'graduation_year', 'current_skill_level')
    readonly_fields = ('created_at', 'updated_at')
    
    # Organize fields into sections in the detail view
    fieldsets = (
        ('Account Connection', {
            'fields': ('user',)
        }),
        ('Personal Details', {
            'fields': ('profile_picture', 'phone_number', 'date_of_birth', 'gender', 'bio')
        }),
        ('Academic Details', {
            'fields': ('college', 'university', 'degree', 'branch', 'semester', 'graduation_year', 'cgpa')
        }),
        ('Career Information', {
            'fields': ('career_goal', 'current_skill_level', 'preferred_domain', 'expected_salary', 'preferred_location')
        }),
        ('Skills', {
            'fields': ('skills',)
        }),
        ('Social Links', {
            'fields': ('github', 'linkedin', 'portfolio', 'leetcode', 'hackerrank')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
