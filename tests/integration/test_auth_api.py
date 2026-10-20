from app.core.security import SESSION_COOKIE_NAME


async def test_login_success_sets_cookie_and_returns_user(api_client, user_factory):
    identity = await user_factory()

    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )

    assert response.status_code == 200
    assert response.json()["email"] == identity.email
    assert SESSION_COOKIE_NAME in response.cookies


async def test_login_with_wrong_password_returns_401(api_client, user_factory):
    identity = await user_factory()

    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": "not-the-password"},
    )

    assert response.status_code == 401


async def test_me_requires_authentication(api_client):
    response = await api_client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_login_then_me_then_logout_then_me_fails(api_client, user_factory):
    identity = await user_factory()

    await api_client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )

    me_response = await api_client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == identity.email

    logout_response = await api_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204

    after_logout = await api_client.get("/api/v1/auth/me")
    assert after_logout.status_code == 401


async def test_workspace_get_and_patch(api_client, user_factory):
    identity = await user_factory(role="owner")

    await api_client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )

    get_response = await api_client.get("/api/v1/workspace")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == identity.workspace.name

    patch_response = await api_client.patch("/api/v1/workspace", json={"name": "Renamed Workspace"})
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "Renamed Workspace"


async def test_workspace_patch_denied_for_viewer_role(api_client, user_factory):
    identity = await user_factory(role="viewer")

    await api_client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )

    patch_response = await api_client.patch("/api/v1/workspace", json={"name": "Should Not Work"})
    assert patch_response.status_code == 403
