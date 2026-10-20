import asyncio
import uuid

from app.connectors.bootstrap import register_default_connectors
from app.core.database import AsyncSessionLocal
from app.modules.publishing.worker import process_job

register_default_connectors()


def process_publishing_job(job_id: str) -> None:
    asyncio.run(_process_publishing_job(uuid.UUID(job_id)))


async def _process_publishing_job(job_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        await process_job(db, job_id)
