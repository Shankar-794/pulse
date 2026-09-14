"""
Comprehensive Tests for Authentication & Per-User Personalization Isolation.
Verifies HMAC-SHA256 session tokens, user persistence, auth endpoints,
and per-user data isolation for preferences, interactions, and saved stories.
"""
import pytest
import time
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.db_repository import db_repository
from backend.app.core.security import create_session_token, verify_session_token

client = TestClient(app)


def test_session_token_cryptography():
    """Verifies HMAC-SHA256 token creation, claims verification, and tamper resistance."""
    user_id = "usr_test_crypto_123"
    email = "crypto@pulse.news"

    token = create_session_token(user_id=user_id, email=email, expires_days=1)
    assert token is not None
    assert "." in token

    claims = verify_session_token(token)
    assert claims is not None
    assert claims["sub"] == user_id
    assert claims["email"] == email
    assert claims["exp"] > time.time()

    # Tamper with token payload
    parts = token.split(".")
    tampered = f"{parts[0]}extra.{parts[1]}"
    assert verify_session_token(tampered) is None

    # Tamper with signature
    tampered_sig = f"{parts[0]}.bad_signature_here"
    assert verify_session_token(tampered_sig) is None

    # Expired token
    expired_token = create_session_token(user_id=user_id, email=email, expires_days=-1)
    assert verify_session_token(expired_token) is None


def test_auth_config_endpoint():
    """Verifies /api/auth/config returns safe public config without leaking secrets."""
    res = client.get("/api/auth/config")
    assert res.status_code == 200
    data = res.json()
    assert "google_configured" in data
    assert "client_id" in data
    assert "redirect_uri" in data
    assert "client_secret" not in data


def test_dev_login_and_me():
    """Verifies developer login, token generation, and /api/auth/me authentication."""
    email = "operator_test@pulse.news"
    name = "Dev Operator"

    # Dev login
    res = client.post("/api/auth/dev-login", json={"email": email, "name": name})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert "user" in data
    assert data["user"]["email"] == email
    assert data["user"]["full_name"] == name
    user_id = data["user"]["id"]
    token = data["token"]

    # Verify /api/auth/me with valid Bearer token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user"]["id"] == user_id
    assert me_data["user"]["email"] == email

    # Verify /api/auth/me without token fails with 401
    unauth_res = client.get("/api/auth/me")
    assert unauth_res.status_code == 401

    # Verify /api/auth/me with invalid token fails with 401
    bad_res = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert bad_res.status_code == 401


