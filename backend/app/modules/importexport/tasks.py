import uuid

from app.core import outbox
from app.core.db import task_session
from app.modules.importexport.service import process_import
from app.worker import celery_app, run_async


async def run_import_event(event_id: uuid.UUID) -> str | None:
    async with task_session() as session:
        event = await outbox.get_event(session, event_id)
        if event is None:
            return None
        job_id = uuid.UUID(event.payload["job_id"])
        await session.commit()
        status = await process_import(session, job_id)
        return status.value if status else None


@celery_app.task(name="importexport.run_import", acks_late=True)
def run_import(event_id: str) -> str | None:
    return run_async(run_import_event(uuid.UUID(event_id)))
