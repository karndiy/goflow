import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog, Release
from app.modules.auth.models import User


async def log_action(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    actor: User,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Fire-and-forget audit entry; does not commit (callers already commit their own change)."""
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_user_id=actor.id,
            actor_email=actor.email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
        )
    )


async def list_audit_logs(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    limit: int,
    offset: int,
    search: str | None = None,
    action_filter: str | None = None,
) -> tuple[list[AuditLog], int]:
    filters = [AuditLog.workspace_id == workspace_id]
    if action_filter:
        filters.append(AuditLog.action == action_filter)
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                AuditLog.actor_email.ilike(pattern),
                AuditLog.action.ilike(pattern),
                AuditLog.target_type.ilike(pattern),
                AuditLog.target_id.ilike(pattern),
            )
        )

    total = (
        await db.execute(select(func.count()).select_from(AuditLog).where(*filters))
    ).scalar_one()

    result = await db.execute(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def create_release(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    actor: User,
    version: str,
    title: str,
    description: str | None,
) -> Release:
    release = Release(
        workspace_id=workspace_id,
        version=version,
        title=title,
        description=description,
        created_by_email=actor.email,
    )
    db.add(release)
    await db.commit()
    await db.refresh(release)
    return release


async def list_releases(
    db: AsyncSession, workspace_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[Release], int]:
    total = (
        await db.execute(
            select(func.count()).select_from(Release).where(Release.workspace_id == workspace_id)
        )
    ).scalar_one()

    result = await db.execute(
        select(Release)
        .where(Release.workspace_id == workspace_id)
        .order_by(Release.released_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total
