def workspace_context(request):
    """
    Context processor providing active workspace and mentor status to all templates.
    Validates active_role session values against backend mentor authorization.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'is_approved_mentor': False,
            'active_workspace': 'student',
        }

    is_approved_mentor = bool(
        hasattr(user, 'mentor_profile') and
        user.mentor_profile.status == 'Approved' and
        user.mentor_profile.verified
    )

    session = getattr(request, 'session', {})
    active_role = session.get('active_role', 'student') if hasattr(session, 'get') else 'student'
    if active_role == 'mentor' and not is_approved_mentor:
        active_role = 'student'
        if hasattr(session, '__setitem__'):
            session['active_role'] = 'student'

    return {
        'is_approved_mentor': is_approved_mentor,
        'active_workspace': active_role,
    }
