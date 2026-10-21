import logging
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership
from app.connectors.facebook import oauth as facebook_oauth
from app.connectors.facebook.client import FacebookAPIError, FacebookGraphClient
from app.connectors.tiktok import oauth as tiktok_oauth
from app.connectors.tiktok.client import TikTokAPIError, TikTokClient
from app.connectors.tiktok.oauth import TikTokOAuthError
from app.core.config import get_settings
from app.core.database import get_db
from app.modules.accounts import service
from app.modules.accounts.oauth_state import consume_oauth_state, create_oauth_state
from app.modules.accounts.schemas import ConnectResponse, SocialAccountRead
from app.modules.audit.service import log_action
from app.modules.auth.models import WorkspaceMember
from app.modules.auth.service import get_user_by_id

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/accounts", tags=["accounts"])
oauth_router = APIRouter(prefix="/oauth", tags=["accounts"])


def _facebook_redirect_uri() -> str:
    return f"{settings.app_base_url}/api/v1/oauth/facebook/callback"


def _tiktok_redirect_uri() -> str:
    return f"{settings.app_base_url}/api/v1/oauth/tiktok/callback"


async def _resolve_facebook_credentials(
    db: AsyncSession, workspace_id: uuid.UUID
) -> tuple[str, str] | None:
    return await service.resolve_platform_credentials(
        db, workspace_id, "facebook", settings.meta_app_id, settings.meta_app_secret
    )


async def _resolve_tiktok_credentials(
    db: AsyncSession, workspace_id: uuid.UUID
) -> tuple[str, str] | None:
    return await service.resolve_platform_credentials(
        db, workspace_id, "tiktok", settings.tiktok_client_key, settings.tiktok_client_secret
    )


