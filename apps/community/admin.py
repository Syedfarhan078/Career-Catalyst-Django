from django.contrib import admin
from .models import (
    ForumCategory, ForumThread, ForumReply, SharedProject, ProjectLike, 
    SuccessStory, MentorMessage, MentorProfile, MentorSkill, 
    MentorshipRequest, MentorReview, MentorAvailability
)

# --- FORUM & SHOWCASE ---
class ForumReplyInline(admin.TabularInline):
    model = ForumReply
    extra = 0

@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(ForumThread)
class ForumThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'author', 'created_at')
    inlines = [ForumReplyInline]

@admin.register(ForumReply)
class ForumReplyAdmin(admin.ModelAdmin):
    list_display = ('thread', 'author', 'created_at')

@admin.register(SharedProject)
class SharedProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')

@admin.register(ProjectLike)
class ProjectLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'liked_at')

@admin.register(SuccessStory)
class SuccessStoryAdmin(admin.ModelAdmin):
    list_display = ('author_name', 'placed_role', 'placed_company', 'grad_year')

@admin.register(MentorMessage)
class MentorMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'sent_at', 'is_read')


# --- MENTOR MARKETPLACE ---
class MentorSkillInline(admin.TabularInline):
    model = MentorSkill
    extra = 0

class MentorAvailabilityInline(admin.TabularInline):
    model = MentorAvailability
    extra = 0

@admin.register(MentorProfile)
class MentorProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'company', 'designation', 'experience_years', 'status', 'verified')
    list_filter = ('status', 'verified', 'company', 'mentorship_type')
    search_fields = ('full_name', 'company', 'designation', 'bio', 'skills')
    inlines = [MentorSkillInline, MentorAvailabilityInline]
    
    actions = ['approve_mentors', 'reject_mentors', 'block_mentors']

    def approve_mentors(self, request, queryset):
        queryset.update(status='Approved', verified=True)
        self.message_user(request, "Selected mentors have been approved and activated.")
    approve_mentors.short_description = "Approve and Verify Selected Mentors"

    def reject_mentors(self, request, queryset):
        queryset.update(status='Rejected', verified=False)
        self.message_user(request, "Selected mentor applications have been rejected.")
    reject_mentors.short_description = "Reject Selected Mentor Applications"

    def block_mentors(self, request, queryset):
        queryset.update(status='Blocked', verified=False)
        self.message_user(request, "Selected mentors have been blocked.")
    block_mentors.short_description = "Block Selected Mentors"


@admin.register(MentorSkill)
class MentorSkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'mentor')
    search_fields = ('name', 'mentor__full_name')


@admin.register(MentorshipRequest)
class MentorshipRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'mentor', 'requested_date', 'requested_time', 'purpose', 'status')
    list_filter = ('status', 'purpose', 'requested_date')
    search_fields = ('student__username', 'mentor__full_name', 'student_message')


@admin.register(MentorReview)
class MentorReviewAdmin(admin.ModelAdmin):
    list_display = ('student', 'mentor', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('student__username', 'mentor__full_name', 'comment')


@admin.register(MentorAvailability)
class MentorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('mentor', 'day', 'start_time', 'end_time', 'max_sessions')
    list_filter = ('day',)
