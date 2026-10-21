import uuid

from app.connectors.base import PublishRequest, PublishResult, SocialConnector


class MockTimeoutError(Exception):
    """Simulates a request that may or may not have reached the provider."""


class MockConnector(SocialConnector):
    """In-memory connector with no network calls, for proving the scheduling pipeline works."""

    platform = "mock"
    supported_media_types = ("none", "image", "video", "carousel")
    supports_direct_publish = True
    supports_status_polling = True

    def __init__(self) -> None:
        self._status_responses: dict[str, PublishResult] = {}

    def set_status_response(self, external_post_id: str, result: PublishResult) -> None:
        self._status_responses[external_post_id] = result

    async def publish(self, request: PublishRequest) -> PublishResult:
        outcome = request.options.get("mock_outcome", "published")
        external_post_id = f"mock-{uuid.uuid4().hex}"

        if outcome == "published":
            return PublishResult(status="published", external_post_id=external_post_id)
        if outcome == "processing":
            return PublishResult(status="processing", external_post_id=external_post_id)
        if outcome == "failed_transient":
            return PublishResult(
                status="failed",
                error_code="rate_limited",
                error_message="Mock rate limit exceeded",
            )
        if outcome == "failed_permanent":
            return PublishResult(
                status="failed",
                error_code="invalid_media",
                error_message="Mock permanent rejection",
            )
        if outcome == "timeout":
            raise MockTimeoutError("Mock request timed out before a response was received")

        raise ValueError(f"Unknown mock_outcome: {outcome}")

    async def get_publish_status(self, account_id: str, external_post_id: str) -> PublishResult:
        result = self._status_responses.get(external_post_id)
        if result is None:
            return PublishResult(status="unknown", external_post_id=external_post_id)
        return result

    async def validate_account(self, account_id: str) -> bool:
        return True
