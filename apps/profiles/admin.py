from django.contrib import admin
from .models import StudentProfile, StudentProject, StudentCertification

class StudentProjectInline(admin.TabularInline):
    model = StudentProject
    extra = 0
    fields = ('title', 'technologies_used', 'start_date', 'end_date', 'is_current')

class StudentCertificationInline(admin.TabularInline):
    model = StudentCertification
    extra = 0
    fields = ('name', 'organization', 'issue_date', 'credential_id')

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'college', 'degree', 'branch', 'graduation_year', 'cgpa', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'college', 'university')
    list_filter = ('branch', 'graduation_year', 'current_skill_level')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [StudentProjectInline, StudentCertificationInline]
    
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

@admin.register(StudentProject)
class StudentProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'profile', 'technologies_used', 'start_date', 'end_date', 'created_at')
    search_fields = ('title', 'technologies_used', 'profile__user__username')
    list_filter = ('is_current', 'created_at')

@admin.register(StudentCertification)
class StudentCertificationAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'profile', 'issue_date', 'credential_id', 'created_at')
    search_fields = ('name', 'organization', 'credential_id', 'profile__user__username')
    list_filter = ('organization', 'created_at')

