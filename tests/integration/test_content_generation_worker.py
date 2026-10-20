import httpx2
from sqlalchemy import select

import app.modules.assistant.service as assistant_service
from app.modules.content import service as content_service
from app.modules.content.models import ContentGenerationJob, ContentVariant


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [_FakeTextBlock(text)]
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, response=None, exception=None) -> None:
        self._response = response
        self._exception = exception

    async def create(self, **kwargs):
        if self._exception is not None:
            raise self._exception
        return self._response


class _FakeAsyncAnthropic:
    def __init__(self, response=None, exception=None, **kwargs) -> None:
        self.messages = _FakeMessages(response, exception)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _patch_anthropic(monkeypatch, *, response=None, exception=None):
    def factory(**kwargs):
        return _FakeAsyncAnthropic(response=response, exception=exception)

    monkeypatch.setattr(assistant_service.anthropic, "AsyncAnthropic", factory)


async def _configure_ai(db_session, workspace_id):
    await assistant_service.upsert_ai_settings(
        db_session, workspace_id, "sk-ant-test", "claude-opus-5"
    )


async def test_run_generation_job_updates_existing_variant(
    db_session, mock_pipeline_factory, monkeypatch
):
    pipeline = await mock_pipeline_factory()
    await _configure_ai(db_session, pipeline.identity.workspace.id)
    _patch_anthropic(monkeypatch, response=_FakeResponse("Brand new generated copy"))

    job = await content_service.create_generation_job(
        db_session, pipeline.content.id, "mock", "Write a launch post", pipeline.identity.user
    )

    await content_service.run_generation_job(db_session, job.id)

    refreshed_job = await db_session.get(ContentGenerationJob, job.id)
    assert refreshed_job.status == "completed"
    assert refreshed_job.generated_text == "Brand new generated copy"

    await db_session.refresh(pipeline.variant)
    assert pipeline.variant.text == "Brand new generated copy"


async def test_run_generation_job_creates_variant_for_new_platform(
    db_session, mock_pipeline_factory, monkeypatch
):
    pipeline = await mock_pipeline_factory()
    await _configure_ai(db_session, pipeline.identity.workspace.id)
    _patch_anthropic(monkeypatch, response=_FakeResponse("Facebook-flavored copy"))

    job = await content_service.create_generation_job(
        db_session, pipeline.content.id, "facebook", "Write a launch post", pipeline.identity.user
    )

    await content_service.run_generation_job(db_session, job.id)

    variant = (
        await db_session.execute(
            select(ContentVariant).where(
                ContentVariant.content_id == pipeline.content.id,
                ContentVariant.platform == "facebook",
            )
        )
    ).scalar_one()
    assert variant.text == "Facebook-flavored copy"


async def test_run_generation_job_without_ai_settings_fails(db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()

    job = await content_service.create_generation_job(
        db_session, pipeline.content.id, "mock", "Write something", pipeline.identity.user
    )

    await content_service.run_generation_job(db_session, job.id)

    refreshed_job = await db_session.get(ContentGenerationJob, job.id)
    assert refreshed_job.status == "failed"
    assert "not configured" in refreshed_job.error_message


async def test_run_generation_job_handles_claude_error(
    db_session, mock_pipeline_factory, monkeypatch
):
    pipeline = await mock_pipeline_factory()
    await _configure_ai(db_session, pipeline.identity.workspace.id)

    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx2.Response(401, request=req)
    auth_error = assistant_service.anthropic.AuthenticationError(
        "invalid api key", response=resp, body=None
    )
    _patch_anthropic(monkeypatch, exception=auth_error)

    job = await content_service.create_generation_job(
        db_session, pipeline.content.id, "mock", "Write something", pipeline.identity.user
    )

    await content_service.run_generation_job(db_session, job.id)

    refreshed_job = await db_session.get(ContentGenerationJob, job.id)
    assert refreshed_job.status == "failed"
    assert "Invalid Anthropic API key" in refreshed_job.error_message
