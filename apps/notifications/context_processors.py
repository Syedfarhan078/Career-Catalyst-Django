from .services import get_unread_count, get_recent_notifications


def notification_context(request):
    """
    Context processor providing unread notification count and recent notifications
    to all authenticated views and templates.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'unread_notifications_count': 0,
            'recent_notifications': [],
        }

    return {
        'unread_notifications_count': get_unread_count(user),
        'recent_notifications': get_recent_notifications(user, limit=5),
    }
