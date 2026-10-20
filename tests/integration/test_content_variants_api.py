async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


async def test_create_list_update_delete_variant(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    content_resp = await api_client.post("/api/v1/contents", json={"title": "Launch post"})
    content_id = content_resp.json()["id"]

    create_resp = await api_client.post(
        f"/api/v1/contents/{content_id}/variants",
        json={"platform": "mock", "text": "Hello mock", "media_type": "none"},
    )
    assert create_resp.status_code == 201
    variant = create_resp.json()
    assert variant["platform"] == "mock"

    list_resp = await api_client.get(f"/api/v1/contents/{content_id}/variants")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    update_resp = await api_client.patch(
        f"/api/v1/contents/{content_id}/variants/{variant['id']}",
        json={"text": "Updated mock text"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["text"] == "Updated mock text"

    delete_resp = await api_client.delete(f"/api/v1/contents/{content_id}/variants/{variant['id']}")
    assert delete_resp.status_code == 204

    list_after = await api_client.get(f"/api/v1/contents/{content_id}/variants")
    assert list_after.json() == []


async def test_duplicate_platform_variant_rejected(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    content_resp = await api_client.post("/api/v1/contents", json={"title": "Dup test"})
    content_id = content_resp.json()["id"]

    await api_client.post(
        f"/api/v1/contents/{content_id}/variants",
        json={"platform": "mock", "text": "first"},
    )
    dup_resp = await api_client.post(
        f"/api/v1/contents/{content_id}/variants",
        json={"platform": "mock", "text": "second"},
    )

    assert dup_resp.status_code == 409
