from app.core import storage as storage_module


def _use_tmp_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_module.settings, "storage_root", str(tmp_path))


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


async def test_set_variant_media_derives_media_type(
    api_client, user_factory, monkeypatch, tmp_path
):
    _use_tmp_storage(monkeypatch, tmp_path)
    identity = await user_factory()
    await _login(api_client, identity)

    content_resp = await api_client.post("/api/v1/contents", json={"title": "With media"})
    content_id = content_resp.json()["id"]
    variant_resp = await api_client.post(
        f"/api/v1/contents/{content_id}/variants",
        json={"platform": "mock", "text": "hello", "media_type": "none"},
    )
    variant_id = variant_resp.json()["id"]
    assert variant_resp.json()["media"] == []

    upload_resp = await api_client.post(
        "/api/v1/media", files={"file": ("photo.png", b"fake-png-bytes", "image/png")}
    )
    media_id = upload_resp.json()["id"]

    set_resp = await api_client.put(
        f"/api/v1/contents/{content_id}/variants/{variant_id}/media",
        json={"media_asset_ids": [media_id]},
    )
    assert set_resp.status_code == 200
    body = set_resp.json()
    assert body["media_type"] == "image"
    assert [m["id"] for m in body["media"]] == [media_id]

    clear_resp = await api_client.put(
        f"/api/v1/contents/{content_id}/variants/{variant_id}/media",
        json={"media_asset_ids": []},
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["media_type"] == "none"
    assert clear_resp.json()["media"] == []


async def test_set_variant_media_rejects_unknown_asset(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    content_resp = await api_client.post("/api/v1/contents", json={"title": "Bad media"})
    content_id = content_resp.json()["id"]
    variant_resp = await api_client.post(
        f"/api/v1/contents/{content_id}/variants", json={"platform": "mock", "text": "hi"}
    )
    variant_id = variant_resp.json()["id"]

    resp = await api_client.put(
        f"/api/v1/contents/{content_id}/variants/{variant_id}/media",
        json={"media_asset_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    assert resp.status_code == 422
