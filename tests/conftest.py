import pytest_asyncio

from app.core.database import engine
from app.core.redis import redis_client


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _dispose_connections_after_tests():
    yield
    await engine.dispose()
    await redis_client.aclose()
