async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


async def test_login_is_logged(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    response = await api_client.get("/api/v1/audit-logs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(item["action"] == "auth.login" for item in body["items"])


async def test_content_actions_are_logged(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    create_resp = await api_client.post("/api/v1/contents", json={"title": "Audited draft"})
    content_id = create_resp.json()["id"]
    await api_client.patch(f"/api/v1/contents/{content_id}", json={"title": "Renamed draft"})
    await api_client.delete(f"/api/v1/contents/{content_id}")

    response = await api_client.get("/api/v1/audit-logs")
    actions = [item["action"] for item in response.json()["items"]]

    assert "content.create" in actions
    assert "content.update" in actions
    assert "content.delete" in actions


async def test_audit_log_search_filters_results(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    await api_client.post("/api/v1/contents", json={"title": "Searchable draft"})

    matching = await api_client.get("/api/v1/audit-logs", params={"q": "content"})
    assert matching.json()["total"] >= 1
    assert all("content" in item["action"] for item in matching.json()["items"])

    no_match = await api_client.get("/api/v1/audit-logs", params={"q": "zzz_no_match"})
    assert no_match.json()["total"] == 0


async def test_audit_log_action_filter(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    await api_client.post("/api/v1/contents", json={"title": "Filter test"})

    response = await api_client.get("/api/v1/audit-logs", params={"action": "content.create"})
    items = response.json()["items"]

    assert len(items) >= 1
    assert all(item["action"] == "content.create" for item in items)


async def test_audit_logs_require_authentication(api_client):
    response = await api_client.get("/api/v1/audit-logs")

    assert response.status_code == 401


async def test_audit_logs_are_workspace_scoped(api_client, user_factory):
    owner_a = await user_factory()
    owner_b = await user_factory()

    await _login(api_client, owner_a)
    await api_client.post("/api/v1/contents", json={"title": "Workspace A content"})
    await api_client.post("/api/v1/auth/logout")

    await _login(api_client, owner_b)
    response = await api_client.get("/api/v1/audit-logs")

    actions_and_details = [(item["action"], item["details"]) for item in response.json()["items"]]
    assert not any(
        action == "content.create" and details.get("title") == "Workspace A content"
        for action, details in actions_and_details
    )
