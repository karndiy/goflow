from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

import app.modules.accounts.router as accounts_router_module
from app.core.encryption import decrypt_token
from app.modules.accounts.models import OAuthToken, SocialAccount
from app.modules.accounts.oauth_state import create_oauth_state


async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


async def test_connect_returns_503_when_not_configured(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    response = await api_client.post("/api/v1/accounts/tiktok/connect")

    assert response.status_code == 503


async def test_connect_returns_authorization_url_when_configured(
    api_client, user_factory, monkeypatch
):
    monkeypatch.setattr(accounts_router_module.settings, "tiktok_client_key", "client-123")
    monkeypatch.setattr(accounts_router_module.settings, "tiktok_client_secret", "secret-123")
    identity = await user_factory()
    await _login(api_client, identity)

    response = await api_client.post("/api/v1/accounts/tiktok/connect")

    assert response.status_code == 200
    url = response.json()["authorization_url"]
    assert url.startswith("https://www.tiktok.com/")
    assert "state=" in url


async def test_connect_requires_authentication(api_client, monkeypatch):
    monkeypatch.setattr(accounts_router_module.settings, "tiktok_client_key", "client-123")

    response = await api_client.post("/api/v1/accounts/tiktok/connect")

    assert response.status_code == 401


async def test_callback_missing_code_redirects_with_error(api_client):
    response = await api_client.get("/api/v1/oauth/tiktok/callback")

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["error"] == ["missing_code_or_state"]


async def test_callback_invalid_state_redirects_with_error(api_client):
    response = await api_client.get(
        "/api/v1/oauth/tiktok/callback", params={"code": "abc", "state": "never-issued"}
    )

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["error"] == ["invalid_state"]


async def test_callback_success_creates_social_account_and_token(
    api_client, db_session, user_factory, monkeypatch
):
    monkeypatch.setattr(accounts_router_module.settings, "tiktok_client_key", "client-123")
    monkeypatch.setattr(accounts_router_module.settings, "tiktok_client_secret", "secret-123")

    identity = await user_factory()
    state = await create_oauth_state(
        workspace_id=str(identity.workspace.id), user_id=str(identity.user.id), platform="tiktok"
    )

    async def fake_exchange_code_for_token(client, **kwargs):
        return {
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "expires_in": 86400,
            "open_id": "open-id-1",
        }

    async def fake_get_creator_info(client, access_token):
        return {"creator_nickname": "My TikTok", "creator_username": "myuser"}

    monkeypatch.setattr(
        accounts_router_module.tiktok_oauth,
        "exchange_code_for_token",
        fake_exchange_code_for_token,
    )
    monkeypatch.setattr(
        accounts_router_module.tiktok_oauth, "get_creator_info", fake_get_creator_info
    )

    response = await api_client.get(
        "/api/v1/oauth/tiktok/callback", params={"code": "auth-code", "state": state}
    )

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["connected"] == ["tiktok"]
    assert query["count"] == ["1"]

    social_account = (
        await db_session.execute(
            select(SocialAccount).where(
                SocialAccount.workspace_id == identity.workspace.id,
                SocialAccount.external_account_id == "open-id-1",
            )
        )
    ).scalar_one()
    assert social_account.account_name == "My TikTok"

    token_row = (
        await db_session.execute(
            select(OAuthToken).where(OAuthToken.social_account_id == social_account.id)
        )
    ).scalar_one()
    assert decrypt_token(token_row.encrypted_access_token) == "access-1"
    assert decrypt_token(token_row.encrypted_refresh_token) == "refresh-1"
    assert token_row.expires_at is not None


async def test_callback_exchange_failure_redirects_with_error(
    api_client, user_factory, monkeypatch
):
    monkeypatch.setattr(accounts_router_module.settings, "tiktok_client_key", "client-123")
    monkeypatch.setattr(accounts_router_module.settings, "tiktok_client_secret", "secret-123")

    identity = await user_factory()
    state = await create_oauth_state(
        workspace_id=str(identity.workspace.id), user_id=str(identity.user.id), platform="tiktok"
    )

    async def failing_exchange(client, **kwargs):
        from app.connectors.tiktok.oauth import TikTokOAuthError

        raise TikTokOAuthError("boom")

    monkeypatch.setattr(
        accounts_router_module.tiktok_oauth, "exchange_code_for_token", failing_exchange
    )

    response = await api_client.get(
        "/api/v1/oauth/tiktok/callback", params={"code": "auth-code", "state": state}
    )

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["error"] == ["tiktok_exchange_failed"]
