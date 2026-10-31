def workspace_context(request):
    """
    Context processor providing active workspace and mentor status to all templates.
    Strictly derives active_workspace from User.role. Session active_role is normalized.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'is_approved_mentor': False,
            'active_workspace': 'student',
        }

    role = getattr(user, 'role', 'student')
    session = getattr(request, 'session', {})

    if role == 'mentor':
        is_approved_mentor = bool(
            hasattr(user, 'mentor_profile') and
            user.mentor_profile.status == 'Approved' and
            user.mentor_profile.verified
        )
        active_workspace = 'mentor'
        if hasattr(session, '__setitem__') and session.get('active_role') != 'mentor':
            session['active_role'] = 'mentor'
    else:
        is_approved_mentor = False
        active_workspace = 'student'
        if hasattr(session, '__setitem__') and session.get('active_role') != 'student':
            session['active_role'] = 'student'

    return {
        'is_approved_mentor': is_approved_mentor,
        'active_workspace': active_workspace,
    }
