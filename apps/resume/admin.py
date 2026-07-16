from django.contrib import admin
from .models import Resume, Education, Experience, Project, Skill, Certification

class EducationInline(admin.TabularInline):
    model = Education
    extra = 1

class ExperienceInline(admin.StackedInline):
    model = Experience
    extra = 1

class ProjectInline(admin.StackedInline):
    model = Project
    extra = 1

class SkillInline(admin.TabularInline):
    model = Skill
    extra = 1

class CertificationInline(admin.TabularInline):
    model = Certification
    extra = 1

@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'template', 'is_default', 'created_at', 'updated_at')
    list_filter = ('template', 'is_default', 'created_at')
    search_fields = ('title', 'user__username', 'user__email')
    inlines = [EducationInline, ExperienceInline, ProjectInline, SkillInline, CertificationInline]

admin.site.register(Education)
admin.site.register(Experience)
admin.site.register(Project)
admin.site.register(Skill)
admin.site.register(Certification)
