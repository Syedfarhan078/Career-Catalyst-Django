"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from django.contrib.sitemaps.views import sitemap

from apps.roadmaps.views import verify_certificate
from apps.core.sitemaps import sitemaps
from apps.core.views import robots_txt

urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('admin-portal/', admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("profile/", include("apps.profiles.urls")),
    path("resume/", include("apps.resume.urls")),
    path("ai-resume/", include("apps.ai_resume.urls")),
    path("roadmaps/", include("apps.roadmaps.urls")),
    path("verify/<str:certificate_id>/", verify_certificate, name='public_verify_certificate'),
    path("interviews/", include("apps.interviews.urls")),
    path("community/", include("apps.community.urls")),
    path("recommendation/", include("apps.recommendation.urls")),
    path("tracker/", include("apps.tracker.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("", include("apps.core.urls")),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
