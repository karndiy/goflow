import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.connectors.base import PublishRequest
from app.connectors.tiktok.client import TikTokClient
from app.connectors.tiktok.connector import TikTokConnector
from app.core.database import AsyncSessionLocal
from app.core.encryption import decrypt_token, encrypt_token
from app.modules.accounts.models import OAuthToken, SocialAccount


@pytest_asyncio.fixture
async def tiktok_account(db_session, user_factory):
    identity = await user_factory()
    social_account = SocialAccount(
        workspace_id=identity.workspace.id,
        platform="tiktok",
        external_account_id="open-id-123",
        account_name="My TikTok",
    )
    db_session.add(social_account)
    await db_session.flush()

    db_session.add(
        OAuthToken(
            social_account_id=social_account.id,
            encrypted_access_token=encrypt_token("access-token"),
            encrypted_refresh_token=encrypt_token("refresh-token"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await db_session.commit()
    await db_session.refresh(social_account)
    return social_account


def _connector(handler) -> TikTokConnector:
    client = TikTokClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    session_factory: async_sessionmaker = AsyncSessionLocal
    return TikTokConnector(session_factory, client=client)


_CREATOR_INFO_OK = {
    "data": {
        "creator_username": "myuser",
        "creator_nickname": "My TikTok",
        "privacy_level_options": ["SELF_ONLY", "PUBLIC_TO_EVERYONE"],
    },
    "error": {"code": "ok", "message": "", "log_id": "l"},
}


async def test_publish_video_success(tiktok_account):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/post/publish/creator_info/query/":
            return httpx.Response(200, json=_CREATOR_INFO_OK)
        assert request.url.path == "/v2/post/publish/video/init/"
        return httpx.Response(
            200,
            json={
                "data": {"publish_id": "pub-1", "upload_url": "https://x/upload"},
                "error": {"code": "ok", "message": "", "log_id": "l"},
            },
        )

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(tiktok_account.id),
        text="Check out this video",
        media_type="video",
        media_urls=["https://example.com/video.mp4"],
    )

    result = await connector.publish(request)

    assert result.status == "processing"
    assert result.external_post_id == "pub-1"


async def test_publish_image_uses_photo_endpoint(tiktok_account):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/post/publish/creator_info/query/":
            return httpx.Response(200, json=_CREATOR_INFO_OK)
        assert request.url.path == "/v2/post/publish/content/init/"
        return httpx.Response(
            200, json={"data": {"publish_id": "pub-2"}, "error": {"code": "ok", "log_id": "l"}}
        )

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(tiktok_account.id),
        text="A nice photo",
        media_type="image",
        media_urls=["https://example.com/photo.jpg"],
    )

    result = await connector.publish(request)

    assert result.status == "processing"
    assert result.external_post_id == "pub-2"


async def test_publish_carousel_sends_all_photo_urls(tiktok_account):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/post/publish/creator_info/query/":
            return httpx.Response(200, json=_CREATOR_INFO_OK)
        captured["body"] = request.content
        return httpx.Response(
            200, json={"data": {"publish_id": "pub-3"}, "error": {"code": "ok", "log_id": "l"}}
        )

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(tiktok_account.id),
        text="Carousel",
        media_type="carousel",
        media_urls=["https://example.com/a.jpg", "https://example.com/b.jpg"],
    )

    result = await connector.publish(request)

    assert result.status == "processing"
    assert b"a.jpg" in captured["body"] and b"b.jpg" in captured["body"]


async def test_publish_rejects_unavailable_privacy_level(tiktok_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_CREATOR_INFO_OK)

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(tiktok_account.id),
        text="hi",
        media_type="image",
        media_urls=["https://example.com/a.jpg"],
        options={"privacy_level": "MUTUAL_FOLLOW_FRIENDS"},
    )

    result = await connector.publish(request)

    assert result.status == "failed"
    assert result.error_code == "invalid_request"
    assert "MUTUAL_FOLLOW_FRIENDS" in result.error_message


