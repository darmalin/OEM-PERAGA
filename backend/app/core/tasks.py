from datetime import UTC, datetime

import structlog

from app.core import outbox
from app.core.db import task_session
from app.worker import celery_app, run_async

logger = structlog.get_logger("outbox")


async def dispatch_outbox_once(limit: int = 100) -> int:
    """Enqueue pending outbox events. Returns the number dispatched."""
    async with task_session() as session, session.begin():
        events = await outbox.claim_pending(session, limit)
        for event in events:
            celery_app.send_task(event.task_name, args=[str(event.id)], queue=event.queue)
            event.dispatched_at = datetime.now(UTC)
            event.dispatch_attempts += 1
        if events:
            logger.info("outbox_dispatched", count=len(events))
        return len(events)


@celery_app.task(name="core.dispatch_outbox")
def dispatch_outbox() -> int:
    return run_async(dispatch_outbox_once())
