import asyncio
import logging

from app.connectors.bootstrap import register_default_connectors
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import configure_logging
from app.modules.publishing.scheduler import claim_due_jobs, recover_stuck_queued_jobs
from app.modules.publishing.worker import reconcile_processing_jobs
from app.tasks.jobs import process_publishing_job
from app.tasks.queue import publishing_queue

logger = logging.getLogger(__name__)
settings = get_settings()

POLL_INTERVAL_SECONDS = 5


async def run_once() -> None:
    async with AsyncSessionLocal() as db:
        job_ids = await claim_due_jobs(db)
    for job_id in job_ids:
        publishing_queue.enqueue(process_publishing_job, str(job_id))
        logger.info("Enqueued publishing job %s", job_id)

    async with AsyncSessionLocal() as db:
        recovered = await recover_stuck_queued_jobs(db)
    for job_id in recovered:
        logger.warning("Recovered stuck job %s back to scheduled", job_id)

    async with AsyncSessionLocal() as db:
        reconciled = await reconcile_processing_jobs(db)
    for job_id in reconciled:
        logger.info("Reconciled processing job %s", job_id)


async def run_forever() -> None:
    register_default_connectors()
    logger.info("GoFlow scheduler started, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await run_once()
        except Exception:
            logger.exception("Scheduler loop iteration failed")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    configure_logging(settings.log_level)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
