import pytest

from app.connectors.base import PublishRequest, PublishResult
from app.connectors.mock.connector import MockConnector, MockTimeoutError
from app.connectors.registry import (
    ConnectorRegistrationError,
    ConnectorRegistry,
    UnsupportedPlatformError,
)


def _request(**options) -> PublishRequest:
    return PublishRequest(
        account_id="acct-1", text="hello", media_type="none", media_urls=[], options=options
    )


async def test_mock_connector_published_outcome():
    result = await MockConnector().publish(_request(mock_outcome="published"))

    assert result.status == "published"
    assert result.external_post_id is not None


async def test_mock_connector_processing_outcome():
    result = await MockConnector().publish(_request(mock_outcome="processing"))

    assert result.status == "processing"
    assert result.external_post_id is not None


async def test_mock_connector_failed_transient_outcome():
    result = await MockConnector().publish(_request(mock_outcome="failed_transient"))

    assert result.status == "failed"
    assert result.error_code == "rate_limited"


async def test_mock_connector_failed_permanent_outcome():
    result = await MockConnector().publish(_request(mock_outcome="failed_permanent"))

    assert result.status == "failed"
    assert result.error_code == "invalid_media"


async def test_mock_connector_timeout_outcome_raises():
    with pytest.raises(MockTimeoutError):
        await MockConnector().publish(_request(mock_outcome="timeout"))


async def test_mock_connector_status_polling():
    connector = MockConnector()
    result = await connector.publish(_request(mock_outcome="processing"))

    status = await connector.get_publish_status("acct-1", result.external_post_id)
    assert status.status == "unknown"

    connector.set_status_response(
        result.external_post_id,
        PublishResult(status="published", external_post_id=result.external_post_id),
    )
    resolved = await connector.get_publish_status("acct-1", result.external_post_id)
    assert resolved.status == "published"


def test_registry_register_and_get():
    registry = ConnectorRegistry()
    connector = MockConnector()

    registry.register(connector)

    assert registry.get("mock") is connector


def test_registry_rejects_duplicate_registration():
    registry = ConnectorRegistry()
    registry.register(MockConnector())

    with pytest.raises(ConnectorRegistrationError):
        registry.register(MockConnector())


def test_registry_raises_for_unsupported_platform():
    registry = ConnectorRegistry()

    with pytest.raises(UnsupportedPlatformError):
        registry.get("facebook")
