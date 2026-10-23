import uuid
from datetime import UTC, datetime
from typing import Any

from app.core import outbox
from app.core.config import get_settings
from app.core.context import Source, source_var
from app.core.db import task_session
from app.core.email import OutgoingEmail, TransientEmailError
from app.modules.mail import service as mail_service
from app.modules.mail import tasks as mail_tasks
from app.modules.mail.rules import EmailEvent, EmailJobStatus
from app.modules.telemarketing.models import FollowupReminder, VisitorFollowup
from app.modules.telemarketing.service import (
    REMINDER_SUBJECT,
    queue_followup_reminders,
    run_assignment_job,
)
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


async def queue_reminders_once() -> int:
    async with task_session() as session:
        count = await queue_followup_reminders(session)
        await session.commit()
        return count


async def send_reminder_event(event_id: uuid.UUID, *, final_attempt: bool = False) -> bool:
    """Send one follow-up reminder through the shared email queue (mail.tasks)."""
    async with task_session() as session:
        found = await mail_tasks.job_for_event(session, event_id)
        if found is None:
            return False
        job, payload = found
        reminder = await session.get(FollowupReminder, uuid.UUID(payload["reminder_id"]))
        followup = await session.get(VisitorFollowup, reminder.followup_id) if reminder else None
        if (
            reminder is None
            or reminder.sent_at is not None
            or followup is None
            or (followup.status != "OPEN")
        ):
            await mail_service.record_result(
                session,
                job,
                EmailJobStatus.CANCELLED,
                EmailEvent.CANCELLED,
                detail="The follow-up is no longer open.",
            )
            await session.commit()
            return False
        account = await mail_service.begin_attempt(session, job)
        await session.commit()
        job_id, recipient, reminder_id = job.id, job.recipient, reminder.id
        due_at, lead_id = followup.due_at, followup.visitor_lead_id
    base = get_settings().public_base_url
    email = OutgoingEmail(
        to=recipient,
        subject=REMINDER_SUBJECT,
        text=f"A follow-up is due at {due_at.isoformat()}.\n{base}/app/visitor-leads/{lead_id}\n",
        html=(
            f"<p>A follow-up is due at {due_at.isoformat()}.</p>"
            f'<p><a href="{base}/app/visitor-leads/{lead_id}">Open lead</a></p>'
        ),
    )
    status = await mail_tasks.deliver(job_id, email, account, final_attempt=final_attempt)
    if status != EmailJobStatus.SENT:
        return False
    async with task_session() as session:
        sent = await session.get(FollowupReminder, reminder_id, with_for_update=True)
        if sent is not None and sent.sent_at is None:
            sent.sent_at = datetime.now(UTC)
            await session.commit()
    return True


@celery_app.task(name="telemarketing.queue_followup_reminders")
def queue_followup_reminders_task() -> int:
    return run_async(queue_reminders_once())


@celery_app.task(
    bind=True, name="telemarketing.send_followup_reminder", max_retries=mail_tasks.MAX_RETRIES
)
def send_followup_reminder(self: Any, event_id: str) -> bool:
    final = self.request.retries >= mail_tasks.MAX_RETRIES
    try:
        return run_async(send_reminder_event(uuid.UUID(event_id), final_attempt=final))
    except TransientEmailError as e:
        raise self.retry(exc=e, countdown=mail_tasks.retry_countdown(self.request.retries)) from e
