async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


async def test_create_list_get_update_delete_draft(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    create_response = await api_client.post("/api/v1/contents", json={"title": "First draft"})
    assert create_response.status_code == 201
    content = create_response.json()
    assert content["title"] == "First draft"
    assert content["status"] == "draft"

    list_response = await api_client.get("/api/v1/contents")
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == content["id"]

    get_response = await api_client.get(f"/api/v1/contents/{content['id']}")
    assert get_response.status_code == 200

    patch_response = await api_client.patch(
        f"/api/v1/contents/{content['id']}", json={"title": "Updated draft"}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Updated draft"

    delete_response = await api_client.delete(f"/api/v1/contents/{content['id']}")
    assert delete_response.status_code == 204

    get_after_delete = await api_client.get(f"/api/v1/contents/{content['id']}")
    assert get_after_delete.status_code == 404


async def test_content_create_requires_authentication(api_client):
    response = await api_client.post("/api/v1/contents", json={"title": "Nope"})

    assert response.status_code == 401


async def test_cross_workspace_content_access_is_denied(api_client, user_factory):
    owner_a = await user_factory()
    owner_b = await user_factory()

    await _login(api_client, owner_a)
    create_response = await api_client.post("/api/v1/contents", json={"title": "Workspace A draft"})
    content_id = create_response.json()["id"]
    await api_client.post("/api/v1/auth/logout")

    await _login(api_client, owner_b)

    get_response = await api_client.get(f"/api/v1/contents/{content_id}")
    assert get_response.status_code == 404

    list_response = await api_client.get("/api/v1/contents")
    assert list_response.json()["total"] == 0

    patch_response = await api_client.patch(
        f"/api/v1/contents/{content_id}", json={"title": "Hijacked"}
    )
    assert patch_response.status_code == 404

    delete_response = await api_client.delete(f"/api/v1/contents/{content_id}")
    assert delete_response.status_code == 404
