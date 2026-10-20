import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_membership
from app.core.database import get_db
from app.modules.auth.models import WorkspaceMember
from app.modules.publishing import service
from app.modules.publishing.schemas import (
    CalendarEntry,
    JobListResponse,
    PublishingJobDetailRead,
    PublishingJobRead,
)

router = APIRouter(prefix="/publishing", tags=["publishing"])


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    items, total = await service.list_jobs_for_workspace(
        db, membership.workspace_id, limit, offset, status_filter
    )
    return JobListResponse(
        items=[PublishingJobRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}", response_model=PublishingJobDetailRead)
async def get_job(
    job_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    job = await service.get_job_for_workspace(db, membership.workspace_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/retry", response_model=PublishingJobRead)
async def retry_job(
    job_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    job = await service.get_job_for_workspace(db, membership.workspace_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    try:
        return await service.retry_job(db, job)
    except service.ScheduleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/calendar", response_model=list[CalendarEntry])
async def get_calendar(
    start: datetime,
    end: datetime,
    membership: WorkspaceMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.get_calendar_jobs(db, membership.workspace_id, start, end)
    return [
        CalendarEntry(
            job_id=job.id,
            content_id=content.id,
            content_title=content.title,
            platform=account.platform,
            social_account_id=account.id,
            account_name=account.account_name,
            scheduled_at=job.scheduled_at,
            status=job.status,
        )
        for job, content, account in rows
    ]
