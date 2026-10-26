from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.conf import settings


class StaticViewSitemap(Sitemap):
    """
    Sitemap for public canonical pages of CareerCatalyst.
    Only includes existing, publicly accessible pages intended for search engines.
    """
    priority = 1.0
    changefreq = 'weekly'
    protocol = getattr(settings, 'CANONICAL_PROTOCOL', 'https')

    def items(self):
        # Only existing, public canonical views that should be indexed by search engines.
        return ['home']

    def location(self, item):
        return reverse(item)

    def get_domain(self, site=None):
        return getattr(settings, 'CANONICAL_HOSTNAME', None) or (site.domain if site else 'career-catalyst-ad5m.onrender.com')


sitemaps = {
    'static': StaticViewSitemap,
}
