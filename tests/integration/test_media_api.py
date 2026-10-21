from app.core import storage as storage_module


def _use_tmp_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_module.settings, "storage_root", str(tmp_path))


async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


async def test_upload_list_serve_and_delete_media(api_client, user_factory, monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    identity = await user_factory()
    await _login(api_client, identity)

    upload_resp = await api_client.post(
        "/api/v1/media", files={"file": ("a.jpg", b"abc123", "image/jpeg")}
    )
    assert upload_resp.status_code == 201
    asset = upload_resp.json()
    assert asset["mime_type"] == "image/jpeg"
    assert asset["size_bytes"] == 6
    assert asset["filename"] == "a.jpg"
    assert asset["file_url"].endswith(f"/api/v1/media/{asset['id']}/file")

    list_resp = await api_client.get("/api/v1/media")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    file_resp = await api_client.get(f"/api/v1/media/{asset['id']}/file")
    assert file_resp.status_code == 200
    assert file_resp.content == b"abc123"
    assert file_resp.headers["content-type"] == "image/jpeg"

    delete_resp = await api_client.delete(f"/api/v1/media/{asset['id']}")
    assert delete_resp.status_code == 204

    missing_resp = await api_client.get(f"/api/v1/media/{asset['id']}/file")
    assert missing_resp.status_code == 404


async def test_upload_rejects_unsupported_mime_type(
    api_client, user_factory, monkeypatch, tmp_path
):
    _use_tmp_storage(monkeypatch, tmp_path)
    identity = await user_factory()
    await _login(api_client, identity)

    resp = await api_client.post("/api/v1/media", files={"file": ("a.txt", b"hello", "text/plain")})
    assert resp.status_code == 422


async def test_media_metadata_is_workspace_scoped(api_client, user_factory, monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    owner = await user_factory()
    other = await user_factory()

    await _login(api_client, owner)
    upload_resp = await api_client.post(
        "/api/v1/media", files={"file": ("a.jpg", b"abc", "image/jpeg")}
    )
    media_id = upload_resp.json()["id"]

    await _login(api_client, other)
    list_resp = await api_client.get("/api/v1/media")
    assert list_resp.json()["total"] == 0

    delete_resp = await api_client.delete(f"/api/v1/media/{media_id}")
    assert delete_resp.status_code == 404


async def test_media_file_route_has_no_session_auth(
    api_client, user_factory, monkeypatch, tmp_path
):
    """Intentional: external platforms fetch media URLs server-to-server, no session cookie."""
    _use_tmp_storage(monkeypatch, tmp_path)
    identity = await user_factory()
    await _login(api_client, identity)
    upload_resp = await api_client.post(
        "/api/v1/media", files={"file": ("a.jpg", b"abc", "image/jpeg")}
    )
    media_id = upload_resp.json()["id"]

    await api_client.post("/api/v1/auth/logout")
    file_resp = await api_client.get(f"/api/v1/media/{media_id}/file")
    assert file_resp.status_code == 200
    assert file_resp.content == b"abc"


async def test_delete_media_blocked_while_attached_to_variant(
    api_client, user_factory, monkeypatch, tmp_path
):
    _use_tmp_storage(monkeypatch, tmp_path)
    identity = await user_factory()
    await _login(api_client, identity)

    content_resp = await api_client.post("/api/v1/contents", json={"title": "x"})
    content_id = content_resp.json()["id"]
    variant_resp = await api_client.post(
        f"/api/v1/contents/{content_id}/variants", json={"platform": "mock", "text": "hi"}
    )
    variant_id = variant_resp.json()["id"]

    upload_resp = await api_client.post(
        "/api/v1/media", files={"file": ("a.jpg", b"abc", "image/jpeg")}
    )
    media_id = upload_resp.json()["id"]

    await api_client.put(
        f"/api/v1/contents/{content_id}/variants/{variant_id}/media",
        json={"media_asset_ids": [media_id]},
    )

    delete_resp = await api_client.delete(f"/api/v1/media/{media_id}")
    assert delete_resp.status_code == 409