def test_user_saved_stories_isolation():
    """
    Verifies that saved stories are completely isolated per user:
    - User A saves a story -> User A sees it.
    - User B does NOT see User A's saved story.
    - Brand new user starts with 0 saved stories (no 'Saved Stories 2' bug).
    - Unsaving removes only from that user's saved list.
    """
    import uuid
    email_a = f"alice_saved_{uuid.uuid4().hex[:8]}@pulse.news"
    email_b = f"bob_saved_{uuid.uuid4().hex[:8]}@pulse.news"

    # 1. Create User A
    res_a = client.post("/api/auth/dev-login", json={"email": email_a, "name": "Alice"})
    assert res_a.status_code == 200
    token_a = res_a.json()["token"]
    auth_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Create User B
    res_b = client.post("/api/auth/dev-login", json={"email": email_b, "name": "Bob"})
    assert res_b.status_code == 200
    token_b = res_b.json()["token"]
    auth_b = {"Authorization": f"Bearer {token_b}"}

    # Verify initial saved stories is exactly 0 for both brand-new users
    init_a = client.get("/api/stories/saved", headers=auth_a).json()
    init_b = client.get("/api/stories/saved", headers=auth_b).json()
    assert init_a["total"] == 0
    assert len(init_a["items"]) == 0
    assert init_b["total"] == 0
    assert len(init_b["items"]) == 0

    # Get real story IDs to save
    stories_res = client.get("/api/stories").json()
    assert stories_res["total"] >= 2, "Need at least 2 stories for isolation test"
    story_id = stories_res["items"][0]["id"]
    story_y_id = stories_res["items"][1]["id"]

    # Alice saves story X
    save_res = client.post(f"/api/stories/{story_id}/save", headers=auth_a)
    assert save_res.status_code == 200
    assert save_res.json()["is_saved"] is True

    # Alice now sees 1 saved story
    after_a = client.get("/api/stories/saved", headers=auth_a).json()
    assert after_a["total"] == 1
    assert any(s["id"] == story_id for s in after_a["items"])

    # Bob still sees 0 saved stories
    after_b = client.get("/api/stories/saved", headers=auth_b).json()
    assert after_b["total"] == 0
    assert len(after_b["items"]) == 0

    # User B now saves a DIFFERENT story (story Y)
    save_b_res = client.post(f"/api/stories/{story_y_id}/save", headers=auth_b)
    assert save_b_res.status_code == 200
    assert save_b_res.json()["is_saved"] is True

    # Bob sees exactly 1 saved story (story Y)
    b_saved = client.get("/api/stories/saved", headers=auth_b).json()
    assert b_saved["total"] == 1
    assert any(s["id"] == story_y_id for s in b_saved["items"])
    assert not any(s["id"] == story_id for s in b_saved["items"])

    # Alice still sees ONLY story X (count remains 1)
    a_still = client.get("/api/stories/saved", headers=auth_a).json()
    assert a_still["total"] == 1
    assert any(s["id"] == story_id for s in a_still["items"])
    assert not any(s["id"] == story_y_id for s in a_still["items"])

    # Anonymous user still sees 0 saved stories
    anon_saved = client.get("/api/stories/saved").json()
    assert anon_saved["total"] == 0

    # Alice unsaves story
    unsave_res = client.delete(f"/api/stories/{story_id}/save", headers=auth_a)
    assert unsave_res.status_code == 200
    assert unsave_res.json()["is_saved"] is False

    # Alice now sees 0 saved stories
    final_a = client.get("/api/stories/saved", headers=auth_a).json()
    assert final_a["total"] == 0


def test_user_preferences_isolation():
    """Verifies that user preference updates are isolated per user."""
    # User A
    res_a = client.post("/api/auth/dev-login", json={"email": "alice_prefs@pulse.news", "name": "Alice P"})
    token_a = res_a.json()["token"]
    auth_a = {"Authorization": f"Bearer {token_a}"}

    # User B
    res_b = client.post("/api/auth/dev-login", json={"email": "bob_prefs@pulse.news", "name": "Bob P"})
    token_b = res_b.json()["token"]
    auth_b = {"Authorization": f"Bearer {token_b}"}

    # Alice updates importance threshold to 88
    put_a = client.put("/api/preferences", json={"importance_threshold": 88}, headers=auth_a)
    assert put_a.status_code == 200
    assert put_a.json()["importance_threshold"] == 88

    # Bob checks his preferences - should remain default 50
    get_b = client.get("/api/preferences", headers=auth_b)
    assert get_b.status_code == 200
    assert get_b.json()["importance_threshold"] == 50


def test_dev_login_production_gating():
    """Verifies that /api/auth/dev-login is rejected with HTTP 403 in production mode."""
    from backend.app.core.config import settings
    orig_env = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        res = client.post("/api/auth/dev-login", json={"email": "hacker@pulse.news", "name": "Attacker"})
        assert res.status_code == 403
        assert "production" in res.json()["detail"].lower()

        cfg_res = client.get("/api/auth/config")
        assert cfg_res.status_code == 200
        assert cfg_res.json()["dev_login_enabled"] is False
    finally:
        settings.ENVIRONMENT = orig_env


