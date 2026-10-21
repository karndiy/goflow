from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

PublishStatus = Literal["published", "processing", "failed", "unknown"]
MediaType = Literal["none", "image", "video", "carousel"]


@dataclass
class PublishRequest:
    # GoFlow's internal social_accounts.id (UUID string), not the platform's external account id --
    # lets a connector resolve its own stored credentials without the caller handling tokens.
    account_id: str
    text: str
    media_type: MediaType
    media_urls: list[str]
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishResult:
    status: PublishStatus
    external_post_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] | None = None


class SocialConnector(ABC):
    platform: str
    supported_media_types: tuple[MediaType, ...] = ("none",)
    supports_direct_publish: bool = True
    supports_status_polling: bool = False

    @abstractmethod
    async def publish(self, request: PublishRequest) -> PublishResult: ...

    @abstractmethod
    async def get_publish_status(self, account_id: str, external_post_id: str) -> PublishResult:
        """`account_id` is GoFlow's internal social_accounts.id (same as PublishRequest) --
        some platforms' status checks are per-user authenticated calls, not a public lookup."""

    @abstractmethod
    async def validate_account(self, account_id: str) -> bool:
        """`account_id` is GoFlow's internal social_accounts.id, same as PublishRequest."""
