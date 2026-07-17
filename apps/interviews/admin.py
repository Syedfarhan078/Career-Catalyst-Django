from django.contrib import admin
from .models import QuestionCategory, Question, UserAttempt, UserAttemptDetail, MockInterviewSession, MockInterviewChat, ProctorLog

class UserAttemptDetailInline(admin.TabularInline):
    model = UserAttemptDetail
    extra = 0

class MockInterviewChatInline(admin.TabularInline):
    model = MockInterviewChat
    extra = 0

@admin.register(QuestionCategory)
class QuestionCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'question_type', 'difficulty')
    list_filter = ('category', 'question_type', 'difficulty')
    search_fields = ('title', 'content')

@admin.register(UserAttempt)
class UserAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'score', 'attempted_at', 'proctor_violations_count')
    list_filter = ('category', 'attempted_at')
    inlines = [UserAttemptDetailInline]

@admin.register(MockInterviewSession)
class MockInterviewSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'started_at', 'is_completed', 'overall_score', 'proctor_violations_count')
    list_filter = ('is_completed', 'started_at')
    inlines = [MockInterviewChatInline]

@admin.register(ProctorLog)
class ProctorLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_type', 'session_id', 'violation_type', 'timestamp')
    list_filter = ('session_type', 'violation_type', 'timestamp')
