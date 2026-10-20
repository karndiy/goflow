import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publishing.models import PublishingJob


async def claim_due_jobs(db: AsyncSession, limit: int = 10) -> list[uuid.UUID]:
    """Atomically claims due jobs, moving scheduled -> queued; safe for concurrent schedulers."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(PublishingJob.id)
        .where(PublishingJob.status == "scheduled", PublishingJob.scheduled_at <= now)
        .order_by(PublishingJob.scheduled_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    job_ids = [row[0] for row in result.all()]

    if job_ids:
        await db.execute(
            update(PublishingJob).where(PublishingJob.id.in_(job_ids)).values(status="queued")
        )
        await db.commit()

    return job_ids


async def recover_stuck_queued_jobs(
    db: AsyncSession, stuck_after: timedelta = timedelta(minutes=5)
) -> list[uuid.UUID]:
    """Resets jobs claimed but never delivered to a worker back to scheduled for re-claiming."""
    threshold = datetime.now(UTC) - stuck_after
    result = await db.execute(
        select(PublishingJob.id)
        .where(PublishingJob.status == "queued", PublishingJob.updated_at <= threshold)
        .with_for_update(skip_locked=True)
    )
    job_ids = [row[0] for row in result.all()]

    if job_ids:
        await db.execute(
            update(PublishingJob).where(PublishingJob.id.in_(job_ids)).values(status="scheduled")
        )
        await db.commit()

    return job_ids
