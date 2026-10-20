import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.accounts.models import SocialAccount
from app.modules.content.models import Content, ContentVariant
from app.modules.publishing.models import PublishingJob
from app.modules.publishing.schemas import ScheduleAssignment

ACTIVE_JOB_STATUSES = ("scheduled", "queued", "publishing", "processing")
RETRYABLE_JOB_STATUSES = ("failed", "unknown")


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


class ScheduleError(Exception):
    pass


async def schedule_content(
    db: AsyncSession,
    content: Content,
    assignments: list[ScheduleAssignment],
) -> list[PublishingJob]:
    variant_rows = await db.execute(
        select(ContentVariant).where(ContentVariant.content_id == content.id)
    )
    variants = {v.platform: v for v in variant_rows.scalars().all()}

    jobs: list[PublishingJob] = []
    for assignment in assignments:
        variant = variants.get(assignment.platform)
        if variant is None:
            raise ScheduleError(f"No '{assignment.platform}' variant exists for this content")

        social_account = await db.get(SocialAccount, assignment.social_account_id)
        if (
            social_account is None
            or social_account.workspace_id != content.workspace_id
            or social_account.platform != assignment.platform
        ):
            raise ScheduleError(
                f"Social account {assignment.social_account_id} is not a valid "
                f"'{assignment.platform}' account in this workspace"
            )

        job = PublishingJob(
            content_variant_id=variant.id,
            social_account_id=social_account.id,
            scheduled_at=assignment.scheduled_at,
            idempotency_key=str(uuid.uuid4()),
        )
        db.add(job)
        jobs.append(job)

    content.status = "scheduled"
    await db.commit()
    for job in jobs:
        await db.refresh(job)
    return jobs


async def list_jobs_for_workspace(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    limit: int,
    offset: int,
    status_filter: str | None = None,
) -> tuple[list[PublishingJob], int]:
    base_filters = [Content.workspace_id == workspace_id]
    if status_filter is not None:
        base_filters.append(PublishingJob.status == status_filter)

    total = (
        await db.execute(
            select(func.count())
            .select_from(PublishingJob)
            .join(ContentVariant, PublishingJob.content_variant_id == ContentVariant.id)
            .join(Content, ContentVariant.content_id == Content.id)
            .where(*base_filters)
        )
    ).scalar_one()

    result = await db.execute(
        select(PublishingJob)
        .join(ContentVariant, PublishingJob.content_variant_id == ContentVariant.id)
        .join(Content, ContentVariant.content_id == Content.id)
        .where(*base_filters)
        .order_by(PublishingJob.scheduled_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def get_job_for_workspace(
    db: AsyncSession, workspace_id: uuid.UUID, job_id: uuid.UUID
) -> PublishingJob | None:
    result = await db.execute(
        select(PublishingJob)
        .options(selectinload(PublishingJob.publish_attempts))
        .join(ContentVariant, PublishingJob.content_variant_id == ContentVariant.id)
        .join(Content, ContentVariant.content_id == Content.id)
        .where(PublishingJob.id == job_id, Content.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def retry_job(db: AsyncSession, job: PublishingJob) -> PublishingJob:
    if job.status not in RETRYABLE_JOB_STATUSES:
        raise ScheduleError(f"Job in status '{job.status}' is not eligible for retry")
    job.status = "scheduled"
    job.scheduled_at = datetime.now(UTC)
    job.last_error = None
    await db.commit()
    await db.refresh(job)
    return job


async def cancel_content_jobs(db: AsyncSession, content: Content) -> int:
    result = await db.execute(
        select(PublishingJob)
        .join(ContentVariant, PublishingJob.content_variant_id == ContentVariant.id)
        .where(
            ContentVariant.content_id == content.id,
            PublishingJob.status.in_(ACTIVE_JOB_STATUSES),
        )
    )
    all_active = list(result.scalars().all())

    cancelled_count = 0
    for job in all_active:
        if job.status in ("scheduled", "queued"):
            job.status = "cancelled"
            cancelled_count += 1

    still_active = any(job.status in ACTIVE_JOB_STATUSES for job in all_active)
    if not still_active:
        content.status = "draft"

    await db.commit()
    return cancelled_count


async def recompute_content_status(db: AsyncSession, content_variant_id: uuid.UUID) -> None:
    variant = await db.get(ContentVariant, content_variant_id)
    if variant is None:
        return
    content = await db.get(Content, variant.content_id)
    if content is None or content.status == "draft":
        return

    result = await db.execute(
        select(PublishingJob.status)
        .join(ContentVariant, PublishingJob.content_variant_id == ContentVariant.id)
        .where(ContentVariant.content_id == content.id)
    )
    statuses = [row[0] for row in result.all()]
    if not statuses:
        return

    if any(s in ACTIVE_JOB_STATUSES for s in statuses):
        is_publishing = any(s in ("publishing", "processing") for s in statuses)
        content.status = "publishing" if is_publishing else "scheduled"
    else:
        non_cancelled = [s for s in statuses if s != "cancelled"]
        if not non_cancelled:
            content.status = "draft"
        else:
            published = sum(1 for s in non_cancelled if s == "published")
            if published == len(non_cancelled):
                content.status = "published"
            elif published == 0:
                content.status = "failed"
            else:
                content.status = "partial_failure"

    await db.commit()


async def get_calendar_jobs(
    db: AsyncSession, workspace_id: uuid.UUID, start: datetime, end: datetime
) -> list[tuple[PublishingJob, Content, SocialAccount]]:
    result = await db.execute(
        select(PublishingJob, Content, SocialAccount)
        .join(ContentVariant, PublishingJob.content_variant_id == ContentVariant.id)
        .join(Content, ContentVariant.content_id == Content.id)
        .join(SocialAccount, PublishingJob.social_account_id == SocialAccount.id)
        .where(
            Content.workspace_id == workspace_id,
            PublishingJob.scheduled_at >= start,
            PublishingJob.scheduled_at < end,
        )
        .order_by(PublishingJob.scheduled_at)
    )
    return [(job, content, account) for job, content, account in result.all()]
