from datetime import UTC, datetime, timedelta

from app.modules.publishing.models import PublishingJob


async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


async def test_schedule_content_creates_job_and_updates_status(api_client, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    await _login(api_client, pipeline.identity)

    scheduled_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    response = await api_client.post(
        f"/api/v1/contents/{pipeline.content.id}/schedule",
        json={
            "assignments": [
                {
                    "social_account_id": str(pipeline.social_account.id),
                    "platform": "mock",
                    "scheduled_at": scheduled_at,
                }
            ]
        },
    )

    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "scheduled"

    content_resp = await api_client.get(f"/api/v1/contents/{pipeline.content.id}")
    assert content_resp.json()["status"] == "scheduled"


async def test_schedule_rejects_unknown_platform_variant(api_client, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    await _login(api_client, pipeline.identity)

    response = await api_client.post(
        f"/api/v1/contents/{pipeline.content.id}/schedule",
        json={
            "assignments": [
                {
                    "social_account_id": str(pipeline.social_account.id),
                    "platform": "facebook",
                    "scheduled_at": datetime.now(UTC).isoformat(),
                }
            ]
        },
    )

    assert response.status_code == 422


async def test_list_and_get_job(api_client, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    await _login(api_client, pipeline.identity)

    await api_client.post(
        f"/api/v1/contents/{pipeline.content.id}/schedule",
        json={
            "assignments": [
                {
                    "social_account_id": str(pipeline.social_account.id),
                    "platform": "mock",
                    "scheduled_at": datetime.now(UTC).isoformat(),
                }
            ]
        },
    )

    list_resp = await api_client.get("/api/v1/publishing/jobs")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 1
    job_id = body["items"][0]["id"]

    detail_resp = await api_client.get(f"/api/v1/publishing/jobs/{job_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["publish_attempts"] == []


async def test_retry_job_requires_eligible_status(api_client, db_session, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    await _login(api_client, pipeline.identity)

    schedule_resp = await api_client.post(
        f"/api/v1/contents/{pipeline.content.id}/schedule",
        json={
            "assignments": [
                {
                    "social_account_id": str(pipeline.social_account.id),
                    "platform": "mock",
                    "scheduled_at": datetime.now(UTC).isoformat(),
                }
            ]
        },
    )
    job_id = schedule_resp.json()[0]["id"]

    not_eligible = await api_client.post(f"/api/v1/publishing/jobs/{job_id}/retry")
    assert not_eligible.status_code == 409

    job = await db_session.get(PublishingJob, job_id)
    job.status = "failed"
    await db_session.commit()

    retried = await api_client.post(f"/api/v1/publishing/jobs/{job_id}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "scheduled"


async def test_cancel_content_cancels_scheduled_jobs(api_client, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    await _login(api_client, pipeline.identity)

    await api_client.post(
        f"/api/v1/contents/{pipeline.content.id}/schedule",
        json={
            "assignments": [
                {
                    "social_account_id": str(pipeline.social_account.id),
                    "platform": "mock",
                    "scheduled_at": datetime.now(UTC).isoformat(),
                }
            ]
        },
    )

    cancel_resp = await api_client.post(f"/api/v1/contents/{pipeline.content.id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["cancelled_jobs"] == 1

    content_resp = await api_client.get(f"/api/v1/contents/{pipeline.content.id}")
    assert content_resp.json()["status"] == "draft"


async def test_calendar_returns_scheduled_entries(api_client, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    await _login(api_client, pipeline.identity)

    scheduled_at = datetime.now(UTC) + timedelta(hours=2)
    await api_client.post(
        f"/api/v1/contents/{pipeline.content.id}/schedule",
        json={
            "assignments": [
                {
                    "social_account_id": str(pipeline.social_account.id),
                    "platform": "mock",
                    "scheduled_at": scheduled_at.isoformat(),
                }
            ]
        },
    )

    start = (scheduled_at - timedelta(hours=1)).isoformat()
    end = (scheduled_at + timedelta(hours=1)).isoformat()
    response = await api_client.get(
        "/api/v1/publishing/calendar", params={"start": start, "end": end}
    )

    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["content_title"] == pipeline.content.title
    assert entries[0]["platform"] == "mock"
