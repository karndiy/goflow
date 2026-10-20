import asyncio

from app.modules.accounts import oauth_state


async def test_create_and_consume_oauth_state_round_trip():
    state = await oauth_state.create_oauth_state(
        workspace_id="workspace-1", user_id="user-1", platform="facebook"
    )

    data = await oauth_state.consume_oauth_state(state)

    assert data == {
        "workspace_id": "workspace-1",
        "user_id": "user-1",
        "platform": "facebook",
        "created_at": data["created_at"],
    }


async def test_consume_unknown_state_returns_none():
    assert await oauth_state.consume_oauth_state("never-issued") is None


async def test_consume_is_one_time_use():
    state = await oauth_state.create_oauth_state(
        workspace_id="workspace-1", user_id="user-1", platform="facebook"
    )

    first = await oauth_state.consume_oauth_state(state)
    second = await oauth_state.consume_oauth_state(state)

    assert first is not None
    assert second is None


async def test_state_expires_after_ttl(monkeypatch):
    monkeypatch.setattr(oauth_state, "STATE_TTL_SECONDS", 1)

    state = await oauth_state.create_oauth_state(
        workspace_id="workspace-1", user_id="user-1", platform="facebook"
    )
    await asyncio.sleep(1.5)

    assert await oauth_state.consume_oauth_state(state) is None
