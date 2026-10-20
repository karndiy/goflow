import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import MediaType, PublishRequest
from app.connectors.mock.connector import RETRYABLE_ERROR_CODES
from app.connectors.registry import ConnectorRegistry
from app.connectors.registry import registry as default_registry
from app.modules.accounts.models import SocialAccount
from app.modules.content.models import ContentVariant
from app.modules.publishing.models import PublishAttempt, PublishingJob

MAX_ATTEMPTS = 3
RETRY_BACKOFF_BASE_SECONDS = 60


def _retry_delay(attempt_number: int) -> timedelta:
    return timedelta(seconds=RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt_number - 1)))


async def process_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    connector_registry: ConnectorRegistry = default_registry,
) -> PublishingJob | None:
    job = await db.get(PublishingJob, job_id)
    if job is None or job.status != "queued":
        return job

    job.status = "publishing"
    await db.commit()

    variant = await db.get(ContentVariant, job.content_variant_id)
    social_account = await db.get(SocialAccount, job.social_account_id)
    if variant is None or social_account is None:
        raise RuntimeError(f"Publishing job {job.id} references a deleted variant or account")
    connector = connector_registry.get(social_account.platform)

    attempt_number = job.attempts + 1
    options = (variant.payload_json or {}).get("options", {})
    media_type = cast(MediaType, variant.media_type)
    request = PublishRequest(
        account_id=social_account.external_account_id,
        text=variant.text,
        media_type=media_type,
        media_urls=[],
        options=options,
    )

    try:
        result = await connector.publish(request)
    except Exception as exc:
        job.attempts = attempt_number
        job.status = "unknown"
        job.last_error = str(exc)
        db.add(
            PublishAttempt(
                job_id=job.id,
                attempt_number=attempt_number,
                status="unknown",
                error_message=str(exc),
            )
        )
        await db.commit()
        return job

    db.add(
        PublishAttempt(
            job_id=job.id,
            attempt_number=attempt_number,
            status=result.status,
            provider_request_id=result.external_post_id,
            sanitized_result=result.raw_response,
            error_code=result.error_code,
            error_message=result.error_message,
        )
    )
    job.attempts = attempt_number
    if result.external_post_id:
        job.external_post_id = result.external_post_id

    if result.status == "published":
        job.status = "published"
        job.last_error = None
    elif result.status == "processing":
        job.status = "processing"
        job.last_error = None
    elif result.status == "failed":
        job.last_error = result.error_message
        if result.error_code in RETRYABLE_ERROR_CODES and attempt_number < MAX_ATTEMPTS:
            job.status = "scheduled"
            job.scheduled_at = datetime.now(UTC) + _retry_delay(attempt_number)
        else:
            job.status = "failed"
    else:
        job.status = "unknown"

    await db.commit()
    await db.refresh(job)
    return job


async def reconcile_processing_jobs(
    db: AsyncSession,
    connector_registry: ConnectorRegistry = default_registry,
    limit: int = 50,
) -> list[uuid.UUID]:
    """Polls provider status for jobs left `processing` and updates them once resolved."""
    result = await db.execute(
        select(PublishingJob)
        .where(PublishingJob.status == "processing", PublishingJob.external_post_id.is_not(None))
        .limit(limit)
    )
    jobs = list(result.scalars().all())
    updated: list[uuid.UUID] = []

    for job in jobs:
        social_account = await db.get(SocialAccount, job.social_account_id)
        if social_account is None or job.external_post_id is None:
            continue
        connector = connector_registry.get(social_account.platform)
        status_result = await connector.get_publish_status(job.external_post_id)

        if status_result.status == "processing":
            continue

        attempt_number = job.attempts + 1
        db.add(
            PublishAttempt(
                job_id=job.id,
                attempt_number=attempt_number,
                status=status_result.status,
                provider_request_id=status_result.external_post_id or job.external_post_id,
                sanitized_result=status_result.raw_response,
                error_code=status_result.error_code,
                error_message=status_result.error_message,
            )
        )
        job.attempts = attempt_number
        job.status = status_result.status
        job.last_error = status_result.error_message
        updated.append(job.id)

    await db.commit()
    return updated
