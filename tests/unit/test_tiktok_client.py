import httpx
import pytest

from app.connectors.tiktok.client import TikTokAPIError, TikTokClient


def _client(handler) -> TikTokClient:
    return TikTokClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_post_json_returns_data_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/post/publish/creator_info/query/"
        assert request.headers["authorization"] == "Bearer token-123"
        return httpx.Response(
            200,
            json={
                "data": {"creator_username": "myuser"},
                "error": {"code": "ok", "message": "", "log_id": "log-1"},
            },
        )

    client = _client(handler)
    result = await client.post_json(
        "v2/post/publish/creator_info/query/", {}, access_token="token-123"
    )

    assert result == {"creator_username": "myuser"}


async def test_post_json_raises_on_non_ok_error_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": {"code": "access_token_invalid", "message": "Bad token", "log_id": "l"}},
        )

    client = _client(handler)

    with pytest.raises(TikTokAPIError) as exc_info:
        await client.post_json("v2/post/publish/video/init/", {}, access_token="bad")

    assert exc_info.value.code == "access_token_invalid"
    assert exc_info.value.log_id == "l"


async def test_post_form_returns_raw_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        return httpx.Response(200, json={"access_token": "abc", "open_id": "user-1"})

    client = _client(handler)
    result = await client.post_form("v2/oauth/token/", {"grant_type": "authorization_code"})

    assert result == {"access_token": "abc", "open_id": "user-1"}
