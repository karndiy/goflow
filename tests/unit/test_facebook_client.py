import httpx
import pytest

from app.connectors.facebook.client import FacebookAPIError, FacebookGraphClient


def _client(handler) -> FacebookGraphClient:
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return FacebookGraphClient("v21.0", http_client=http_client)


async def test_get_returns_parsed_json_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v21.0/me"
        return httpx.Response(200, json={"id": "123", "name": "Test Page"})

    client = _client(handler)
    result = await client.get("me", {"access_token": "token"})

    assert result == {"id": "123", "name": "Test Page"}


async def test_post_returns_parsed_json_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v21.0/123/feed"
        return httpx.Response(200, json={"id": "456"})

    client = _client(handler)
    result = await client.post("123/feed", {"message": "hello"})

    assert result == {"id": "456"}


async def test_error_response_raises_facebook_api_error_with_details():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Invalid OAuth access token.",
                    "type": "OAuthException",
                    "code": 190,
                    "error_subcode": 463,
                    "fbtrace_id": "abc123",
                }
            },
        )

    client = _client(handler)

    with pytest.raises(FacebookAPIError) as exc_info:
        await client.get("me", {"access_token": "bad-token"})

    assert exc_info.value.code == 190
    assert exc_info.value.subcode == 463
    assert exc_info.value.fbtrace_id == "abc123"
