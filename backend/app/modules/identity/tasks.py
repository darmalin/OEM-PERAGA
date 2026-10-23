import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.crypto import decrypt
from app.core.db import task_session
from app.core.email import OutgoingEmail, TransientEmailError
from app.modules.identity import repository as repo
from app.modules.identity.models import PasswordResetToken
from app.modules.identity.service import RESET_SUBJECT
from app.modules.mail import service as mail_service
from app.modules.mail import tasks as mail_tasks
from app.modules.mail.rules import EmailEvent, EmailJobStatus
from app.worker import celery_app, run_async


async def send_password_reset_email(event_id: uuid.UUID, *, final_attempt: bool = False) -> bool:
    """Send the reset link once per email job. Returns True when an email went out."""
    async with task_session() as session:
        found = await mail_tasks.job_for_event(session, event_id)
        if found is None:
            return False
        job, payload = found
        reset = await session.get(PasswordResetToken, uuid.UUID(payload["reset_id"]))
        user = await repo.get_user(session, reset.user_id) if reset else None
        if (
            reset is None
            or reset.used_at
            or reset.expires_at < datetime.now(UTC)
            or user is None
            or not user.is_active
        ):
            await mail_service.record_result(
                session,
                job,
                EmailJobStatus.CANCELLED,
                EmailEvent.CANCELLED,
                detail="The reset link was used, expired, or the user is inactive.",
            )
            await session.commit()
            return False
        token = decrypt(payload["token_enc"])
        account = await mail_service.begin_attempt(session, job)
        await session.commit()
        job_id, recipient = job.id, job.recipient
    link = f"{get_settings().public_base_url}/reset-password?token={token}"
    email = OutgoingEmail(
        to=recipient,
        subject=RESET_SUBJECT,
        text=f"Use this link to set a new password. It expires soon.\n\n{link}\n",
        html=(
            "<p>Use this link to set a new password. It expires soon.</p>"
            f'<p><a href="{link}">Reset password</a></p>'
        ),
    )
    status = await mail_tasks.deliver(job_id, email, account, final_attempt=final_attempt)
    return status == EmailJobStatus.SENT


@celery_app.task(bind=True, name="identity.send_password_reset", max_retries=mail_tasks.MAX_RETRIES)
def send_password_reset(self: Any, event_id: str) -> bool:
    final = self.request.retries >= mail_tasks.MAX_RETRIES
    try:
        return run_async(send_password_reset_email(uuid.UUID(event_id), final_attempt=final))
    except TransientEmailError as e:
        raise self.retry(exc=e, countdown=mail_tasks.retry_countdown(self.request.retries)) from e
