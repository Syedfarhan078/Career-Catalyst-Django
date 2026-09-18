from django.contrib import admin
from .models import JobApplication


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'role_title', 'user', 'status', 'job_type', 'applied_date', 'updated_at')
    list_filter = ('status', 'job_type', 'applied_date')
    search_fields = ('company_name', 'role_title', 'user__username', 'user__email', 'location')
    ordering = ('-updated_at',)
