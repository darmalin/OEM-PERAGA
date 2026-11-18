"""Order emails worker (orders.emails). Delivery, retries, and the email log are shared."""

import uuid
from typing import Any

from app.core.db import task_session
from app.core.email import OutgoingEmail, TransientEmailError
from app.modules.mail import service as mail_service
from app.modules.mail import tasks as mail_tasks
from app.modules.mail.rules import EmailEvent, EmailJobStatus
from app.modules.orders import emails
from app.worker import celery_app, run_async


async def send_order_email_event(event_id: uuid.UUID, *, final_attempt: bool = False) -> str | None:
    """Returns the final job status, or None when there was nothing to send."""
    async with task_session() as session:
        found = await mail_tasks.job_for_event(session, event_id)
        if found is None:
            return None
        job, payload = found
        rendered = await emails.render(session, job.kind, emails.payload_order_id(payload))
        if rendered is None:
            await mail_service.record_result(
                session,
                job,
                EmailJobStatus.CANCELLED,
                EmailEvent.CANCELLED,
                detail="The order no longer exists.",
            )
            await session.commit()
            return None
        job.subject = rendered.subject
        account = await mail_service.begin_attempt(session, job)
        await session.commit()
        job_id, recipient = job.id, job.recipient
    email = OutgoingEmail(
        to=recipient, subject=rendered.subject, text=rendered.text, html=rendered.html
    )
    return await mail_tasks.deliver(job_id, email, account, final_attempt=final_attempt)


@celery_app.task(bind=True, name=emails.TASK, max_retries=mail_tasks.MAX_RETRIES)
def send_order_email(self: Any, event_id: str) -> str | None:
    final = self.request.retries >= mail_tasks.MAX_RETRIES
    try:
        return run_async(send_order_email_event(uuid.UUID(event_id), final_attempt=final))
    except TransientEmailError as e:
        raise self.retry(exc=e, countdown=mail_tasks.retry_countdown(self.request.retries)) from e
