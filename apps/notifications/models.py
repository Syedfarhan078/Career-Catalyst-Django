from django.db import models
from django.conf import settings
from django.utils import timezone


class Notification(models.Model):
    """
    Centralized, persistent database-backed notification model.
    Shared by both Student and Mentor workspaces.
    """
    NOTIFICATION_TYPES = [
        ('mentorship_request_submitted', 'Mentorship Request Submitted'),
        ('mentorship_request_accepted', 'Mentorship Request Accepted'),
        ('mentorship_request_rejected', 'Mentorship Request Rejected'),
        ('mentorship_session_completed', 'Mentorship Session Completed'),
        ('mentorship_session_cancelled', 'Mentorship Session Cancelled'),
        ('mentorship_profile_approved', 'Mentorship Profile Approved'),
        ('mentorship_profile_rejected', 'Mentorship Profile Rejected'),
        ('mentorship_profile_blocked', 'Mentorship Profile Blocked'),
        ('mentor_review_received', 'Mentor Review Received'),
        ('general', 'General Notification'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        db_index=True,
        help_text="User receiving the notification."
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications',
        help_text="User who triggered this event (null for system events)."
    )
    notification_type = models.CharField(
        max_length=64,
        choices=NOTIFICATION_TYPES,
        default='general',
        db_index=True
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    target_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="Safe internal URL destination when opening this notification."
    )
    related_request = models.ForeignKey(
        'community.MentorshipRequest',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Associated mentorship request, if applicable."
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
            models.Index(fields=['recipient', '-created_at']),
        ]

    def __str__(self):
        status = "Read" if self.is_read else "Unread"
        return f"[{status}] {self.title} -> {self.recipient.username}"

    def mark_as_read(self):
        """Marks this notification as read and records timestamp."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
