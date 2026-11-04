from urllib.parse import urlparse
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


SAFE_ORIGIN_CONFIG = {
    'dashboard': {
        'label': 'Back to Dashboard',
        'url_name': 'dashboard',
    },
    'my_roadmaps': {
        'label': 'Back to My Roadmaps',
        'url_name': 'roadmaps:my_roadmap',
    },
    'guidance': {
        'label': 'Back to Career Guidance',
        'url_name': 'recommendation:dashboard',
    },
    'catalogue': {
        'label': 'Back to Roadmaps Catalogue',
        'url_name': 'roadmaps:path_list',
    },
    'public_detail': {
        'label': 'Back to Roadmap Overview',
        'url_name': 'roadmaps:path_detail',
    },
    'home': {
        'label': 'Back to Home',
        'url_name': 'home',
    },
}


def get_safe_roadmap_back_navigation(request, default_context='my_roadmaps', path_slug=None):
    """
    Determines safe in-page return navigation for roadmap pages.
    Respects user entry point, account type, and public/private distinction.
    Never redirects to untrusted external URLs or causes open redirects.
    
    Returns:
        tuple (back_url: str, back_label: str)
    """
    # 1. Check explicit query parameter 'from' or 'origin'
    origin_key = (request.GET.get('from') or request.GET.get('origin') or '').strip().lower()
    if origin_key in SAFE_ORIGIN_CONFIG:
        config = SAFE_ORIGIN_CONFIG[origin_key]
        if origin_key == 'public_detail' and path_slug:
            return reverse(config['url_name'], kwargs={'slug': path_slug}), config['label']
        return reverse(config['url_name']), config['label']

    # 2. Check explicit 'return_to' query parameter if present and safely local
    return_to = request.GET.get('return_to', '').strip()
    if return_to and url_has_allowed_host_and_scheme(return_to, allowed_hosts={request.get_host()}, require_https=False):
        parsed = urlparse(return_to)
        p = parsed.path
        if p == reverse('dashboard'):
            return return_to, 'Back to Dashboard'
        elif p.startswith('/recommendation/'):
            return return_to, 'Back to Career Guidance'
        elif p == reverse('roadmaps:my_roadmap'):
            return return_to, 'Back to My Roadmaps'
        elif p == reverse('roadmaps:path_list'):
            return return_to, 'Back to Roadmaps Catalogue'

    # 3. Inspect HTTP Referer if safely on the same host
    referer = request.META.get('HTTP_REFERER', '')
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}, require_https=False):
        ref_path = urlparse(referer).path
        if ref_path == reverse('dashboard'):
            return reverse('dashboard'), 'Back to Dashboard'
        elif ref_path.startswith('/recommendation/'):
            return reverse('recommendation:dashboard'), 'Back to Career Guidance'
        elif ref_path == reverse('roadmaps:my_roadmap'):
            return reverse('roadmaps:my_roadmap'), 'Back to My Roadmaps'
        elif ref_path == reverse('roadmaps:path_list'):
            return reverse('roadmaps:path_list'), 'Back to Roadmaps Catalogue'
        elif path_slug and ref_path == reverse('roadmaps:path_detail', kwargs={'slug': path_slug}):
            return reverse('roadmaps:path_detail', kwargs={'slug': path_slug}), 'Back to Roadmap Overview'

    # 4. Fallback based on default_context
    fallback_config = SAFE_ORIGIN_CONFIG.get(default_context, SAFE_ORIGIN_CONFIG['my_roadmaps'])
    if default_context == 'public_detail' and path_slug:
        return reverse(fallback_config['url_name'], kwargs={'slug': path_slug}), fallback_config['label']
    return reverse(fallback_config['url_name']), fallback_config['label']
