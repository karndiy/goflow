async def test_dashboard_summary_requires_auth(api_client):
    response = await api_client.get("/api/v1/dashboard/summary")

    assert response.status_code == 401


async def test_dashboard_summary_reflects_counts(api_client, mock_pipeline_factory):
    pipeline = await mock_pipeline_factory()
    await api_client.post(
        "/api/v1/auth/login",
        json={"email": pipeline.identity.email, "password": pipeline.identity.password},
    )

    response = await api_client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["content_by_status"]["draft"] == 1
    assert body["accounts"] == [{"platform": "mock", "status": "active", "count": 1}]
    assert body["jobs_by_status"] == {}
