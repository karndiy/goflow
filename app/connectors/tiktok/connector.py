import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.connectors.base import PublishRequest, PublishResult, SocialConnector
from app.connectors.tiktok import oauth as tiktok_oauth
from app.connectors.tiktok.client import TikTokAPIError, TikTokClient
from app.connectors.tiktok.errors import map_tiktok_error
from app.core.config import get_settings
from app.core.encryption import decrypt_token, encrypt_token
from app.modules.accounts.models import OAuthToken, SocialAccount
from app.modules.accounts.service import resolve_platform_credentials

DEFAULT_PRIVACY_LEVEL = "SELF_ONLY"  # always available, even for an unaudited app/client.
TITLE_MAX_RUNES = 2200
PHOTO_DESCRIPTION_MAX_RUNES = 4000

# A finished post isn't necessarily live immediately -- SEND_TO_USER_INBOX means TikTok queued
# it for the creator to manually approve/post from their own app, not an automatic failure.
_STATUS_MAP = {
    "PROCESSING_UPLOAD": "processing",
    "PROCESSING_DOWNLOAD": "processing",
    "SEND_TO_USER_INBOX": "processing",
    "PUBLISH_COMPLETE": "published",
    "FAILED": "failed",
}


class TikTokConnector(SocialConnector):
    platform = "tiktok"
    supported_media_types = ("image", "video", "carousel")  # TikTok has no text-only post.
    supports_direct_publish = True
    supports_status_polling = True

    def __init__(
        self,
        session_factory: async_sessionmaker,
        client: TikTokClient | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._client = client or TikTokClient()
        self._settings = get_settings()

    async def _resolve_account_and_token(self, account_id: str) -> tuple[SocialAccount, str]:
        async with self._session_factory() as db:
            social_account = await db.get(SocialAccount, uuid.UUID(account_id))
            if social_account is None:
                raise ValueError(f"Unknown social account {account_id}")

            token_row = (
                await db.execute(
                    select(OAuthToken).where(OAuthToken.social_account_id == social_account.id)
                )
            ).scalar_one_or_none()
            if token_row is None:
                raise ValueError(f"No stored token for social account {account_id}")

            access_token = decrypt_token(token_row.encrypted_access_token)
            needs_refresh = (
                token_row.expires_at is not None
                and token_row.expires_at <= datetime.now(UTC)
                and token_row.encrypted_refresh_token is not None
            )
            if needs_refresh:
                credentials = await resolve_platform_credentials(
                    db,
                    social_account.workspace_id,
                    "tiktok",
                    self._settings.tiktok_client_key,
                    self._settings.tiktok_client_secret,
                )
                if credentials is None:
                    raise ValueError(
                        "TikTok app credentials are not configured; cannot refresh token"
                    )
                client_key, client_secret = credentials
                refreshed = await tiktok_oauth.refresh_access_token(
                    self._client,
                    client_key,
                    client_secret,
                    decrypt_token(token_row.encrypted_refresh_token),  # type: ignore[arg-type]
                )
                access_token = refreshed["access_token"]
                token_row.encrypted_access_token = encrypt_token(access_token)
                if refreshed.get("refresh_token"):
                    token_row.encrypted_refresh_token = encrypt_token(refreshed["refresh_token"])
                expires_in = refreshed.get("expires_in")
                token_row.expires_at = (
                    datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in else None
                )
                await db.commit()

            return social_account, access_token

    async def publish(self, request: PublishRequest) -> PublishResult:
        _, access_token = await self._resolve_account_and_token(request.account_id)
        privacy_level = request.options.get("privacy_level", DEFAULT_PRIVACY_LEVEL)

        try:
            creator_info = await tiktok_oauth.get_creator_info(self._client, access_token)
        except TikTokAPIError as exc:
            return PublishResult(
                status="failed",
                error_code=map_tiktok_error(exc.code),
                error_message=str(exc),
                raw_response={"code": exc.code, "log_id": exc.log_id},
            )

        available_levels = creator_info.get("privacy_level_options") or []
        if available_levels and privacy_level not in available_levels:
            return PublishResult(
                status="failed",
                error_code="invalid_request",
                error_message=(
                    f"privacy_level '{privacy_level}' is not available for this creator "
                    f"(available: {', '.join(available_levels)})"
                ),
                raw_response={"creator_info": creator_info},
            )

        try:
            body: dict[str, Any]
            if request.media_type == "video":
                body = {
                    "post_info": {
                        "title": request.text[:TITLE_MAX_RUNES],
                        "privacy_level": privacy_level,
                        "disable_duet": request.options.get("disable_duet", False),
                        "disable_stitch": request.options.get("disable_stitch", False),
                        "disable_comment": request.options.get("disable_comment", False),
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "video_url": request.media_urls[0],
                    },
                }
                data = await self._client.post_json(
                    "v2/post/publish/video/init/", body, access_token
                )
            else:
                body = {
                    "media_type": "PHOTO",
                    "post_mode": "DIRECT_POST",
                    "post_info": {
                        "description": request.text[:PHOTO_DESCRIPTION_MAX_RUNES],
                        "privacy_level": privacy_level,
                        "disable_comment": request.options.get("disable_comment", False),
                        "auto_add_music": request.options.get("auto_add_music", True),
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "photo_images": request.media_urls,
                        "photo_cover_index": 0,
                    },
                }
                data = await self._client.post_json(
                    "v2/post/publish/content/init/", body, access_token
                )
        except TikTokAPIError as exc:
            return PublishResult(
                status="failed",
                error_code=map_tiktok_error(exc.code),
                error_message=str(exc),
                raw_response={"code": exc.code, "log_id": exc.log_id},
            )

        return PublishResult(
            status="processing", external_post_id=data.get("publish_id"), raw_response=data
        )

    async def get_publish_status(self, account_id: str, external_post_id: str) -> PublishResult:
        # external_post_id here is TikTok's publish_id (not yet a public post id/URL -- see
        # _STATUS_MAP: PUBLISH_COMPLETE is the only status that means it actually went live).
        _, access_token = await self._resolve_account_and_token(account_id)
        try:
            data = await self._client.post_json(
                "v2/post/publish/status/fetch/",
                {"publish_id": external_post_id},
                access_token,
            )
        except TikTokAPIError as exc:
            return PublishResult(
                status="failed",
                external_post_id=external_post_id,
                error_code=map_tiktok_error(exc.code),
                error_message=str(exc),
                raw_response={"code": exc.code, "log_id": exc.log_id},
            )

        provider_status = data.get("status", "")
        mapped_status = _STATUS_MAP.get(provider_status, "unknown")
        fail_reason = data.get("fail_reason")
        return PublishResult(
            status=mapped_status,  # type: ignore[arg-type]
            external_post_id=external_post_id,
            error_code=map_tiktok_error(fail_reason) if fail_reason else None,
            error_message=fail_reason,
            raw_response=data,
        )

    async def validate_account(self, account_id: str) -> bool:
        try:
            _, access_token = await self._resolve_account_and_token(account_id)
        except ValueError:
            return False

        try:
            await tiktok_oauth.get_creator_info(self._client, access_token)
        except TikTokAPIError:
            return False
        return True
