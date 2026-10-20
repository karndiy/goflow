async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


async def test_create_and_list_releases(api_client, user_factory):
    identity = await user_factory(role="owner")
    await _login(api_client, identity)

    create_resp = await api_client.post(
        "/api/v1/releases",
        json={"version": "0.6.0", "title": "Dashboard launch", "description": "Added the UI."},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["version"] == "0.6.0"
    assert body["created_by_email"] == identity.email

    list_resp = await api_client.get("/api/v1/releases")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_create_release_requires_owner_or_admin(api_client, user_factory):
    identity = await user_factory(role="editor")
    await _login(api_client, identity)

    response = await api_client.post("/api/v1/releases", json={"version": "0.6.0", "title": "X"})

    assert response.status_code == 403


async def test_releases_require_authentication(api_client):
    response = await api_client.get("/api/v1/releases")

    assert response.status_code == 401


async def test_releases_are_workspace_scoped(api_client, user_factory):
    owner_a = await user_factory(role="owner")
    owner_b = await user_factory(role="owner")

    await _login(api_client, owner_a)
    await api_client.post(
        "/api/v1/releases", json={"version": "1.0.0", "title": "Workspace A release"}
    )
    await api_client.post("/api/v1/auth/logout")

    await _login(api_client, owner_b)
    response = await api_client.get("/api/v1/releases")

    assert response.json() == []
