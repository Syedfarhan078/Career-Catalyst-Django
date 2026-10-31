from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Notification
from .services import (
    mark_notification_as_read,
    mark_all_notifications_as_read,
    get_unread_count,
)


@login_required
def notification_history_view(request):
    """
    Dedicated Notification History page.
    Displays user notifications with pagination, read/unread filters, and actions.
    Strictly restricted to request.user's own records.
    """
    filter_type = request.GET.get('filter', 'all')
    notifications_qs = Notification.objects.filter(recipient=request.user).select_related('actor', 'related_request')

    if filter_type == 'unread':
        notifications_qs = notifications_qs.filter(is_read=False)

    paginator = Paginator(notifications_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    unread_count = get_unread_count(request.user)

    return render(request, "notifications/history.html", {
        "page_obj": page_obj,
        "filter_type": filter_type,
        "unread_count": unread_count,
        "total_count": paginator.count,
    })


@login_required
def unread_count_api(request):
    """
    Lightweight endpoint returning current unread notification count.
    Used for frontend polling/syncing.
    """
    return JsonResponse({
        "unread_count": get_unread_count(request.user)
    })


@login_required
@require_POST
def mark_as_read_view(request, notification_id):
    """
    Marks a single notification as read, enforcing strict ownership.
    Supports both AJAX and standard POST submissions.
    """
    notification = mark_notification_as_read(notification_id, request.user)
    if not notification:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({"error": "Notification not found or unauthorized."}, status=404)
        messages.error(request, "Notification not found or access denied.")
        return redirect('notifications:history')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({
            "success": True,
            "notification_id": notification_id,
            "unread_count": get_unread_count(request.user)
        })

    # Validate next redirect url to prevent open-redirect vulnerabilities
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    return redirect('notifications:history')


@login_required
@require_POST
def mark_all_as_read_view(request):
    """
    Marks all unread notifications for the authenticated user as read.
    """
    count = mark_all_notifications_as_read(request.user)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({
            "success": True,
            "updated_count": count,
            "unread_count": 0
        })

    messages.success(request, f"Marked {count} notification(s) as read.")
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    return redirect('notifications:history')
