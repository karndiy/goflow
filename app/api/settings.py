from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_role
from app.core.database import get_db
from app.modules.accounts import service
from app.modules.accounts.models import PlatformCredential
from app.modules.accounts.schemas import (
    SUPPORTED_CREDENTIAL_PLATFORMS,
    PlatformCredentialRead,
    PlatformCredentialWrite,
)
from app.modules.audit.service import log_action
from app.modules.auth.models import User, WorkspaceMember

router = APIRouter(prefix="/settings", tags=["settings"])

require_workspace_admin = Depends(require_role("owner", "admin"))


def _to_read(credential: PlatformCredential) -> PlatformCredentialRead:
    return PlatformCredentialRead(
        platform=credential.platform,
        app_id=credential.app_id,
        has_secret=bool(credential.encrypted_app_secret),
        updated_at=credential.updated_at,
    )


@router.get("/platform-credentials", response_model=list[PlatformCredentialRead])
async def list_platform_credentials(
    membership: WorkspaceMember = require_workspace_admin,
    db: AsyncSession = Depends(get_db),
):
    credentials = await service.list_platform_credentials(db, membership.workspace_id)
    return [_to_read(c) for c in credentials]


@router.put("/platform-credentials/{platform}", response_model=PlatformCredentialRead)
async def set_platform_credential(
    platform: str,
    payload: PlatformCredentialWrite,
    membership: WorkspaceMember = require_workspace_admin,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if platform not in SUPPORTED_CREDENTIAL_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported platform '{platform}'"
        )
    credential = await service.upsert_platform_credential(
        db, membership.workspace_id, platform, payload.app_id, payload.app_secret
    )
    await log_action(
        db,
        membership.workspace_id,
        current_user,
        "settings.platform_credential_set",
        target_type="platform_credential",
        target_id=platform,
        details={"app_id": payload.app_id},
    )
    await db.commit()
    return _to_read(credential)


@router.delete("/platform-credentials/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform_credential(
    platform: str,
    membership: WorkspaceMember = require_workspace_admin,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    credential = await service.get_platform_credential(db, membership.workspace_id, platform)
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not configured")
    await service.delete_platform_credential(db, credential)
    await log_action(
        db,
        membership.workspace_id,
        current_user,
        "settings.platform_credential_delete",
        target_type="platform_credential",
        target_id=platform,
    )
    await db.commit()
