import httpx2

import app.modules.assistant.service as assistant_service
from app.core.encryption import decrypt_token


async def _login(client, identity) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": identity.email, "password": identity.password},
    )
    assert response.status_code == 200


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.content = [_FakeTextBlock(text)]
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, response=None, exception=None) -> None:
        self._response = response
        self._exception = exception

    async def create(self, **kwargs):
        if self._exception is not None:
            raise self._exception
        return self._response


class _FakeAsyncAnthropic:
    def __init__(self, response=None, exception=None, **kwargs) -> None:
        self.messages = _FakeMessages(response, exception)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _patch_anthropic(monkeypatch, *, response=None, exception=None):
    def factory(**kwargs):
        return _FakeAsyncAnthropic(response=response, exception=exception)

    monkeypatch.setattr(assistant_service.anthropic, "AsyncAnthropic", factory)


def _fake_auth_error():
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx2.Response(401, request=req)
    return assistant_service.anthropic.AuthenticationError(
        "invalid api key", response=resp, body=None
    )


async def test_create_request_without_ai_settings_returns_503(api_client, user_factory):
    identity = await user_factory()
    await _login(api_client, identity)

    response = await api_client.post("/api/v1/requests", json={"prompt": "hello"})

    assert response.status_code == 503


async def test_set_ai_settings_requires_owner_or_admin(api_client, user_factory):
    identity = await user_factory(role="viewer")
    await _login(api_client, identity)

    response = await api_client.put(
        "/api/v1/settings/ai", json={"api_key": "sk-ant-test", "model": "claude-opus-5"}
    )

    assert response.status_code == 403


async def test_set_ai_settings_encrypts_key(api_client, user_factory, db_session):
    identity = await user_factory(role="owner")
    await _login(api_client, identity)

    response = await api_client.put(
        "/api/v1/settings/ai", json={"api_key": "sk-ant-test-key", "model": "claude-opus-5"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_api_key"] is True
    assert body["model"] == "claude-opus-5"
    assert "api_key" not in body

    ai_settings = await assistant_service.get_ai_settings(db_session, identity.workspace.id)
    assert decrypt_token(ai_settings.encrypted_api_key) == "sk-ant-test-key"


async def test_create_request_success(api_client, user_factory, monkeypatch):
    identity = await user_factory(role="owner")
    await _login(api_client, identity)
    await api_client.put(
        "/api/v1/settings/ai", json={"api_key": "sk-ant-test-key", "model": "claude-opus-5"}
    )

    _patch_anthropic(monkeypatch, response=_FakeResponse("Here is your answer."))

    response = await api_client.post(
        "/api/v1/requests", json={"prompt": "What should our next feature be?"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "answered"
    assert body["response"] == "Here is your answer."
    assert body["error_message"] is None


async def test_create_request_handles_auth_error(api_client, user_factory, monkeypatch):
    identity = await user_factory(role="owner")
    await _login(api_client, identity)
    await api_client.put(
        "/api/v1/settings/ai", json={"api_key": "sk-ant-bad-key", "model": "claude-opus-5"}
    )

    _patch_anthropic(monkeypatch, exception=_fake_auth_error())

    response = await api_client.post("/api/v1/requests", json={"prompt": "hello"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert "Invalid Anthropic API key" in body["error_message"]


async def test_create_request_handles_refusal(api_client, user_factory, monkeypatch):
    identity = await user_factory(role="owner")
    await _login(api_client, identity)
    await api_client.put(
        "/api/v1/settings/ai", json={"api_key": "sk-ant-test-key", "model": "claude-opus-5"}
    )

    _patch_anthropic(monkeypatch, response=_FakeResponse("", stop_reason="refusal"))

    response = await api_client.post("/api/v1/requests", json={"prompt": "hello"})

    assert response.json()["status"] == "failed"


async def test_list_and_search_requests(api_client, user_factory, monkeypatch):
    identity = await user_factory(role="owner")
    await _login(api_client, identity)
    await api_client.put(
        "/api/v1/settings/ai", json={"api_key": "sk-ant-test-key", "model": "claude-opus-5"}
    )
    _patch_anthropic(monkeypatch, response=_FakeResponse("answer"))

    await api_client.post("/api/v1/requests", json={"prompt": "add a calendar export feature"})
    await api_client.post("/api/v1/requests", json={"prompt": "unrelated question"})

    all_resp = await api_client.get("/api/v1/requests")
    assert all_resp.json()["total"] == 2

    filtered = await api_client.get("/api/v1/requests", params={"q": "calendar"})
    assert filtered.json()["total"] == 1


async def test_requests_are_workspace_scoped(api_client, user_factory, monkeypatch):
    owner_a = await user_factory(role="owner")
    owner_b = await user_factory(role="owner")

    await _login(api_client, owner_a)
    await api_client.put(
        "/api/v1/settings/ai", json={"api_key": "sk-ant-test-key", "model": "claude-opus-5"}
    )
    _patch_anthropic(monkeypatch, response=_FakeResponse("answer"))
    create_resp = await api_client.post("/api/v1/requests", json={"prompt": "workspace a only"})
    request_id = create_resp.json()["id"]
    await api_client.post("/api/v1/auth/logout")

    await _login(api_client, owner_b)
    detail_resp = await api_client.get(f"/api/v1/requests/{request_id}")
    assert detail_resp.status_code == 404

    list_resp = await api_client.get("/api/v1/requests")
    assert list_resp.json()["total"] == 0
