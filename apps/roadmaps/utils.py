"""
Utilities for Roadmaps & Certificates:
- In-memory QR code generation using ReportLab QREncoder and Pillow (pure Python, zero extra dependencies).
- Cache-backed rate limiting for public certificate verification endpoints.
"""
import io
import base64
from typing import Optional
from django.core.cache import cache
from reportlab.graphics.barcode import qrencoder
from PIL import Image


def generate_qr_code_base64(data_url: str, box_size: int = 5, border: int = 4) -> str:
    """
    Generates a high-contrast QR code image for data_url in pure Python.
    Returns a data URI string ('data:image/png;base64,...') ready for HTML/xhtml2pdf rendering.
    Performs all operations in-memory without any disk writes or external network requests.
    """
    if not data_url:
        return ""

    qr = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.M)
    qr.addData(data_url)
    qr.make()

    matrix = qr.modules
    n = len(matrix)
    img_size = (n + 2 * border) * box_size
    img = Image.new('RGB', (img_size, img_size), 'white')
    pixels = img.load()

    for r in range(n):
        for c in range(n):
            if matrix[r][c]:
                for dr in range(box_size):
                    for dc in range(box_size):
                        pixels[(c + border) * box_size + dc, (r + border) * box_size + dr] = (15, 23, 42) # Deep slate/navy

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    b64_data = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f"data:image/png;base64,{b64_data}"


def get_client_ip(request) -> str:
    """Extracts client IP address safely from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip or '127.0.0.1'


def is_rate_limited(request, key_prefix: str = "cert_verify", max_requests: int = 30, window_seconds: int = 60) -> bool:
    """
    Determines if request exceeds rate limit using Django cache backend.
    Returns True if rate-limited (blocked), False if permitted.
    """
    ip = get_client_ip(request)
    cache_key = f"{key_prefix}:{ip}"
    try:
        current_count = cache.get(cache_key)
        if current_count is None:
            cache.set(cache_key, 1, timeout=window_seconds)
            return False
        if current_count >= max_requests:
            return True
        cache.incr(cache_key)
        return False
    except Exception:
        # Fail open if cache is unavailable
        return False
