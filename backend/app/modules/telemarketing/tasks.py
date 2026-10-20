import uuid

from app.core import outbox
from app.core.context import Source, source_var
from app.core.db import task_session
from app.modules.telemarketing.service import run_assignment_job
from app.worker import celery_app, run_async


async def run_assignment_event(event_id: uuid.UUID) -> str | None:
    source_var.set(Source.WORKER)
    async with task_session() as session:
        event = await outbox.get_event(session, event_id)
        if event is None:
            return None
        job_id = uuid.UUID(event.payload["job_id"])
        await session.commit()
        return await run_assignment_job(session, job_id)


@celery_app.task(name="telemarketing.run_assignment")
def run_assignment(event_id: str) -> str | None:
    return run_async(run_assignment_event(uuid.UUID(event_id)))
