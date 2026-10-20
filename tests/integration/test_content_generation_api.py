from datetime import UTC, datetime


async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


async def test_generate_variant_creates_pending_job(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    content_resp = await api_client.post("/api/v1/contents", json={"title": "AI draft"})
    content_id = content_resp.json()["id"]

    response = await api_client.post(
        f"/api/v1/contents/{content_id}/generate",
        json={"platform": "mock", "brief": "Announce our new feature"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["platform"] == "mock"

    poll_resp = await api_client.get(f"/api/v1/contents/{content_id}/generation-jobs/{body['id']}")
    assert poll_resp.status_code == 200
    assert poll_resp.json()["status"] == "pending"


async def test_generate_variant_requires_draft_content(api_client, mock_pipeline_factory):
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

    response = await api_client.post(
        f"/api/v1/contents/{pipeline.content.id}/generate",
        json={"platform": "mock", "brief": "Write something"},
    )

    assert response.status_code == 409


async def test_generation_jobs_are_workspace_scoped(api_client, user_factory):
    owner_a = await user_factory()
    owner_b = await user_factory()

    await _login(api_client, owner_a)
    content_resp = await api_client.post("/api/v1/contents", json={"title": "Workspace A"})
    content_id = content_resp.json()["id"]
    job_resp = await api_client.post(
        f"/api/v1/contents/{content_id}/generate", json={"platform": "mock", "brief": "hi"}
    )
    job_id = job_resp.json()["id"]
    await api_client.post("/api/v1/auth/logout")

    await _login(api_client, owner_b)
    response = await api_client.get(f"/api/v1/contents/{content_id}/generation-jobs/{job_id}")

    assert response.status_code == 404
