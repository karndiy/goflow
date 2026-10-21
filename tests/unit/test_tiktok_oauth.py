from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.connectors.tiktok import oauth
from app.connectors.tiktok.client import TikTokClient
from app.connectors.tiktok.oauth import TikTokOAuthError


def test_build_authorization_url_contains_required_params():
    url = oauth.build_authorization_url(
        client_key="client-123",
        redirect_uri="http://localhost:8000/api/v1/oauth/tiktok/callback",
        state="the-state-value",
    )

    parsed = urlparse(url)
    assert parsed.netloc == "www.tiktok.com"
    assert parsed.path == "/v2/auth/authorize/"
    query = parse_qs(parsed.query)
    assert query["client_key"] == ["client-123"]
    assert query["state"] == ["the-state-value"]
    assert query["response_type"] == ["code"]
    assert "redirect_uri" in query
    assert query["scope"] == ["user.info.basic,video.publish"]


async def test_exchange_code_for_token_calls_expected_endpoint():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "access_token": "access-1",
                "expires_in": 86400,
                "refresh_token": "refresh-1",
                "refresh_expires_in": 31536000,
                "open_id": "open-1",
                "scope": "user.info.basic,video.publish",
                "token_type": "Bearer",
            },
        )

    client = TikTokClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    result = await oauth.exchange_code_for_token(
        client,
        client_key="client-123",
        client_secret="secret",
        redirect_uri="http://localhost/callback",
        code="auth-code",
    )

    assert result["access_token"] == "access-1"
    assert result["open_id"] == "open-1"
    assert captured["path"] == "/v2/oauth/token/"


async def test_exchange_code_for_token_raises_on_error_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": "invalid_grant", "error_description": "Code expired"}
        )

    client = TikTokClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    with pytest.raises(TikTokOAuthError, match="Code expired"):
        await oauth.exchange_code_for_token(
            client,
            client_key="client-123",
            client_secret="secret",
            redirect_uri="http://localhost/callback",
            code="bad-code",
        )


async def test_refresh_access_token_returns_new_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "expires_in": 86400,
                "refresh_token": "new-refresh",
                "open_id": "open-1",
            },
        )

    client = TikTokClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    result = await oauth.refresh_access_token(client, "client-123", "secret", "old-refresh")

    assert result["access_token"] == "new-access"
    assert result["refresh_token"] == "new-refresh"


async def test_get_creator_info_returns_data():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/post/publish/creator_info/query/"
        return httpx.Response(
            200,
            json={
                "data": {"creator_nickname": "My TikTok", "creator_username": "myuser"},
                "error": {"code": "ok", "message": "", "log_id": "l"},
            },
        )

    client = TikTokClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    info = await oauth.get_creator_info(client, "token")

    assert info["creator_nickname"] == "My TikTok"
