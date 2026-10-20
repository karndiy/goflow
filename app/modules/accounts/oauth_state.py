import json
import secrets
import time

from app.core.redis import redis_client

STATE_TTL_SECONDS = 600
STATE_KEY_PREFIX = "oauth_state:"


async def create_oauth_state(workspace_id: str, user_id: str, platform: str) -> str:
    state = secrets.token_urlsafe(32)
    payload = json.dumps(
        {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "platform": platform,
            "created_at": time.time(),
        }
    )
    await redis_client.set(f"{STATE_KEY_PREFIX}{state}", payload, ex=STATE_TTL_SECONDS)
    return state


async def consume_oauth_state(state: str) -> dict | None:
    """One-time use: the key is atomically read and deleted, so a replayed state always fails."""
    payload = await redis_client.getdel(f"{STATE_KEY_PREFIX}{state}")
    if payload is None:
        return None
    return json.loads(payload)
