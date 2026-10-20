import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    database_ok = True
    redis_ok = True

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        database_ok = False

    try:
        await redis_client.ping()
    except Exception:
        logger.exception("Redis health check failed")
        redis_ok = False

    status = "ok" if database_ok and redis_ok else "degraded"

    return {
        "status": status,
        "database": "ok" if database_ok else "unavailable",
        "redis": "ok" if redis_ok else "unavailable",
    }
