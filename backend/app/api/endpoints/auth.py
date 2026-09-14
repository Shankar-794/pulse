"""
Authentication Endpoints for Pulse.
Supports Google OAuth 2.0 / OpenID Connect and developer authentication.
"""
from typing import Optional, Dict, Any
from urllib.parse import urlencode, quote
import httpx
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.security import (
    create_session_token,
    verify_session_token,
    generate_oauth_state
)
from backend.app.core.db_repository import db_repository
from backend.app.api.deps import get_current_user, get_optional_user

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleCallbackRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None


class DevLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, description="User email address")
    name: Optional[str] = None
    picture_url: Optional[str] = None


@router.get("/config")
async def get_auth_config() -> Dict[str, Any]:
    """
    Returns public authentication configuration.
    Never exposes client secret.
    """
    is_configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    env = getattr(settings, "ENVIRONMENT", "development").lower()
    dev_enabled = env in ("development", "dev", "test", "testing") and env not in ("production", "prod")
    return {
        "google_configured": is_configured,
        "dev_login_enabled": dev_enabled,
        "client_id": settings.GOOGLE_CLIENT_ID if is_configured else "",
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    }


@router.get("/google/url")
async def get_google_auth_url(redirect_uri: Optional[str] = None) -> Dict[str, str]:
    """
    Generates a secure Google OAuth 2.0 authorization URL with state parameter.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google sign-in is temporarily unavailable."
        )

    state = generate_oauth_state()
    effective_redirect_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": effective_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account"
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {
        "url": auth_url,
        "state": state
    }


async def _process_google_code(code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """
    Core token exchange and user provisioning logic.
    Exchanges code with Google, retrieves userinfo, upserts user,
    and returns session token + user profile.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured on this server."
        )

    effective_redirect_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI

    # 1. Exchange authorization code for Google access token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": effective_redirect_uri,
        "grant_type": "authorization_code"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            token_resp = await client.post(token_url, data=token_data)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to communicate with Google authentication services."
            )

        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google token exchange failed."
            )

        token_json = token_resp.json()
        access_token = token_json.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access_token returned by Google"
            )

        # 2. Retrieve userinfo from Google
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        try:
            userinfo_resp = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to retrieve Google user profile."
            )

        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve profile from Google"
            )

        userinfo = userinfo_resp.json()

    email = userinfo.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account did not return an email address"
        )

    # 3. Upsert user in database (handles duplicate protection & returning user lookup)
    user = db_repository.upsert_user(
        email=email,
        full_name=userinfo.get("name") or email.split("@")[0].title(),
        picture_url=userinfo.get("picture") or "",
        oauth_provider="google",
        oauth_sub=userinfo.get("sub", "")
    )

    # 4. Generate signed session token
    session_token = create_session_token(
        user_id=user["id"],
        email=user["email"],
        expires_days=settings.AUTH_TOKEN_EXPIRE_DAYS
    )

    return {
        "token": session_token,
        "user": user
    }


@router.get("/google/callback")
async def handle_google_callback_redirect(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None)
):
    """
    HTTP GET endpoint for direct Google OAuth redirect.
    Validates OAuth response, creates/retrieves user, creates session token,
    and 302 redirects back to the configured frontend application.
    """
    frontend_base = getattr(settings, "FRONTEND_URL", "https://pulse-drab-eight.vercel.app").rstrip("/")
    target_callback = f"{frontend_base}/auth/callback"

    if error:
        return RedirectResponse(
            url=f"{target_callback}?error={quote(error)}",
            status_code=status.HTTP_302_FOUND
        )

    if not code:
        return RedirectResponse(
            url=f"{target_callback}?error=missing_code",
            status_code=status.HTTP_302_FOUND
        )

    try:
        res = await _process_google_code(code, redirect_uri=settings.GOOGLE_REDIRECT_URI)
        token = res["token"]
        return RedirectResponse(
            url=f"{target_callback}?token={quote(token)}",
            status_code=status.HTTP_302_FOUND
        )
    except HTTPException as he:
        err_msg = str(he.detail) if isinstance(he.detail, str) else "auth_failed"
        return RedirectResponse(
            url=f"{target_callback}?error={quote(err_msg)}",
            status_code=status.HTTP_302_FOUND
        )
    except Exception:
        return RedirectResponse(
            url=f"{target_callback}?error=internal_auth_error",
            status_code=status.HTTP_302_FOUND
        )


@router.post("/google/callback")
async def handle_google_callback(payload: GoogleCallbackRequest) -> Dict[str, Any]:
    """
    Exchanges an authorization code for tokens, retrieves profile,
    and returns a signed session token with the authenticated user.
    """
    return await _process_google_code(payload.code, payload.redirect_uri)


@router.post("/dev-login")
async def dev_login(payload: DevLoginRequest) -> Dict[str, Any]:
    """
    Developer/offline login endpoint.
    Allows deterministic authentication and user isolation testing without live Google credentials.
    DISABLED in production environments.
    """
    from backend.app.core.config import settings
    env = getattr(settings, "ENVIRONMENT", "development").lower()
    if env in ("production", "prod") or env not in ("development", "dev", "test", "testing"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Developer login is not available in production."
        )

    email = payload.email.strip().lower()
    full_name = payload.name or email.split("@")[0].title()
    picture_url = payload.picture_url or ""

    user = db_repository.upsert_user(
        email=email,
        full_name=full_name,
        picture_url=picture_url,
        oauth_provider="dev",
        oauth_sub=f"dev_{email}"
    )

    session_token = create_session_token(
        user_id=user["id"],
        email=user["email"],
        expires_days=settings.AUTH_TOKEN_EXPIRE_DAYS
    )

    return {
        "token": session_token,
        "user": user
    }


@router.get("/me")
async def get_me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Retrieves the profile of the currently authenticated user.
    """
    return {"user": user}


@router.post("/logout")
async def logout(user: Optional[Dict[str, Any]] = Depends(get_optional_user)) -> Dict[str, str]:
    """
    Logs out the user session. Client will discard the session token.
    """
    return {"status": "logged_out"}
