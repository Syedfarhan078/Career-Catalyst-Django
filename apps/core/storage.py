import os
import time
import requests
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.exceptions import ImproperlyConfigured

try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.utils
    from cloudinary_storage.storage import MediaCloudinaryStorage, RESOURCE_TYPES
except (ImportError, ImproperlyConfigured):
    cloudinary = None
    MediaCloudinaryStorage = None
    RESOURCE_TYPES = {'IMAGE': 'image', 'RAW': 'raw', 'VIDEO': 'video'}

_BaseStorage = MediaCloudinaryStorage if MediaCloudinaryStorage is not None else FileSystemStorage


class CareerCatalystPublicMediaStorage(_BaseStorage):
    """
    Dedicated public storage backend for non-sensitive public assets (profile pictures, photos).
    Uses Cloudinary 'upload' delivery type.
    """
    IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
        '.ico', '.bmp', '.tiff', '.tif', '.avif', '.heic'
    }

    def _get_resource_type(self, name):
        ext = os.path.splitext(name or '')[1].lower()
        if ext in self.IMAGE_EXTENSIONS:
            return RESOURCE_TYPES.get('IMAGE', 'image')
        return RESOURCE_TYPES.get('RAW', 'raw')

    def _upload(self, name, content):
        if not cloudinary:
            return super()._upload(name, content)
        options = {
            'use_filename': True,
            'resource_type': self._get_resource_type(name),
            'type': 'upload',
            'tags': getattr(self, 'TAG', None),
        }
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        return cloudinary.uploader.upload(content, **options)

    def url(self, name):
        if not cloudinary:
            return super().url(name)
        return self._get_url(name) if hasattr(self, '_get_url') else super().url(name)

    def exists(self, name):
        if not cloudinary or not getattr(settings, 'USE_CLOUDINARY', False):
            return super().exists(name)
        try:
            pub_url = self.url(name)
            resp = requests.head(pub_url, timeout=5)
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except Exception:
            return False


class CareerCatalystPrivateMediaStorage(_BaseStorage):
    """
    Dedicated private storage backend for sensitive documents (resumes, CVs).
    Enforces Cloudinary 'authenticated' access type and 'raw' resource type.
    Anonymous public CDN access without a valid cryptographic signature is rejected.
    """
    def _get_resource_type(self, name):
        return RESOURCE_TYPES.get('RAW', 'raw')

    def _upload(self, name, content):
        if not cloudinary:
            return super()._upload(name, content)
        options = {
            'use_filename': True,
            'resource_type': 'raw',
            'type': 'authenticated',
            'tags': getattr(self, 'TAG', None),
        }
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        return cloudinary.uploader.upload(content, **options)

    def url(self, name):
        """
        Generates a signed authenticated URL for the asset.
        Unsigned public delivery is completely disabled.
        """
        if not cloudinary:
            return super().url(name)
        clean_name = self._prepend_prefix(name) if hasattr(self, '_prepend_prefix') else name
        signed_url, _ = cloudinary.utils.cloudinary_url(
            clean_name,
            resource_type='raw',
            type='authenticated',
            sign_url=True
        )
        return signed_url

    def generate_expiring_url(self, name, expires_in=300):
        """
        Generates an expiring signed download URL via Cloudinary private_download_url.
        """
        if not cloudinary:
            return self.url(name)
        clean_name = self._prepend_prefix(name) if hasattr(self, '_prepend_prefix') else name
        clean_name = (clean_name or '').replace('\\', '/')
        ext = os.path.splitext(clean_name)[1].lstrip('.').lower() or 'pdf'
        public_id = os.path.splitext(clean_name)[0]
        expires_at = int(time.time()) + expires_in
        return cloudinary.utils.private_download_url(
            public_id,
            ext,
            resource_type='raw',
            type='authenticated',
            expires_at=expires_at
        )

    def exists(self, name):
        if not cloudinary or not getattr(settings, 'USE_CLOUDINARY', False):
            return super().exists(name)
        try:
            signed_url = self.url(name)
            resp = requests.head(signed_url, timeout=5)
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except Exception:
            return False


class CareerCatalystMediaCloudinaryStorage(_BaseStorage):
    """
    Intelligent unified Cloudinary storage router for CareerCatalyst.
    Enforces strict separation between public media and private documents:
    - Public pictures (profile_pictures/, mentor_photos/):
      resource_type='image', delivery_type='upload' (public CDN)
    - Private documents (resumes/, mentor_resumes/):
      resource_type='raw', delivery_type='authenticated' (signed-only access; unsigned CDN access rejected)
    """
    IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
        '.ico', '.bmp', '.tiff', '.tif', '.avif', '.heic'
    }
    PRIVATE_PREFIXES = ('resumes/', 'mentor_resumes/')

    def is_private_asset(self, name):
        normalized = (name or '').replace('\\', '/').lstrip('/')
        return any(normalized.startswith(prefix) for prefix in self.PRIVATE_PREFIXES)

    def _get_resource_type(self, name):
        if self.is_private_asset(name):
            return RESOURCE_TYPES.get('RAW', 'raw')
        ext = os.path.splitext(name or '')[1].lower()
        if ext in self.IMAGE_EXTENSIONS:
            return RESOURCE_TYPES.get('IMAGE', 'image')
        return RESOURCE_TYPES.get('RAW', 'raw')

    def _upload(self, name, content):
        if not cloudinary:
            return super()._upload(name, content)
        delivery_type = 'authenticated' if self.is_private_asset(name) else 'upload'
        resource_type = self._get_resource_type(name)
        options = {
            'use_filename': True,
            'resource_type': resource_type,
            'type': delivery_type,
            'tags': getattr(self, 'TAG', None),
        }
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        return cloudinary.uploader.upload(content, **options)

    def url(self, name):
        if not cloudinary:
            return super().url(name)
        if self.is_private_asset(name):
            clean_name = self._prepend_prefix(name) if hasattr(self, '_prepend_prefix') else name
            signed_url, _ = cloudinary.utils.cloudinary_url(
                clean_name,
                resource_type='raw',
                type='authenticated',
                sign_url=True
            )
            return signed_url
        return self._get_url(name) if hasattr(self, '_get_url') else super().url(name)

    def generate_expiring_url(self, name, expires_in=300):
        if not cloudinary:
            return self.url(name)
        clean_name = self._prepend_prefix(name) if hasattr(self, '_prepend_prefix') else name
        clean_name = (clean_name or '').replace('\\', '/')
        ext = os.path.splitext(clean_name)[1].lstrip('.').lower() or 'pdf'
        public_id = os.path.splitext(clean_name)[0]
        expires_at = int(time.time()) + expires_in
        return cloudinary.utils.private_download_url(
            public_id,
            ext,
            resource_type='raw',
            type='authenticated',
            expires_at=expires_at
        )

    def exists(self, name):
        if not cloudinary or not getattr(settings, 'USE_CLOUDINARY', False):
            return super().exists(name)
        try:
            target_url = self.url(name)
            resp = requests.head(target_url, timeout=5)
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except Exception:
            return False


def get_public_storage():
    """Returns the dedicated public media storage backend."""
    if getattr(settings, 'USE_CLOUDINARY', False):
        return CareerCatalystPublicMediaStorage()
    return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)


def get_private_storage():
    """Returns the dedicated private media storage backend."""
    if getattr(settings, 'USE_CLOUDINARY', False):
        return CareerCatalystPrivateMediaStorage()
    return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
