async def test_list_accounts_requires_authentication(api_client):
    response = await api_client.get("/api/v1/accounts")

    assert response.status_code == 401


async def test_list_accounts_returns_empty_list_for_new_workspace(api_client, user_factory):
    identity = await user_factory()

    await api_client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )

    response = await api_client.get("/api/v1/accounts")

    assert response.status_code == 200
    assert response.json() == []
