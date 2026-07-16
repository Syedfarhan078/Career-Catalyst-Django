from django.contrib import admin
from .models import CareerPath, Milestone, Topic, UserRoadmap, TopicProgress


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0

class TopicInline(admin.TabularInline):
    model = Topic
    extra = 0

@admin.register(CareerPath)
class CareerPathAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'estimated_weeks', 'difficulty', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [MilestoneInline]

@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ('career_path', 'week_number', 'title', 'level')
    list_filter = ('career_path', 'level')
    inlines = [TopicInline]

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'milestone', 'resource_type', 'estimated_hours')
    list_filter = ('resource_type',)

@admin.register(UserRoadmap)
class UserRoadmapAdmin(admin.ModelAdmin):
    list_display = ('user', 'career_path', 'started_at', 'is_active')

@admin.register(TopicProgress)
class TopicProgressAdmin(admin.ModelAdmin):
    list_display = ('user_roadmap', 'topic', 'is_completed', 'completed_at')
