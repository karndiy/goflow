import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publishing.models import PublishingJob


async def create_job(
    db: AsyncSession,
    content_variant_id: uuid.UUID,
    social_account_id: uuid.UUID,
    scheduled_at: datetime,
    idempotency_key: str | None = None,
) -> PublishingJob:
    job = PublishingJob(
        content_variant_id=content_variant_id,
        social_account_id=social_account_id,
        scheduled_at=scheduled_at,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> PublishingJob | None:
    return await db.get(PublishingJob, job_id)
