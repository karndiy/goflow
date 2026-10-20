import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import SocialConnector
from app.core.encryption import encrypt_token
from app.modules.accounts.models import OAuthToken, SocialAccount


async def list_social_accounts(db: AsyncSession, workspace_id: uuid.UUID) -> list[SocialAccount]:
    result = await db.execute(
        select(SocialAccount)
        .where(SocialAccount.workspace_id == workspace_id)
        .order_by(SocialAccount.created_at.desc())
    )
    return list(result.scalars().all())


async def upsert_social_account_with_token(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    platform: str,
    external_account_id: str,
    account_name: str,
    access_token: str,
    expires_at: datetime | None = None,
) -> SocialAccount:
    social_account = (
        await db.execute(
            select(SocialAccount).where(
                SocialAccount.workspace_id == workspace_id,
                SocialAccount.platform == platform,
                SocialAccount.external_account_id == external_account_id,
            )
        )
    ).scalar_one_or_none()

    if social_account is None:
        social_account = SocialAccount(
            workspace_id=workspace_id,
            platform=platform,
            external_account_id=external_account_id,
            account_name=account_name,
        )
        db.add(social_account)
    else:
        social_account.account_name = account_name
        social_account.status = "active"
    await db.flush()

    encrypted = encrypt_token(access_token)
    token_row = (
        await db.execute(
            select(OAuthToken).where(OAuthToken.social_account_id == social_account.id)
        )
    ).scalar_one_or_none()

    if token_row is None:
        db.add(
            OAuthToken(
                social_account_id=social_account.id,
                encrypted_access_token=encrypted,
                expires_at=expires_at,
            )
        )
    else:
        token_row.encrypted_access_token = encrypted
        token_row.expires_at = expires_at

    await db.commit()
    await db.refresh(social_account)
    return social_account


async def check_account_health(
    db: AsyncSession, social_account: SocialAccount, connector: SocialConnector
) -> bool:
    is_valid = await connector.validate_account(str(social_account.id))
    social_account.status = "active" if is_valid else "needs_reauth"
    await db.commit()
    return is_valid
