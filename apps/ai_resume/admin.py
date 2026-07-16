from django.contrib import admin
from .models import ResumeAnalysis, MissingSkill, ImprovementSuggestion

class MissingSkillInline(admin.TabularInline):
    model = MissingSkill
    extra = 0

class ImprovementSuggestionInline(admin.TabularInline):
    model = ImprovementSuggestion
    extra = 0

@admin.register(ResumeAnalysis)
class ResumeAnalysisAdmin(admin.ModelAdmin):
    list_display = ('user', 'target_role', 'overall_score', 'ats_score', 'created_at')
    list_filter = ('target_role', 'created_at')
    search_fields = ('user__username', 'target_role', 'raw_text')
    inlines = [MissingSkillInline, ImprovementSuggestionInline]

@admin.register(MissingSkill)
class MissingSkillAdmin(admin.ModelAdmin):
    list_display = ('skill_name', 'importance', 'analysis')
    list_filter = ('importance',)

@admin.register(ImprovementSuggestion)
class ImprovementSuggestionAdmin(admin.ModelAdmin):
    list_display = ('category', 'priority', 'analysis')
    list_filter = ('category', 'priority')
