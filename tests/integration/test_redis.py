import pytest

from app.core.redis import redis_client


@pytest.mark.asyncio
async def test_redis_ping_succeeds():
    assert await redis_client.ping() is True
