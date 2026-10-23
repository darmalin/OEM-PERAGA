"""Email delivery shared by every email task, and the test email task.

Delivery is at-least-once: SENDING is committed before the SMTP call, so a worker crash
mid-send leads to one more attempt on redelivery. A finished job (SENT, FAILED, CANCELLED)
is never sent again.
"""

import uuid
from typing import Any

import structlog

from app.core import outbox
from app.core.db import task_session
from app.core.email import (
    OutgoingEmail,
    PermanentEmailError,
    SmtpAccount,
    TransientEmailError,
    get_email_sender,
)
from app.modules.mail import service
from app.modules.mail.models import EmailJob
from app.modules.mail.rules import FINAL_EMAIL_STATUSES, EmailEvent, EmailJobStatus
from app.worker import celery_app, run_async

logger = structlog.get_logger("mail.tasks")

MAX_RETRIES = 5


async def job_for_event(
    session: Any, event_id: uuid.UUID
) -> tuple[EmailJob, dict[str, Any]] | None:
    """The locked, unfinished job of an outbox event and the event payload; None to skip."""
    event = await outbox.get_event(session, event_id)
    if event is None:
        return None
    job = await session.get(
        EmailJob, uuid.UUID(event.payload["email_job_id"]), with_for_update=True
    )
    if job is None or job.status in FINAL_EMAIL_STATUSES:
        return None
    return job, dict(event.payload)


async def finish(
    job_id: uuid.UUID,
    status: EmailJobStatus,
    event: EmailEvent,
    *,
    detail: str | None = None,
    message_id: str | None = None,
) -> None:
    async with task_session() as session:
        job = await session.get(EmailJob, job_id, with_for_update=True)
        assert job is not None  # noqa: S101 - prepared before sending
        await service.record_result(
            session, job, status, event, detail=detail, message_id=message_id
        )
        await session.commit()


async def deliver(
    job_id: uuid.UUID, email: OutgoingEmail, account: SmtpAccount, *, final_attempt: bool
) -> str:
    """Send an email whose job `begin_attempt` already marked SENDING; returns the final status.

    Raises TransientEmailError when the task should retry.
    """
    try:
        message_id = get_email_sender().send(email, account)
    except TransientEmailError as e:
        if final_attempt:
            await finish(job_id, EmailJobStatus.FAILED, EmailEvent.FAILED, detail=str(e))
            return EmailJobStatus.FAILED
        await finish(job_id, EmailJobStatus.QUEUED, EmailEvent.RETRY, detail=str(e))
        raise
    except PermanentEmailError as e:
        await finish(job_id, EmailJobStatus.FAILED, EmailEvent.FAILED, detail=str(e))
        return EmailJobStatus.FAILED
    except Exception as e:
        # Unexpected (bad template data, broken account settings): retrying will not help.
        logger.exception("email_failed", email_job_id=str(job_id))
        await finish(job_id, EmailJobStatus.FAILED, EmailEvent.FAILED, detail=type(e).__name__)
        return EmailJobStatus.FAILED
    await finish(job_id, EmailJobStatus.SENT, EmailEvent.SENT, message_id=message_id)
    return EmailJobStatus.SENT


def retry_countdown(retries: int) -> int:
    return min(600, 30 * (1 << retries))


# --- test email ----------------------------------------------------------------------------


async def send_test_email_event(event_id: uuid.UUID, *, final_attempt: bool = False) -> str | None:
    async with task_session() as session:
        found = await job_for_event(session, event_id)
        if found is None:
            return None
        job, _ = found
        account = await service.begin_attempt(session, job)
        await session.commit()
        job_id, recipient = job.id, job.recipient
    email = OutgoingEmail(
        to=recipient,
        subject="EMS test email",
        text="This is a test email from EMS. The email account works.\n",
        html="<p>This is a test email from EMS. The email account works.</p>",
    )
    return await deliver(job_id, email, account, final_attempt=final_attempt)


@celery_app.task(bind=True, name=service.TEST_TASK, max_retries=1)
def send_test_email(self: Any, event_id: str) -> str | None:
    # One quick retry only: the admin is waiting on the result.
    final = self.request.retries >= 1
    try:
        return run_async(send_test_email_event(uuid.UUID(event_id), final_attempt=final))
    except TransientEmailError as e:
        raise self.retry(exc=e, countdown=5) from e