@router.get("", response_model=list[SocialAccountRead])
async def list_accounts(
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_social_accounts(db, membership.workspace_id)


@router.post("/facebook/connect", response_model=ConnectResponse)
async def connect_facebook(
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    credentials = await _resolve_facebook_credentials(db, membership.workspace_id)
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Facebook integration is not configured",
        )
    app_id, _ = credentials

    state = await create_oauth_state(
        workspace_id=str(membership.workspace_id),
        user_id=str(membership.user_id),
        platform="facebook",
    )
    authorization_url = facebook_oauth.build_authorization_url(
        api_version=settings.meta_graph_api_version,
        app_id=app_id,
        redirect_uri=_facebook_redirect_uri(),
        state=state,
    )
    return ConnectResponse(authorization_url=authorization_url)


@oauth_router.get("/facebook/callback")
async def facebook_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    frontend_accounts_url = f"{settings.frontend_base_url}/accounts"

    if error or not code or not state:
        return RedirectResponse(
            f"{frontend_accounts_url}?{urlencode({'error': error or 'missing_code_or_state'})}"
        )

    state_data = await consume_oauth_state(state)
    if state_data is None or state_data.get("platform") != "facebook":
        return RedirectResponse(f"{frontend_accounts_url}?{urlencode({'error': 'invalid_state'})}")

    workspace_id = uuid.UUID(state_data["workspace_id"])
    credentials = await _resolve_facebook_credentials(db, workspace_id)
    if credentials is None:
        return RedirectResponse(
            f"{frontend_accounts_url}?{urlencode({'error': 'facebook_not_configured'})}"
        )
    app_id, app_secret = credentials

    client = FacebookGraphClient(settings.meta_graph_api_version)
    try:
        token_response = await facebook_oauth.exchange_code_for_token(
            client,
            app_id=app_id,
            app_secret=app_secret,
            redirect_uri=_facebook_redirect_uri(),
            code=code,
        )
        long_lived = await facebook_oauth.exchange_for_long_lived_token(
            client,
            app_id=app_id,
            app_secret=app_secret,
            short_lived_token=token_response["access_token"],
        )
        pages = await facebook_oauth.list_pages(client, long_lived["access_token"])
    except FacebookAPIError:
        logger.exception("Facebook OAuth exchange failed")
        return RedirectResponse(
            f"{frontend_accounts_url}?{urlencode({'error': 'facebook_exchange_failed'})}"
        )
    finally:
        await client.aclose()

    for page in pages:
        await service.upsert_social_account_with_token(
            db,
            workspace_id=workspace_id,
            platform="facebook",
            external_account_id=page["id"],
            account_name=page.get("name", page["id"]),
            access_token=page["access_token"],
        )

    actor = await get_user_by_id(db, uuid.UUID(state_data["user_id"]))
    if actor is not None:
        await log_action(
            db,
            workspace_id,
            actor,
            "accounts.facebook_connected",
            target_type="social_account",
            details={"page_count": len(pages)},
        )
        await db.commit()

    return RedirectResponse(
        f"{frontend_accounts_url}?{urlencode({'connected': 'facebook', 'count': len(pages)})}"
    )


@router.post("/tiktok/connect", response_model=ConnectResponse)
async def connect_tiktok(
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    credentials = await _resolve_tiktok_credentials(db, membership.workspace_id)
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TikTok integration is not configured",
        )
    client_key, _ = credentials

    state = await create_oauth_state(
        workspace_id=str(membership.workspace_id),
        user_id=str(membership.user_id),
        platform="tiktok",
    )
    authorization_url = tiktok_oauth.build_authorization_url(
        client_key=client_key,
        redirect_uri=_tiktok_redirect_uri(),
        state=state,
    )
    return ConnectResponse(authorization_url=authorization_url)


@oauth_router.get("/tiktok/callback")
async def tiktok_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    frontend_accounts_url = f"{settings.frontend_base_url}/accounts"

    if error or not code or not state:
        return RedirectResponse(
            f"{frontend_accounts_url}?{urlencode({'error': error or 'missing_code_or_state'})}"
        )

    state_data = await consume_oauth_state(state)
    if state_data is None or state_data.get("platform") != "tiktok":
        return RedirectResponse(f"{frontend_accounts_url}?{urlencode({'error': 'invalid_state'})}")

    workspace_id = uuid.UUID(state_data["workspace_id"])
    credentials = await _resolve_tiktok_credentials(db, workspace_id)
    if credentials is None:
        return RedirectResponse(
            f"{frontend_accounts_url}?{urlencode({'error': 'tiktok_not_configured'})}"
        )
    client_key, client_secret = credentials

    client = TikTokClient()
    try:
        token_response = await tiktok_oauth.exchange_code_for_token(
            client,
            client_key=client_key,
            client_secret=client_secret,
            redirect_uri=_tiktok_redirect_uri(),
            code=code,
        )
        creator_info = await tiktok_oauth.get_creator_info(client, token_response["access_token"])
    except (TikTokOAuthError, TikTokAPIError):
        logger.exception("TikTok OAuth exchange failed")
        return RedirectResponse(
            f"{frontend_accounts_url}?{urlencode({'error': 'tiktok_exchange_failed'})}"
        )
    finally:
        await client.aclose()

    account_name = creator_info.get("creator_nickname") or creator_info.get(
        "creator_username", token_response["open_id"]
    )
    expires_in = token_response.get("expires_in")
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in else None

    await service.upsert_social_account_with_token(
        db,
        workspace_id=workspace_id,
        platform="tiktok",
        external_account_id=token_response["open_id"],
        account_name=account_name,
        access_token=token_response["access_token"],
        refresh_token=token_response.get("refresh_token"),
        expires_at=expires_at,
    )

    actor = await get_user_by_id(db, uuid.UUID(state_data["user_id"]))
    if actor is not None:
        await log_action(
            db,
            workspace_id,
            actor,
            "accounts.tiktok_connected",
            target_type="social_account",
            details={"account_name": account_name},
        )
        await db.commit()

    return RedirectResponse(
        f"{frontend_accounts_url}?{urlencode({'connected': 'tiktok', 'count': 1})}"
    )
