import logging
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Notification

logger = logging.getLogger(__name__)
User = get_user_model()


def create_notification(
    recipient,
    title,
    message,
    actor=None,
    notification_type='general',
    target_url='',
    related_request=None,
    deduplicate_seconds=60
):
    """
    Central service for creating database-backed notifications.
    Enforces validation, actor != recipient checks, and duplicate-prevention.
    """
    if not recipient:
        raise ValidationError("Notification recipient must be specified.")

    if not recipient.is_active:
        logger.warning(f"Skipping notification for inactive user ID {recipient.pk}")
        return None

    # Do not send notification if recipient is the actor (prevent self-notifications)
    if actor and actor == recipient:
        logger.info(f"Skipping self-notification for user ID {recipient.pk}")
        return None

    # Deduplication check:
    # If an identical unread notification was created within deduplicate_seconds, avoid duplicating
    if deduplicate_seconds and deduplicate_seconds > 0:
        recent_threshold = timezone.now() - timedelta(seconds=deduplicate_seconds)
        duplicate_filter = {
            'recipient': recipient,
            'notification_type': notification_type,
            'is_read': False,
            'created_at__gte': recent_threshold,
        }
        if related_request:
            duplicate_filter['related_request'] = related_request
        if actor:
            duplicate_filter['actor'] = actor

        existing = Notification.objects.filter(**duplicate_filter).first()
        if existing:
            logger.info(f"Duplicate notification suppressed for {recipient.username} ({notification_type})")
            return existing

    notification = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        title=title,
        message=message,
        target_url=target_url or '',
        related_request=related_request,
        is_read=False,
    )
    logger.info(f"[NOTIFICATION CREATED] id={notification.id} to={recipient.username} type={notification_type}")
    return notification


def mark_notification_as_read(notification_id, user):
    """
    Marks a single notification as read, strictly enforcing recipient ownership.
    Returns the updated notification, or None if not found/unauthorized.
    """
    if not user or not user.is_authenticated:
        return None

    try:
        notification = Notification.objects.get(id=notification_id, recipient=user)
        notification.mark_as_read()
        return notification
    except Notification.DoesNotExist:
        return None


def mark_all_notifications_as_read(user):
    """
    Marks all unread notifications for a user as read.
    Returns the count of updated notifications.
    """
    if not user or not user.is_authenticated:
        return 0

    now = timezone.now()
    count = Notification.objects.filter(recipient=user, is_read=False).update(
        is_read=True,
        read_at=now
    )
    return count


def get_unread_count(user):
    """
    Returns unread notifications count for a user.
    """
    if not user or not user.is_authenticated:
        return 0
    return Notification.objects.filter(recipient=user, is_read=False).count()


def get_recent_notifications(user, limit=5):
    """
    Returns recent notifications for navbar dropdown, ordered newest first.
    """
    if not user or not user.is_authenticated:
        return Notification.objects.none()
    return Notification.objects.filter(recipient=user).select_related('actor', 'related_request')[:limit]
