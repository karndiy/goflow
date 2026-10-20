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

    response = await api_client.post("/api/v1/accounts/facebook/connect")

    assert response.status_code == 503


async def test_connect_returns_authorization_url_when_configured(
    api_client, user_factory, monkeypatch
):
    monkeypatch.setattr(accounts_router_module.settings, "meta_app_id", "app-123")
    monkeypatch.setattr(accounts_router_module.settings, "meta_app_secret", "secret-123")
    identity = await user_factory()
    await _login(api_client, identity)

    response = await api_client.post("/api/v1/accounts/facebook/connect")

    assert response.status_code == 200
    url = response.json()["authorization_url"]
    assert url.startswith("https://www.facebook.com/")
    assert "state=" in url


async def test_connect_requires_authentication(api_client, monkeypatch):
    monkeypatch.setattr(accounts_router_module.settings, "meta_app_id", "app-123")

    response = await api_client.post("/api/v1/accounts/facebook/connect")

    assert response.status_code == 401


async def test_callback_missing_code_redirects_with_error(api_client):
    response = await api_client.get("/api/v1/oauth/facebook/callback")

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["error"] == ["missing_code_or_state"]


async def test_callback_invalid_state_redirects_with_error(api_client):
    response = await api_client.get(
        "/api/v1/oauth/facebook/callback", params={"code": "abc", "state": "never-issued"}
    )

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["error"] == ["invalid_state"]


async def test_callback_success_creates_social_account_and_token(
    api_client, db_session, user_factory, monkeypatch
):
    monkeypatch.setattr(accounts_router_module.settings, "meta_app_id", "app-123")
    monkeypatch.setattr(accounts_router_module.settings, "meta_app_secret", "secret-123")

    identity = await user_factory()
    state = await create_oauth_state(
        workspace_id=str(identity.workspace.id), user_id=str(identity.user.id), platform="facebook"
    )

    async def fake_exchange_code_for_token(client, **kwargs):
        return {"access_token": "short-lived", "expires_in": 3600}

    async def fake_exchange_for_long_lived_token(client, **kwargs):
        return {"access_token": "long-lived", "expires_in": 5184000}

    async def fake_list_pages(client, user_access_token):
        return [{"id": "page-1", "name": "My Page", "access_token": "page-token-1"}]

    monkeypatch.setattr(
        accounts_router_module.facebook_oauth,
        "exchange_code_for_token",
        fake_exchange_code_for_token,
    )
    monkeypatch.setattr(
        accounts_router_module.facebook_oauth,
        "exchange_for_long_lived_token",
        fake_exchange_for_long_lived_token,
    )
    monkeypatch.setattr(accounts_router_module.facebook_oauth, "list_pages", fake_list_pages)

    response = await api_client.get(
        "/api/v1/oauth/facebook/callback", params={"code": "auth-code", "state": state}
    )

    assert response.status_code == 307
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["connected"] == ["facebook"]
    assert query["count"] == ["1"]

    social_account = (
        await db_session.execute(
            select(SocialAccount).where(
                SocialAccount.workspace_id == identity.workspace.id,
                SocialAccount.external_account_id == "page-1",
            )
        )
    ).scalar_one()
    assert social_account.account_name == "My Page"

    token_row = (
        await db_session.execute(
            select(OAuthToken).where(OAuthToken.social_account_id == social_account.id)
        )
    ).scalar_one()
    assert decrypt_token(token_row.encrypted_access_token) == "page-token-1"