def test_business_and_economy_categories():
    """Verifies /api/stories for 'business' and 'economy' categories execute cleanly."""
    res_biz = client.get("/api/stories?category=business")
    assert res_biz.status_code == 200
    biz_data = res_biz.json()
    assert "total" in biz_data
    assert "items" in biz_data

    res_econ = client.get("/api/stories?category=economy")
    assert res_econ.status_code == 200
    econ_data = res_econ.json()
    assert "total" in econ_data
    assert "items" in econ_data


def test_google_oauth_callback_cancellation():
    """Verifies that OAuth cancellation or error query parameters 302 redirect to frontend with error."""
    res = client.get("/api/auth/google/callback?error=access_denied", follow_redirects=False)
    assert res.status_code == 302
    assert "error=access_denied" in res.headers["location"]
    assert "/auth/callback" in res.headers["location"]


def test_google_oauth_callback_missing_code():
    """Verifies that missing code 302 redirects to frontend with missing_code."""
    res = client.get("/api/auth/google/callback", follow_redirects=False)
    assert res.status_code == 302
    assert "error=missing_code" in res.headers["location"]


def test_google_oauth_full_flow_and_returning_user():
    """Verifies Google OAuth GET callback creates user and subsequent login returns same user without duplicates."""
    import httpx
    from unittest.mock import AsyncMock, patch
    from backend.app.core.config import settings
    from backend.app.core.db_repository import db_repository

    orig_client_id = settings.GOOGLE_CLIENT_ID
    orig_client_secret = settings.GOOGLE_CLIENT_SECRET
    settings.GOOGLE_CLIENT_ID = "mock_client_id"
    settings.GOOGLE_CLIENT_SECRET = "mock_client_secret"

    try:
        mock_token_resp = httpx.Response(200, json={"access_token": "ya29.mock_token_123"}, request=httpx.Request("POST", "https://oauth2.googleapis.com/token"))
        mock_userinfo_resp = httpx.Response(200, json={
            "sub": "google_sub_999888",
            "email": "sarah.connor@cyberdyne.org",
            "name": "Sarah Connor",
            "picture": "https://lh3.googleusercontent.com/sarah.jpg"
        }, request=httpx.Request("GET", "https://www.googleapis.com/oauth2/v3/userinfo"))

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_token_resp), \
             patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_userinfo_resp):
            # First login: creates new user
            res = client.get("/api/auth/google/callback?code=mock_auth_code_1", follow_redirects=False)
            assert res.status_code == 302
            loc = res.headers["location"]
            assert "token=" in loc
            assert "/auth/callback" in loc

            # Verify user exists in database
            user1 = db_repository.get_user_by_email("sarah.connor@cyberdyne.org")
            assert user1 is not None
            assert user1["full_name"] == "Sarah Connor"
            assert user1["oauth_sub"] == "google_sub_999888"

            # Second login: returning user
            res2 = client.get("/api/auth/google/callback?code=mock_auth_code_2", follow_redirects=False)
            assert res2.status_code == 302
            loc2 = res2.headers["location"]
            assert "token=" in loc2

            # Verify no duplicate user was created
            user2 = db_repository.get_user_by_email("sarah.connor@cyberdyne.org")
            assert user2 is not None
            assert user2["id"] == user1["id"]
    finally:
        settings.GOOGLE_CLIENT_ID = orig_client_id
        settings.GOOGLE_CLIENT_SECRET = orig_client_secret


def test_anonymous_read_only_access():
    """Verifies that anonymous users can read feed, categories, and system health without auth."""
    res_health = client.get("/api/health")
    assert res_health.status_code == 200

    res_feed = client.get("/api/feed?limit=5")
    assert res_feed.status_code == 200

    res_stories = client.get("/api/stories?limit=5")
    assert res_stories.status_code == 200

    res_cfg = client.get("/api/auth/config")
    assert res_cfg.status_code == 200
    assert "google_configured" in res_cfg.json()


def test_protected_endpoints_require_auth():
    """Verifies that personalized write actions reject unauthenticated requests with HTTP 401."""
    # Attempting to save a story without token
    res = client.post("/api/stories/test_story_123/save")
    assert res.status_code == 401

