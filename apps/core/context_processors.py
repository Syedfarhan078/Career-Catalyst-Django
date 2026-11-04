from django.conf import settings


def canonical_context(request):
    """
    Context processor to provide the configured canonical protocol, hostname,
    and origin for SEO metadata, canonical links, and social graph tags.
    Falls back gracefully to request.get_host() if no canonical host is set.
    """
    protocol = getattr(settings, 'CANONICAL_PROTOCOL', 'https')
    host = getattr(settings, 'CANONICAL_HOSTNAME', None) or request.get_host()
    canonical_origin = f"{protocol}://{host}"

    return {
        'CANONICAL_ORIGIN': canonical_origin,
        'CANONICAL_HOSTNAME': host,
        'CANONICAL_PROTOCOL': protocol,
    }
