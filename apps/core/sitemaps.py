from datetime import datetime
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.conf import settings
from apps.roadmaps.models import CareerPath
from apps.core.guides_data import get_all_guides


class StaticViewSitemap(Sitemap):
    """
    Sitemap for public canonical pages of CareerCatalyst.
    Only includes existing, publicly accessible pages intended for search engines.
    """
    priority = 1.0
    changefreq = 'weekly'
    protocol = getattr(settings, 'CANONICAL_PROTOCOL', 'https')

    def items(self):
        # Public canonical views intended for search engines.
        return ['home', 'roadmaps:path_list']

    def location(self, item):
        return reverse(item)

    def get_domain(self, site=None):
        return getattr(settings, 'CANONICAL_HOSTNAME', None) or (site.domain if site else 'career-catalyst-ad5m.onrender.com')


class RoadmapSitemap(Sitemap):
    """
    Sitemap for public, active curriculum roadmaps.
    Excludes private learning consoles, enrollments, and progress APIs.
    """
    priority = 0.8
    changefreq = 'weekly'
    protocol = getattr(settings, 'CANONICAL_PROTOCOL', 'https')

    def items(self):
        return CareerPath.objects.filter(is_active=True).order_by('name')

    def location(self, obj):
        return reverse('roadmaps:path_detail', kwargs={'slug': obj.slug})

    def get_domain(self, site=None):
        return getattr(settings, 'CANONICAL_HOSTNAME', None) or (site.domain if site else 'career-catalyst-ad5m.onrender.com')


class CareerGuideSitemap(Sitemap):
    """
    Sitemap for public career guides and editorial content hub.
    Includes the career guides catalogue and individual published articles.
    """
    priority = 0.8
    changefreq = 'weekly'
    protocol = getattr(settings, 'CANONICAL_PROTOCOL', 'https')

    def items(self):
        items_list = ['guide_list']
        items_list.extend(get_all_guides())
        return items_list

    def location(self, item):
        if item == 'guide_list':
            return reverse('guide_list')
        return reverse('guide_detail', kwargs={'slug': item['slug']})

    def lastmod(self, item):
        if item == 'guide_list':
            guides = get_all_guides()
            if guides:
                latest = max(g.get('modified_date', '2026-04-01T00:00:00Z') for g in guides)
                return datetime.fromisoformat(latest.replace('Z', '+00:00'))
            return None
        mod_date = item.get('modified_date')
        if mod_date:
            return datetime.fromisoformat(mod_date.replace('Z', '+00:00'))
        return None

    def get_domain(self, site=None):
        return getattr(settings, 'CANONICAL_HOSTNAME', None) or (site.domain if site else 'career-catalyst-ad5m.onrender.com')


sitemaps = {
    'static': StaticViewSitemap,
    'roadmaps': RoadmapSitemap,
    'career_guides': CareerGuideSitemap,
}
