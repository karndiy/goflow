from datetime import UTC, datetime

from app.connectors.base import PublishRequest, PublishResult
from app.connectors.mock.connector import MockConnector
from app.connectors.registry import ConnectorRegistry
from app.modules.content import media as media_service
from app.modules.content.models import ContentVariantMedia, MediaAsset
from app.modules.publishing import service
from app.modules.publishing.worker import process_job, reconcile_processing_jobs


def _registry_with_mock() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(MockConnector())
    return registry


class _SpyConnector(MockConnector):
    def __init__(self) -> None:
        super().__init__()
        self.last_request: PublishRequest | None = None

    async def publish(self, request: PublishRequest) -> PublishResult:
        self.last_request = request
        return await super().publish(request)


async def _queued_job(db_session, pipeline, options: dict):
    pipeline.variant.payload_json = {"options": options}
    db_session.add(pipeline.variant)
    await db_session.commit()

    job = await service.create_job(
        db_session,
        pipeline.variant.id,
        pipeline.social_account.id,
        datetime.now(UTC),
    )
    job.status = "queued"
    await db_session.commit()
    return job


async def test_process_job_success_marks_published(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    job = await _queued_job(db_session, pipeline, {"mock_outcome": "published"})

    result = await process_job(db_session, job.id, _registry_with_mock())

    assert result.status == "published"
    assert result.attempts == 1
    assert result.external_post_id is not None
    assert result.last_error is None


async def test_process_job_processing_outcome(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    job = await _queued_job(db_session, pipeline, {"mock_outcome": "processing"})

    result = await process_job(db_session, job.id, _registry_with_mock())

    assert result.status == "processing"
    assert result.external_post_id is not None


async def test_process_job_permanent_failure_marks_failed(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    job = await _queued_job(db_session, pipeline, {"mock_outcome": "failed_permanent"})

    result = await process_job(db_session, job.id, _registry_with_mock())

    assert result.status == "failed"
    assert result.last_error == "Mock permanent rejection"


async def test_process_job_transient_failure_reschedules_for_retry(
    db_session, mock_pipeline_factory
):
    pipeline = await mock_pipeline_factory()
    job = await _queued_job(db_session, pipeline, {"mock_outcome": "failed_transient"})
    original_scheduled_at = job.scheduled_at

    result = await process_job(db_session, job.id, _registry_with_mock())

    assert result.status == "scheduled"
    assert result.attempts == 1
    assert result.scheduled_at > original_scheduled_at


async def test_process_job_exhausted_retries_marks_failed(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    job = await _queued_job(db_session, pipeline, {"mock_outcome": "failed_transient"})

    registry = _registry_with_mock()
    for _ in range(3):
        job.status = "queued"
        await db_session.commit()
        job = await process_job(db_session, job.id, registry)

    assert job.status == "failed"
    assert job.attempts == 3


async def test_process_job_timeout_sets_unknown_without_retry(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    job = await _queued_job(db_session, pipeline, {"mock_outcome": "timeout"})

    result = await process_job(db_session, job.id, _registry_with_mock())

    assert result.status == "unknown"
    assert result.attempts == 1
    assert "timed out" in result.last_error


async def test_process_job_ignores_job_not_in_queued_state(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    job = await service.create_job(
        db_session,
        pipeline.variant.id,
        pipeline.social_account.id,
        datetime.now(UTC),
    )

    result = await process_job(db_session, job.id, _registry_with_mock())

    assert result.status == "scheduled"
    assert result.attempts == 0


async def test_process_job_passes_attached_media_urls_to_connector(
    db_session, mock_pipeline_factory
):
    pipeline = await mock_pipeline_factory()

    asset = MediaAsset(
        workspace_id=pipeline.identity.workspace.id,
        storage_key=f"{pipeline.identity.workspace.id}/test.png",
        mime_type="image/png",
        size_bytes=10,
    )
    db_session.add(asset)
    await db_session.flush()
    db_session.add(
        ContentVariantMedia(
            content_variant_id=pipeline.variant.id, media_asset_id=asset.id, position=0
        )
    )
    pipeline.variant.media_type = "image"
    await db_session.commit()

    job = await _queued_job(db_session, pipeline, {"mock_outcome": "published"})

    spy = _SpyConnector()
    registry = ConnectorRegistry()
    registry.register(spy)

    await process_job(db_session, job.id, registry)

    assert spy.last_request is not None
    assert spy.last_request.media_urls == [media_service.media_asset_to_read(asset).file_url]


async def test_reconcile_processing_jobs_resolves_to_published(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    job = await _queued_job(db_session, pipeline, {"mock_outcome": "processing"})

    registry = _registry_with_mock()
    connector = registry.get("mock")
    job = await process_job(db_session, job.id, registry)
    assert job.status == "processing"

    connector.set_status_response(
        job.external_post_id,
        PublishResult(status="published", external_post_id=job.external_post_id),
    )

    updated_ids = await reconcile_processing_jobs(db_session, registry)

    assert job.id in updated_ids
    await db_session.refresh(job)
    assert job.status == "published"
    assert job.attempts == 2
