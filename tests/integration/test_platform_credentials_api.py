from sqlalchemy import select

from app.core.encryption import decrypt_token
from app.modules.accounts.models import PlatformCredential


async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


async def test_set_list_and_delete_credential(api_client, user_factory, db_session):
    identity = await user_factory(role="owner")
    await _login(api_client, identity)

    set_resp = await api_client.put(
        "/api/v1/settings/platform-credentials/facebook",
        json={"app_id": "app-123", "app_secret": "super-secret"},
    )
    assert set_resp.status_code == 200
    body = set_resp.json()
    assert body["platform"] == "facebook"
    assert body["app_id"] == "app-123"
    assert body["has_secret"] is True
    assert "app_secret" not in body

    credential = (
        await db_session.execute(
            select(PlatformCredential).where(
                PlatformCredential.workspace_id == identity.workspace.id
            )
        )
    ).scalar_one()
    assert decrypt_token(credential.encrypted_app_secret) == "super-secret"

    list_resp = await api_client.get("/api/v1/settings/platform-credentials")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    delete_resp = await api_client.delete("/api/v1/settings/platform-credentials/facebook")
    assert delete_resp.status_code == 204

    list_after = await api_client.get("/api/v1/settings/platform-credentials")
    assert list_after.json() == []


async def test_set_credential_rejects_unsupported_platform(api_client, user_factory):
    identity = await user_factory(role="owner")
    await _login(api_client, identity)

    response = await api_client.put(
        "/api/v1/settings/platform-credentials/myspace",
        json={"app_id": "x", "app_secret": "y"},
    )

    assert response.status_code == 400


async def test_credential_endpoints_require_owner_or_admin(api_client, user_factory):
    identity = await user_factory(role="viewer")
    await _login(api_client, identity)

    response = await api_client.put(
        "/api/v1/settings/platform-credentials/facebook",
        json={"app_id": "app-123", "app_secret": "super-secret"},
    )

    assert response.status_code == 403
