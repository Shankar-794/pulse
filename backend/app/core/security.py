"""
Security and Session Token Management for Pulse.
Provides cryptographic HMAC-SHA256 session token generation and verification
with expiration handling, tamper prevention, and constant-time signature checks.
"""
import time
import json
import hmac
import base64
import hashlib
import secrets
from typing import Optional, Dict, Any

from backend.app.core.config import settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def create_session_token(
    user_id: str,
    email: str,
    expires_days: Optional[int] = None,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Creates a tamper-proof cryptographically signed HMAC-SHA256 session token.
    """
    secret = getattr(settings, "AUTH_SECRET_KEY", "pulse-default-secret-key").encode("utf-8")
    days = expires_days if expires_days is not None else getattr(settings, "AUTH_TOKEN_EXPIRE_DAYS", 7)
    now = int(time.time())
    exp = now + (days * 86400)

    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": exp
    }
    if extra_claims:
        payload.update(extra_claims)

    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)

    signature = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{payload_b64}.{sig_b64}"


def verify_session_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Validates a session token. Checks signature and expiration using constant-time comparison.
    Returns decoded claims dict if valid, or None if invalid or expired.
    """
    if not token or not isinstance(token, str) or "." not in token:
        return None

    try:
        payload_b64, sig_b64 = token.split(".", 1)
        secret = getattr(settings, "AUTH_SECRET_KEY", "pulse-default-secret-key").encode("utf-8")
        expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = _b64url_decode(payload_b64)
        claims = json.loads(payload_bytes.decode("utf-8"))

        now = int(time.time())
        if claims.get("exp") and claims["exp"] < now:
            return None

        return claims
    except Exception:
        return None


def generate_oauth_state() -> str:
    """Generates a cryptographically random state parameter for OAuth CSRF protection."""
    return secrets.token_urlsafe(32)
