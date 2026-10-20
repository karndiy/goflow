from urllib.parse import parse_qs, urlparse

import httpx

from app.connectors.facebook import oauth
from app.connectors.facebook.client import FacebookGraphClient


def test_build_authorization_url_contains_required_params():
    url = oauth.build_authorization_url(
        api_version="v21.0",
        app_id="app-123",
        redirect_uri="http://localhost:8000/api/v1/oauth/facebook/callback",
        state="the-state-value",
    )

    parsed = urlparse(url)
    assert parsed.netloc == "www.facebook.com"
    assert parsed.path == "/v21.0/dialog/oauth"
    query = parse_qs(parsed.query)
    assert query["client_id"] == ["app-123"]
    assert query["state"] == ["the-state-value"]
    assert query["response_type"] == ["code"]
    assert "redirect_uri" in query


async def test_exchange_code_for_token_calls_expected_endpoint():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"access_token": "short-lived", "expires_in": 3600})

    client = FacebookGraphClient(
        "v21.0", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    result = await oauth.exchange_code_for_token(
        client,
        app_id="app-123",
        app_secret="secret",
        redirect_uri="http://localhost/callback",
        code="auth-code",
    )

    assert result["access_token"] == "short-lived"
    assert captured["path"] == "/v21.0/oauth/access_token"
    assert captured["params"]["code"] == "auth-code"


async def test_list_pages_returns_data_array():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "page-1", "name": "Page One", "access_token": "page-token-1"},
                    {"id": "page-2", "name": "Page Two", "access_token": "page-token-2"},
                ]
            },
        )

    client = FacebookGraphClient(
        "v21.0", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    pages = await oauth.list_pages(client, "user-token")

    assert len(pages) == 2
    assert pages[0]["id"] == "page-1"
