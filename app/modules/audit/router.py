from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership, get_current_user, require_role
from app.core.database import get_db
from app.modules.audit import service
from app.modules.audit.schemas import (
    AuditLogListResponse,
    AuditLogRead,
    ReleaseCreate,
    ReleaseRead,
)
from app.modules.auth.models import User, WorkspaceMember

router = APIRouter(prefix="/audit-logs", tags=["audit"])
releases_router = APIRouter(prefix="/releases", tags=["audit"])

require_workspace_admin = Depends(require_role("owner", "admin"))


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    q: str | None = Query(default=None, description="Free-text search"),
    action: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    items, total = await service.list_audit_logs(
        db, membership.workspace_id, limit, offset, search=q, action_filter=action
    )
    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@releases_router.get("", response_model=list[ReleaseRead])
async def list_releases(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    items, _ = await service.list_releases(db, membership.workspace_id, limit, offset)
    return items


@releases_router.post("", response_model=ReleaseRead, status_code=201)
async def create_release(
    payload: ReleaseCreate,
    membership: WorkspaceMember = require_workspace_admin,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_release(
        db,
        membership.workspace_id,
        current_user,
        payload.version,
        payload.title,
        payload.description,
    )
