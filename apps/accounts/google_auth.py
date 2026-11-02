# apps/accounts/google_auth.py
"""
Google OAuth 2.0 and OpenID Connect Service for CareerCatalyst.
Implements:
- Authorization URL generation with PKCE (S256), state, and OIDC nonce
- Authorization-code exchange via server-side HTTP POST
- Cryptographic ID-token validation using Google's JWKS and cryptography library
- Normalized email matching and persistent GoogleIdentity association
- Atomic account linking and role-enforced account creation
"""

import base64
import hashlib
import json
import logging
import re
import secrets
import time
import urllib.parse
from datetime import timedelta

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import EmailOTP, GoogleIdentity

logger = logging.getLogger(__name__)
User = get_user_model()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]

# In-memory cache for Google JWKS public keys
_JWKS_CACHE = {
    "keys": {},
    "expires_at": 0,
}


def normalize_google_email(email: str) -> str:
    """Consistently normalizes email addresses by trimming and lowercasing."""
    if not email:
        return ""
    return email.strip().lower()


def generate_oauth_state() -> str:
    """Generates a cryptographically secure random state parameter."""
    return secrets.token_urlsafe(32)


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generates a cryptographically secure PKCE verifier and S256 challenge.
    Returns (code_verifier, code_challenge).
    """
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def generate_oauth_nonce() -> str:
    """Generates a cryptographically secure OpenID Connect nonce."""
    return secrets.token_urlsafe(32)


def get_google_redirect_uri(request) -> str:
    """
    Constructs the exact absolute callback URI for Google OAuth.
    Preserves HTTPS behind reverse proxies and production environments.
    """
    callback_path = reverse("google_callback")
    uri = request.build_absolute_uri(callback_path)

    # Enforce HTTPS if behind SSL termination, Render, or in production
    is_secure = (
        request.is_secure()
        or request.headers.get("x-forwarded-proto") == "https"
        or not settings.DEBUG
    )
    if is_secure and uri.startswith("http://") and not (
        "127.0.0.1" in uri or "localhost" in uri
    ):
        uri = "https://" + uri[len("http://"):]

    return uri


def get_google_authorization_url(request, role: str = None) -> str:
    """
    Generates the Google OAuth authorization URL, storing state, PKCE verifier,
    OIDC nonce, and optional pending role in the server-side session.
    """
    state = generate_oauth_state()
    verifier, challenge = generate_pkce_pair()
    nonce = generate_oauth_nonce()

    request.session["oauth_state"] = state
    request.session["oauth_code_verifier"] = verifier
    request.session["oauth_nonce"] = nonce
    request.session["oauth_created_at"] = time.time()

    if role in ["student", "mentor"]:
        request.session["oauth_pending_role"] = role
    else:
        request.session.pop("oauth_pending_role", None)

    redirect_uri = get_google_redirect_uri(request)

    params = {
        "client_id": getattr(settings, "GOOGLE_CLIENT_ID", ""),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }

    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(code: str, code_verifier: str, redirect_uri: str) -> dict:
    """
    Exchanges an authorization code for tokens via server-side POST.
    Includes explicit timeouts, error handling, and safe logging.
    """
    payload = {
        "code": code,
        "client_id": getattr(settings, "GOOGLE_CLIENT_ID", ""),
        "client_secret": getattr(settings, "GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data=payload,
            timeout=10,
            headers={"Accept": "application/json"},
        )
    except requests.RequestException as e:
        logger.error("Network error during Google token exchange: %s", type(e).__name__)
        raise ValidationError("Failed to communicate with Google authentication servers. Please try again.")

    if response.status_code != 200:
        logger.warning("Google token exchange returned status %s", response.status_code)
        raise ValidationError("Google authorization code exchange failed. Please try signing in again.")

    try:
        token_data = response.json()
    except ValueError:
        raise ValidationError("Invalid response received from Google authentication servers.")

    if "id_token" not in token_data:
        raise ValidationError("Google did not return an OpenID Connect ID token.")

    return token_data


def _base64url_decode(input_str: str) -> bytes:
    """Decodes base64url-encoded string with appropriate padding."""
    rem = len(input_str) % 4
    if rem > 0:
        input_str += "=" * (4 - rem)
    return base64.urlsafe_b64decode(input_str)


def fetch_jwks_keys(force_refresh: bool = False) -> dict:
    """
    Fetches and caches Google's JWKS public keys.
    Returns a dictionary mapping kid to key data.
    """
    global _JWKS_CACHE
    now = time.time()

    if not force_refresh and _JWKS_CACHE["keys"] and now < _JWKS_CACHE["expires_at"]:
        return _JWKS_CACHE["keys"]

    try:
        response = requests.get(GOOGLE_JWKS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        keys_by_kid = {k["kid"]: k for k in data.get("keys", []) if "kid" in k}
        _JWKS_CACHE = {
            "keys": keys_by_kid,
            "expires_at": now + 3600,  # Cache for 1 hour
        }
        return keys_by_kid
    except Exception as e:
        logger.error("Failed to fetch Google JWKS: %s", type(e).__name__)
        if _JWKS_CACHE["keys"]:
            return _JWKS_CACHE["keys"]
        raise ValidationError("Unable to verify Google token signatures. Could not fetch public keys.")


def verify_google_id_token(
    id_token: str,
    expected_nonce: str,
    client_id: str = None,
    jwks_keys: dict = None,
) -> dict:
    """
    Cryptographically verifies a Google OpenID Connect ID token:
    1. Signature verification against Google JWKS (RS256 via cryptography)
    2. Issuer validation (accounts.google.com or https://accounts.google.com)
    3. Audience validation (matches GOOGLE_CLIENT_ID)
    4. Expiration and issued-at time claims
    5. Nonce match against session nonce
    6. Verified email claim presence and truth
    """
    if not id_token or not isinstance(id_token, str):
        raise ValidationError("Missing or invalid ID token.")

    parts = id_token.split(".")
    if len(parts) != 3:
        raise ValidationError("Malformed ID token: incorrect number of segments.")

    header_b64, payload_b64, sig_b64 = parts

    try:
        header = json.loads(_base64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_base64url_decode(payload_b64).decode("utf-8"))
        signature_bytes = _base64url_decode(sig_b64)
    except Exception:
        raise ValidationError("Failed to decode ID token segments.")

    if header.get("alg") != "RS256":
        raise ValidationError(f"Unsupported ID token algorithm: {header.get('alg')}")

    kid = header.get("kid")
    if not kid:
        raise ValidationError("ID token missing 'kid' header parameter.")

    # Retrieve JWKS keys
    if jwks_keys is None:
        keys = fetch_jwks_keys()
        if kid not in keys:
            # Attempt forced refresh for key rotation
            keys = fetch_jwks_keys(force_refresh=True)
    else:
        keys = jwks_keys

    key_data = keys.get(kid)
    if not key_data:
        raise ValidationError("Matching public key for ID token not found in Google JWKS.")

    # Reconstruct RSA public key
    try:
        n_int = int.from_bytes(_base64url_decode(key_data["n"]), "big")
        e_int = int.from_bytes(_base64url_decode(key_data["e"]), "big")
        public_key = rsa.RSAPublicNumbers(e_int, n_int).public_key()
    except Exception as e:
        raise ValidationError(f"Failed to reconstruct RSA public key: {str(e)}")

    # Cryptographic RS256 signature verification
    signed_bytes = f"{header_b64}.{payload_b64}".encode("ascii")
    try:
        public_key.verify(
            signature_bytes,
            signed_bytes,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except Exception:
        raise ValidationError("ID token cryptographic signature verification failed.")

    # Validate claims
    target_client_id = client_id or getattr(settings, "GOOGLE_CLIENT_ID", "")
    now = time.time()

    # Issuer check
    if payload.get("iss") not in GOOGLE_ISSUERS:
        raise ValidationError(f"Invalid ID token issuer: {payload.get('iss')}")

    # Audience check
    token_aud = payload.get("aud")
    if isinstance(token_aud, list):
        if target_client_id not in token_aud:
            raise ValidationError(f"Target client ID not in token audiences: {token_aud}")
        # Multi-audience token requires valid azp claim per OIDC Core 3.1.3.7
        azp = payload.get("azp")
        if not azp or not isinstance(azp, str):
            raise ValidationError("ID token with multiple audiences missing valid 'azp' claim.")
        if not secrets.compare_digest(azp, target_client_id):
            raise ValidationError(f"Invalid ID token authorized party (azp): {azp}")
    elif isinstance(token_aud, str):
        if not secrets.compare_digest(token_aud, target_client_id):
            raise ValidationError(f"Invalid ID token audience: {token_aud}")
    else:
        raise ValidationError("Invalid or missing ID token audience.")

    # Explicit azp check if azp claim is present (single or multi-audience)
    if "azp" in payload:
        azp = payload.get("azp")
        if not isinstance(azp, str) or not azp.strip():
            raise ValidationError("Malformed 'azp' claim in ID token.")
        if not secrets.compare_digest(azp, target_client_id):
            raise ValidationError(f"Invalid ID token authorized party (azp): {azp}")

    # Expiration check (with 30-second leeway)
    exp = payload.get("exp", 0)
    if not isinstance(exp, (int, float)):
        raise ValidationError("Malformed expiration (exp) claim in ID token.")
    if now > exp + 30:
        raise ValidationError("ID token has expired.")

    # Issued-at check (with 30-second future leeway)
    iat = payload.get("iat", 0)
    if not isinstance(iat, (int, float)):
        raise ValidationError("Malformed issued-at (iat) claim in ID token.")
    if iat > now + 30:
        raise ValidationError("ID token issued at a future date.")

    # Nonce check (Must fail closed)
    if not expected_nonce or not isinstance(expected_nonce, str) or not expected_nonce.strip():
        raise ValidationError("Missing or empty expected nonce for ID token verification.")

    token_nonce = payload.get("nonce")
    if not token_nonce or not isinstance(token_nonce, str):
        raise ValidationError("ID token missing nonce claim.")

    if not secrets.compare_digest(token_nonce, expected_nonce):
        raise ValidationError("ID token nonce does not match session nonce.")

    # Subject check
    if not payload.get("sub"):
        raise ValidationError("ID token missing subject (sub) claim.")

    # Email claims
    email = payload.get("email")
    if not email:
        raise ValidationError("ID token does not contain an email address.")

    email_verified = payload.get("email_verified")
    if email_verified is not True:
        raise ValidationError("Google email address is not verified.")

    return payload


def get_google_user_info(access_token: str) -> dict:
    """
    Optionally retrieves profile info from Google's UserInfo endpoint.
    """
    try:
        response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning("Failed to fetch Google userinfo: %s", type(e).__name__)
        return {}


def generate_unique_username(base_name: str) -> str:
    """
    Generates a clean, unique alphanumeric username conforming to AbstractUser.
    Appends numeric suffixes if collisions occur.
    """
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "", base_name).strip("._-")
    if not clean:
        clean = "user"

    # Truncate base to ensure room for suffix within max_length=150
    base = clean[:130]
    candidate = base

    suffix = 1
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base}_{suffix}"
        suffix += 1

    return candidate


def authenticate_or_register_google_user(
    request,
    google_data: dict,
    role: str = None,
) -> tuple[str, User | None, str | None]:
    """
    Central authentication authority for Google identities:
    1. Checks persistent GoogleIdentity by provider_user_id (sub).
    2. If absent, matches verified email against existing User records.
       - Exactly 1 match: checks activation, links GoogleIdentity atomically, logs in.
       - > 1 matches: halts and reports safe error.
    3. If no matching User:
       - If role is provided ('student' or 'mentor'): creates User and GoogleIdentity atomically, logs in.
       - If no role is provided: returns ('needs_role', None, None) to prompt role selection.

    Returns:
        (status, user, error_message)
        where status is one of: 'authenticated', 'created', 'needs_role', 'error'
    """
    sub = google_data.get("sub")
    raw_email = google_data.get("email", "")
    email = normalize_google_email(raw_email)
    given_name = google_data.get("given_name", "") or google_data.get("name", "")
    family_name = google_data.get("family_name", "")

    if not sub:
        return "error", None, "Missing Google subject identifier."
    if not email:
        return "error", None, "Missing verified Google email address."

    # ---------------------------------------------------------
    # 1. Lookup Persistent GoogleIdentity
    # ---------------------------------------------------------
    identity = (
        GoogleIdentity.objects.filter(provider="google", provider_user_id=sub)
        .select_related("user")
        .first()
    )

    if identity:
        user = identity.user
        # Account eligibility checks
        if not user.is_active:
            with transaction.atomic():
                # Check for incomplete registration OTP
                unexpired_otp = (
                    EmailOTP.objects.filter(user=user, is_verified=False)
                    .order_by("-created_at")
                    .first()
                )
                if unexpired_otp and not unexpired_otp.is_expired():
                    # Legitimate incomplete signup recovered via verified Google identity
                    user.is_active = True
                    user.save(update_fields=["is_active"])
                    EmailOTP.objects.filter(user=user).delete()
                else:
                    return (
                        "error",
                        None,
                        "This account has been deactivated. Please contact support for assistance.",
                    )

        user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, user)
        return "authenticated", user, None

    # ---------------------------------------------------------
    # 2. Check Existing Account by Normalized Email
    # ---------------------------------------------------------
    matching_users = User.objects.filter(email__iexact=email)
    count = matching_users.count()

    if count > 1:
        logger.warning(
            "Multiple accounts found matching normalized email during Google linking: count=%d",
            count,
        )
        return (
            "error",
            None,
            "Multiple accounts found with this email address. Please sign in with your username and password, or contact support.",
        )

    if count == 1:
        user = matching_users.first()

        # Atomic account activation and GoogleIdentity linking
        with transaction.atomic():
            # Ensure user does not already have a different google identity
            if GoogleIdentity.objects.filter(user=user, provider="google").exists():
                return (
                    "error",
                    None,
                    "This account is already linked to a different Google identity.",
                )
            if GoogleIdentity.objects.filter(provider="google", provider_user_id=sub).exists():
                return (
                    "error",
                    None,
                    "This Google account is already linked to another user.",
                )

            # Account activation check inside the atomic transaction
            if not user.is_active:
                unexpired_otp = (
                    EmailOTP.objects.filter(user=user, is_verified=False)
                    .order_by("-created_at")
                    .first()
                )
                if unexpired_otp and not unexpired_otp.is_expired():
                    user.is_active = True
                    user.save(update_fields=["is_active"])
                    EmailOTP.objects.filter(user=user).delete()
                else:
                    return (
                        "error",
                        None,
                        "This account has been deactivated. Please contact support for assistance.",
                    )

            GoogleIdentity.objects.create(
                user=user,
                provider="google",
                provider_user_id=sub,
                email_at_link=email,
            )

        user.backend = "django.contrib.auth.backends.ModelBackend"
        login(request, user)
        return "authenticated", user, None

    # ---------------------------------------------------------
    # 3. New User Flow
    # ---------------------------------------------------------
    if not role or role not in ["student", "mentor"]:
        return "needs_role", None, None

    with transaction.atomic():
        # Handle concurrent registration race condition
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            if not existing_user.is_active:
                return (
                    "error",
                    None,
                    "This account has been deactivated. Please contact support.",
                )
            GoogleIdentity.objects.create(
                user=existing_user,
                provider="google",
                provider_user_id=sub,
                email_at_link=email,
            )
            existing_user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, existing_user)
            return "authenticated", existing_user, None

        # Handle concurrent identity race condition
        existing_identity = GoogleIdentity.objects.filter(
            provider="google", provider_user_id=sub
        ).first()
        if existing_identity:
            user = existing_identity.user
            if not user.is_active:
                return (
                    "error",
                    None,
                    "This account has been deactivated. Please contact support.",
                )
            user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, user)
            return "authenticated", user, None

        # Create new User
        base_name = email.split("@")[0] or f"{given_name}_{family_name}"
        username = generate_unique_username(base_name)

        new_user = User(
            username=username,
            email=email,
            first_name=given_name[:150],
            last_name=family_name[:150],
            role=role,
            is_active=True,
        )
        new_user.set_unusable_password()
        new_user.save()

        GoogleIdentity.objects.create(
            user=new_user,
            provider="google",
            provider_user_id=sub,
            email_at_link=email,
        )

    new_user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, new_user)
    return "created", new_user, None
