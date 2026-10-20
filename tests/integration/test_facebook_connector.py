import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.connectors.base import PublishRequest
from app.connectors.facebook.client import FacebookGraphClient
from app.connectors.facebook.connector import FacebookConnector
from app.core.database import AsyncSessionLocal
from app.core.encryption import encrypt_token
from app.modules.accounts.models import OAuthToken, SocialAccount


@pytest_asyncio.fixture
async def facebook_account(db_session, user_factory):
    identity = await user_factory()
    social_account = SocialAccount(
        workspace_id=identity.workspace.id,
        platform="facebook",
        external_account_id="page-123",
        account_name="Test Page",
    )
    db_session.add(social_account)
    await db_session.flush()

    db_session.add(
        OAuthToken(
            social_account_id=social_account.id,
            encrypted_access_token=encrypt_token("page-access-token"),
        )
    )
    await db_session.commit()
    await db_session.refresh(social_account)
    return social_account


def _connector(handler) -> FacebookConnector:
    client = FacebookGraphClient(
        "v21.0", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    session_factory: async_sessionmaker = AsyncSessionLocal
    return FacebookConnector(session_factory, "v21.0", client=client)


async def test_publish_text_post_success(facebook_account):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v21.0/page-123/feed"
        return httpx.Response(200, json={"id": "page-123_post-1"})

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(facebook_account.id),
        text="Hello from GoFlow",
        media_type="none",
        media_urls=[],
    )

    result = await connector.publish(request)

    assert result.status == "published"
    assert result.external_post_id == "page-123_post-1"


async def test_publish_image_post_success(facebook_account):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v21.0/page-123/photos"
        return httpx.Response(200, json={"id": "photo-1", "post_id": "page-123_post-2"})

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(facebook_account.id),
        text="Check out this photo",
        media_type="image",
        media_urls=["https://example.com/photo.jpg"],
    )

    result = await connector.publish(request)

    assert result.status == "published"
    assert result.external_post_id == "page-123_post-2"


async def test_publish_maps_provider_error_to_retryable(facebook_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"message": "Rate limited", "code": 4, "error_subcode": None}}
        )

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(facebook_account.id), text="hi", media_type="none", media_urls=[]
    )

    result = await connector.publish(request)

    assert result.status == "failed"
    assert result.error_code == "rate_limited"


async def test_publish_maps_invalid_token_error(facebook_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": {"message": "Invalid token", "code": 190, "error_subcode": 463}}
        )

    connector = _connector(handler)
    request = PublishRequest(
        account_id=str(facebook_account.id), text="hi", media_type="none", media_urls=[]
    )

    result = await connector.publish(request)

    assert result.status == "failed"
    assert result.error_code == "invalid_token"


async def test_validate_account_true_on_success(facebook_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "page-123"})

    connector = _connector(handler)

    assert await connector.validate_account(str(facebook_account.id)) is True


async def test_validate_account_false_on_api_error(facebook_account):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": {"message": "Invalid token", "code": 190, "error_subcode": 463}}
        )

    connector = _connector(handler)

    assert await connector.validate_account(str(facebook_account.id)) is False


async def test_validate_account_false_for_unknown_account():
    connector = _connector(lambda request: httpx.Response(200, json={}))

    assert await connector.validate_account(str(uuid.uuid4())) is False


async def test_get_publish_status_not_implemented(facebook_account):
    connector = _connector(lambda request: httpx.Response(200, json={}))

    with pytest.raises(NotImplementedError):
        await connector.get_publish_status("some-post-id")
