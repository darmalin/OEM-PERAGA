import uuid
from datetime import UTC, datetime

from app.core import outbox
from app.core.config import get_settings
from app.core.context import Source, source_var
from app.core.db import task_session
from app.core.email import OutgoingEmail, TransientEmailError, get_email_sender
from app.modules.identity import service as identity_service
from app.modules.telemarketing.models import FollowupReminder, VisitorFollowup
from app.modules.telemarketing.service import queue_followup_reminders, run_assignment_job
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


async def send_reminder_event(event_id: uuid.UUID) -> bool:
    """At-most-once: sent_at is committed before sending, cleared again on a retriable error."""
    async with task_session() as session:
        event = await outbox.get_event(session, event_id)
        if event is None:
            return False
        reminder = await session.get(FollowupReminder, uuid.UUID(event.payload["reminder_id"]))
        if reminder is None or reminder.sent_at is not None:
            return False
        followup = await session.get(VisitorFollowup, reminder.followup_id)
        if followup is None or followup.status != "OPEN":
            return False
        assignee = await identity_service.get_user(session, followup.assigned_to)
        reminder.sent_at = datetime.now(UTC)
        await session.commit()
        email = OutgoingEmail(
            to=assignee.email,
            subject="Follow-up due soon",
            text=(
                f"A follow-up is due at {followup.due_at.isoformat()}.\n"
                f"{get_settings().public_base_url}/visitor-leads/{followup.visitor_lead_id}\n"
            ),
            html=(
                f"<p>A follow-up is due at {followup.due_at.isoformat()}.</p>"
                f'<p><a href="{get_settings().public_base_url}/visitor-leads/'
                f'{followup.visitor_lead_id}">Open lead</a></p>'
            ),
        )
        try:
            get_email_sender().send(email)
        except TransientEmailError:
            reminder.sent_at = None
            await session.commit()
            raise
        return True


@celery_app.task(name="telemarketing.queue_followup_reminders")
def queue_followup_reminders_task() -> int:
    return run_async(queue_reminders_once())


@celery_app.task(
    name="telemarketing.send_followup_reminder",
    autoretry_for=(TransientEmailError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def send_followup_reminder(event_id: str) -> bool:
    return run_async(send_reminder_event(uuid.UUID(event_id)))
