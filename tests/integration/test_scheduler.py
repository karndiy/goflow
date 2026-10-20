from datetime import UTC, datetime, timedelta

from app.modules.publishing import service
from app.modules.publishing.models import PublishingJob
from app.modules.publishing.scheduler import claim_due_jobs, recover_stuck_queued_jobs


async def test_claim_due_jobs_claims_only_past_due_scheduled_jobs(
    db_session, mock_pipeline_factory
):
    pipeline = await mock_pipeline_factory()
    now = datetime.now(UTC)

    due_job = await service.create_job(
        db_session, pipeline.variant.id, pipeline.social_account.id, now - timedelta(minutes=1)
    )
    future_job = await service.create_job(
        db_session, pipeline.variant.id, pipeline.social_account.id, now + timedelta(hours=1)
    )

    claimed = await claim_due_jobs(db_session, limit=10)

    assert due_job.id in claimed
    assert future_job.id not in claimed

    await db_session.refresh(due_job)
    await db_session.refresh(future_job)
    assert due_job.status == "queued"
    assert future_job.status == "scheduled"


async def test_claim_due_jobs_respects_limit(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    now = datetime.now(UTC)

    for _ in range(3):
        await service.create_job(
            db_session, pipeline.variant.id, pipeline.social_account.id, now - timedelta(minutes=1)
        )

    claimed = await claim_due_jobs(db_session, limit=2)

    assert len(claimed) == 2


async def test_recover_stuck_queued_jobs_resets_old_queued_jobs(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    now = datetime.now(UTC)

    job = await service.create_job(
        db_session, pipeline.variant.id, pipeline.social_account.id, now - timedelta(minutes=10)
    )
    job.status = "queued"
    await db_session.commit()

    stuck_job = await db_session.get(PublishingJob, job.id)
    stuck_job.updated_at = now - timedelta(minutes=30)
    await db_session.commit()

    recovered = await recover_stuck_queued_jobs(db_session, stuck_after=timedelta(minutes=5))

    assert job.id in recovered
    await db_session.refresh(job)
    assert job.status == "scheduled"


async def test_recover_stuck_queued_jobs_leaves_recent_queued_jobs_alone(
    db_session, mock_pipeline_factory
):
    pipeline = await mock_pipeline_factory()
    now = datetime.now(UTC)

    job = await service.create_job(
        db_session, pipeline.variant.id, pipeline.social_account.id, now - timedelta(minutes=1)
    )
    job.status = "queued"
    await db_session.commit()

    recovered = await recover_stuck_queued_jobs(db_session, stuck_after=timedelta(minutes=5))

    assert job.id not in recovered
    await db_session.refresh(job)
    assert job.status == "queued"
