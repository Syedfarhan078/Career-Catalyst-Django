"""
Proctoring Audit Service for CareerCatalyst.

Transforms proctoring from client-trusted score manipulation into a secure,
rate-limited, server-audited integrity tracking system.
Distinguishes client-reported events from server-verified telemetry, defends
against database flooding, and computes audit integrity summaries without docking
candidate performance scores arbitrarily.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

from apps.interviews.models import ProctorLog, QuizSession, MockInterviewSession


class ProctorAuditService:
    RATE_LIMIT_WINDOW_SECONDS = 60
    MAX_EVENTS_PER_WINDOW = 12

    VALID_SESSION_TYPES = {'Quiz', 'MockInterview', 'Coding'}

    @classmethod
    def record_violation(
        cls,
        user,
        session_type: str,
        session_id: int,
        violation_type: str,
        source: str = 'CLIENT_REPORTED'
    ) -> Tuple[bool, str]:
        """
        Validates, rate-limits, and records an integrity event.
        Returns (success, message).
        """
        if not user or not user.is_authenticated:
            return False, "Authentication required."

        if session_type not in cls.VALID_SESSION_TYPES:
            return False, f"Invalid session_type '{session_type}'."

        if not session_id or not isinstance(session_id, int):
            try:
                session_id = int(session_id)
            except (ValueError, TypeError):
                return False, "Invalid session_id."

        clean_violation = (violation_type or "").strip()
        if not clean_violation:
            return False, "Violation type cannot be empty."

        # Enforce rate-limiting using cache
        cache_key = f"proctor_ratelimit_{user.id}_{session_type}_{session_id}"
        event_count = cache.get(cache_key, 0)
        if event_count >= cls.MAX_EVENTS_PER_WINDOW:
            # Drop silently or reject to protect database
            return False, "Rate limit exceeded for proctoring telemetry."

        cache.set(cache_key, event_count + 1, timeout=cls.RATE_LIMIT_WINDOW_SECONDS)

        # Verify session ownership if possible
        if session_type == 'MockInterview':
            session_obj = MockInterviewSession.objects.filter(id=session_id).first()
            if session_obj and session_obj.user_id != user.id:
                return False, "Session does not belong to the authenticated user."
        elif session_type == 'Quiz':
            # session_id could be category_id (legacy) or QuizSession.id
            pass

        ProctorLog.objects.create(
            user=user,
            session_type=session_type,
            session_id=session_id,
            violation_type=clean_violation[:100],
            source=source
        )

        return True, "Integrity event recorded."

    @classmethod
    def get_session_integrity_report(
        cls,
        user,
        session_type: str,
        session_id: int
    ) -> Dict[str, Any]:
        """
        Aggregates proctoring telemetry for audit review without penalizing candidate scores.
        """
        logs = ProctorLog.objects.filter(
            user=user,
            session_type=session_type,
            session_id=session_id
        ).order_by('timestamp')

        total_count = logs.count()
        type_breakdown: Dict[str, int] = {}
        for l in logs:
            type_breakdown[l.violation_type] = type_breakdown.get(l.violation_type, 0) + 1

        if total_count >= 7:
            integrity_level = "High Anomaly Count"
            integrity_badge = "danger"
            description = "Multiple window blur or focus change events logged. Review recommended."
        elif total_count >= 3:
            integrity_level = "Noticeable Anomaly"
            integrity_badge = "warning"
            description = "A few focus changes detected during the session."
        else:
            integrity_level = "Standard Integrity"
            integrity_badge = "success"
            description = "Session executed within normal focus and interaction parameters."

        return {
            "total_events": total_count,
            "integrity_level": integrity_level,
            "integrity_badge": integrity_badge,
            "description": description,
            "type_breakdown": type_breakdown
        }
