"""QR email worker.

Delivery is at-least-once: SENDING is committed before the SMTP call, so a worker crash
mid-send leads to one more attempt on redelivery. A finished job (SENT, FAILED, CANCELLED)
is never sent again, and retries never touch the registration itself.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core import outbox
from app.core.crypto import decrypt
from app.core.db import task_session
from app.core.email import Attachment, OutgoingEmail, TransientEmailError, get_email_sender
from app.modules.exhibitions import service as exhibitions_service
from app.modules.registrations import templates
from app.modules.registrations.models import (
    EmailJob,
    EmailTemplate,
    QrCredential,
    VisitorRegistration,
)
from app.modules.registrations.rules import (
    FINAL_EMAIL_STATUSES,
    CredentialStatus,
    EmailEvent,
    EmailJobStatus,
    qr_png,
)
from app.modules.registrations.service import add_log
from app.modules.visitors.models import VisitorLead
from app.worker import celery_app, run_async

logger = structlog.get_logger("registrations.tasks")

MAX_RETRIES = 5


async def _prepare(event_id: uuid.UUID) -> tuple[uuid.UUID, OutgoingEmail] | None:
    """Mark the job SENDING and build the email, or finish it without sending."""
    async with task_session() as session:
        event = await outbox.get_event(session, event_id)
        if event is None:
            return None
        job = await session.get(
            EmailJob, uuid.UUID(event.payload["email_job_id"]), with_for_update=True
        )
        if job is None or job.status in FINAL_EMAIL_STATUSES:
            return None
        cred = (
            await session.get(QrCredential, job.qr_credential_id) if job.qr_credential_id else None
        )
        if cred is None or cred.status != CredentialStatus.ACTIVE:
            job.status = EmailJobStatus.CANCELLED
            add_log(session, job, EmailEvent.CANCELLED, "QR code was revoked before sending.")
            await session.commit()
            return None
        reg = await session.get(VisitorRegistration, cred.registration_id)
        assert reg is not None  # noqa: S101 - FK
        lead = await session.get(VisitorLead, reg.visitor_lead_id)
        edition = await exhibitions_service.get_edition_by_id(session, job.edition_id)
        template = await session.get(EmailTemplate, job.template_id)
        assert lead is not None and edition is not None and template is not None  # noqa: S101
        rendered = templates.render(
            template.subject,
            template.body_text,
            template.body_html,
            templates.context(
                first_name=lead.first_name,
                registration_code=lead.registration_code,
                edition_name=edition.name,
                edition_code=edition.code,
                start_date=edition.start_date,
                end_date=edition.end_date,
                city=edition.city,
            ),
        )
        png = qr_png(decrypt(cred.token_enc))
        job.status = EmailJobStatus.SENDING
        job.attempts += 1
        add_log(session, job, EmailEvent.ATTEMPT, f"Attempt {job.attempts}")
        await session.commit()
        email = OutgoingEmail(
            to=job.recipient,
            subject=rendered.subject,
            text=rendered.text,
            html=rendered.html,
            attachments=[
                Attachment(
                    filename=f"{lead.registration_code}-qr.png",
                    content=png,
                    mime_type="image/png",
                    content_id=templates.QR_IMAGE_CID,
                ),
            ],
            from_name=edition.email_sender_name,
            reply_to=edition.email_reply_to,
        )
        return job.id, email


async def _finish(
    job_id: uuid.UUID,
    status: EmailJobStatus,
    event: EmailEvent,
    *,
    detail: str | None = None,
    message_id: str | None = None,
) -> None:
    async with task_session() as session:
        job = await session.get(EmailJob, job_id, with_for_update=True)
        assert job is not None  # noqa: S101 - prepared above
        job.status = status
        if status == EmailJobStatus.SENT:
            job.sent_at = datetime.now(UTC)
            job.provider_message_id = message_id
            job.error_summary = None
        elif detail:
            job.error_summary = detail[:500]
        add_log(session, job, event, detail)
        await session.commit()


async def send_qr_email_event(event_id: uuid.UUID, *, final_attempt: bool = False) -> str | None:
    """Returns the final job status, or None when there was nothing to send."""
    prepared = await _prepare(event_id)
    if prepared is None:
        return None
    job_id, email = prepared
    try:
        message_id = get_email_sender().send(email)
    except TransientEmailError as e:
        if final_attempt:
            await _finish(job_id, EmailJobStatus.FAILED, EmailEvent.FAILED, detail=str(e))
            return EmailJobStatus.FAILED
        await _finish(job_id, EmailJobStatus.QUEUED, EmailEvent.RETRY, detail=str(e))
        raise
    except Exception as e:
        # Permanent (recipient refused, bad template data): retrying will not help.
        logger.exception("qr_email_failed", email_job_id=str(job_id))
        await _finish(job_id, EmailJobStatus.FAILED, EmailEvent.FAILED, detail=type(e).__name__)
        return EmailJobStatus.FAILED
    await _finish(job_id, EmailJobStatus.SENT, EmailEvent.SENT, message_id=message_id)
    return EmailJobStatus.SENT


@celery_app.task(bind=True, name="registrations.send_qr_email", max_retries=MAX_RETRIES)
def send_qr_email(self: Any, event_id: str) -> str | None:
    final = self.request.retries >= MAX_RETRIES
    try:
        return run_async(send_qr_email_event(uuid.UUID(event_id), final_attempt=final))
    except TransientEmailError as e:
        raise self.retry(exc=e, countdown=min(600, 30 * 2**self.request.retries)) from e
