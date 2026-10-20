from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership
from app.core.database import get_db
from app.modules.audit import service
from app.modules.audit.schemas import AuditLogListResponse, AuditLogRead
from app.modules.auth.models import WorkspaceMember

router = APIRouter(prefix="/audit-logs", tags=["audit"])


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
