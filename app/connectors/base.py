from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

PublishStatus = Literal["published", "processing", "failed", "unknown"]
MediaType = Literal["none", "image", "video", "carousel"]


@dataclass
class PublishRequest:
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
    async def get_publish_status(self, external_post_id: str) -> PublishResult: ...

    @abstractmethod
    async def validate_account(self, account_id: str) -> bool: ...