async def test_publish_maps_creator_info_error(tiktok_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": {"code": "access_token_invalid", "message": "bad token", "log_id": "l"}},
        )

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(tiktok_account.id),
        text="hi",
        media_type="image",
        media_urls=["https://example.com/a.jpg"],
    )

    result = await connector.publish(request)

    assert result.status == "failed"
    assert result.error_code == "invalid_token"


async def test_publish_maps_post_init_error(tiktok_account):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/post/publish/creator_info/query/":
            return httpx.Response(200, json=_CREATOR_INFO_OK)
        return httpx.Response(
            200,
            json={"error": {"code": "rate_limit_exceeded", "message": "slow down", "log_id": "l"}},
        )

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(tiktok_account.id),
        text="hi",
        media_type="image",
        media_urls=["https://example.com/a.jpg"],
    )

    result = await connector.publish(request)

    assert result.status == "failed"
    assert result.error_code == "rate_limited"


async def test_get_publish_status_maps_publish_complete(tiktok_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {"status": "PUBLISH_COMPLETE"},
                "error": {"code": "ok", "message": "", "log_id": "l"},
            },
        )

    connector = _connector(handler)
    result = await connector.get_publish_status(str(tiktok_account.id), "pub-1")

    assert result.status == "published"


async def test_get_publish_status_maps_failed_with_reason(tiktok_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {"status": "FAILED", "fail_reason": "picture_size_check_failed"},
                "error": {"code": "ok", "message": "", "log_id": "l"},
            },
        )

    connector = _connector(handler)
    result = await connector.get_publish_status(str(tiktok_account.id), "pub-1")

    assert result.status == "failed"
    assert result.error_code == "invalid_request"
    assert result.error_message == "picture_size_check_failed"


async def test_get_publish_status_maps_processing_variants(tiktok_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {"status": "SEND_TO_USER_INBOX"},
                "error": {"code": "ok", "message": "", "log_id": "l"},
            },
        )

    connector = _connector(handler)
    result = await connector.get_publish_status(str(tiktok_account.id), "pub-1")

    assert result.status == "processing"


async def test_validate_account_true_on_success(tiktok_account):
    connector = _connector(lambda request: httpx.Response(200, json=_CREATOR_INFO_OK))

    assert await connector.validate_account(str(tiktok_account.id)) is True


async def test_validate_account_false_on_api_error(tiktok_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error": {"code": "access_token_invalid", "message": "bad", "log_id": "l"}}
        )

    connector = _connector(handler)

    assert await connector.validate_account(str(tiktok_account.id)) is False


async def test_validate_account_false_for_unknown_account():
    connector = _connector(lambda request: httpx.Response(200, json=_CREATOR_INFO_OK))

    assert await connector.validate_account(str(uuid.uuid4())) is False


async def test_publish_refreshes_expired_token(db_session, user_factory, monkeypatch):
    identity = await user_factory()
    social_account = SocialAccount(
        workspace_id=identity.workspace.id,
        platform="tiktok",
        external_account_id="open-id-456",
        account_name="Expiring account",
    )
    db_session.add(social_account)
    await db_session.flush()
    db_session.add(
        OAuthToken(
            social_account_id=social_account.id,
            encrypted_access_token=encrypt_token("stale-access"),
            encrypted_refresh_token=encrypt_token("refresh-abc"),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.commit()
    await db_session.refresh(social_account)

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v2/oauth/token/":
            return httpx.Response(
                200,
                json={
                    "access_token": "fresh-access",
                    "refresh_token": "fresh-refresh",
                    "expires_in": 86400,
                    "open_id": "open-id-456",
                },
            )
        assert request.headers["authorization"] == "Bearer fresh-access"
        return httpx.Response(200, json=_CREATOR_INFO_OK)

    connector = _connector(handler)
    monkeypatch.setattr(connector._settings, "tiktok_client_key", "client-key")
    monkeypatch.setattr(connector._settings, "tiktok_client_secret", "client-secret")

    assert await connector.validate_account(str(social_account.id)) is True
    assert "/v2/oauth/token/" in calls

    refreshed_token = (
        await db_session.execute(
            select(OAuthToken).where(OAuthToken.social_account_id == social_account.id)
        )
    ).scalar_one()
    assert decrypt_token(refreshed_token.encrypted_access_token) == "fresh-access"
