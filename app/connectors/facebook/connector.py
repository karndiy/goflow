import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.connectors.base import PublishRequest, PublishResult, SocialConnector
from app.connectors.facebook.client import FacebookAPIError, FacebookGraphClient
from app.connectors.facebook.errors import map_facebook_error
from app.core.encryption import decrypt_token
from app.modules.accounts.models import OAuthToken, SocialAccount


class FacebookConnector(SocialConnector):
    platform = "facebook"
    supported_media_types = ("none", "image")
    supports_direct_publish = True
    supports_status_polling = False

    def __init__(
        self,
        session_factory: async_sessionmaker,
        api_version: str,
        client: FacebookGraphClient | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._client = client or FacebookGraphClient(api_version)

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

            return social_account, decrypt_token(token_row.encrypted_access_token)

    async def publish(self, request: PublishRequest) -> PublishResult:
        social_account, access_token = await self._resolve_account_and_token(request.account_id)
        page_id = social_account.external_account_id

        try:
            if request.media_type == "image" and request.media_urls:
                response = await self._client.post(
                    f"{page_id}/photos",
                    {
                        "url": request.media_urls[0],
                        "caption": request.text,
                        "access_token": access_token,
                    },
                )
                post_id = response.get("post_id") or response.get("id")
            else:
                response = await self._client.post(
                    f"{page_id}/feed",
                    {"message": request.text, "access_token": access_token},
                )
                post_id = response.get("id")
        except FacebookAPIError as exc:
            return PublishResult(
                status="failed",
                error_code=map_facebook_error(exc.code, exc.subcode),
                error_message=str(exc),
                raw_response={
                    "code": exc.code,
                    "subcode": exc.subcode,
                    "fbtrace_id": exc.fbtrace_id,
                },
            )

        return PublishResult(status="published", external_post_id=post_id, raw_response=response)

    async def get_publish_status(self, external_post_id: str) -> PublishResult:
        raise NotImplementedError(
            "FacebookConnector publishes text/image posts synchronously "
            "(supports_status_polling=False); there is nothing to poll."
        )

    async def validate_account(self, account_id: str) -> bool:
        try:
            _, access_token = await self._resolve_account_and_token(account_id)
        except ValueError:
            return False

        try:
            await self._client.get("me", {"fields": "id", "access_token": access_token})
        except FacebookAPIError:
            return False
        return True
