"""QR email worker. Delivery, retries, and the email log are shared (mail.tasks)."""

import uuid
from typing import Any

from app.core.crypto import decrypt
from app.core.db import task_session
from app.core.email import Attachment, OutgoingEmail, TransientEmailError
from app.modules.exhibitions import service as exhibitions_service
from app.modules.mail import service as mail_service
from app.modules.mail import tasks as mail_tasks
from app.modules.mail.rules import EmailEvent, EmailJobStatus
from app.modules.registrations import templates
from app.modules.registrations.models import EmailTemplate, QrCredential, VisitorRegistration
from app.modules.registrations.rules import CredentialStatus, qr_png
from app.modules.visitors.models import VisitorLead
from app.worker import celery_app, run_async

MAX_RETRIES = mail_tasks.MAX_RETRIES


async def send_qr_email_event(event_id: uuid.UUID, *, final_attempt: bool = False) -> str | None:
    """Returns the final job status, or None when there was nothing to send."""
    async with task_session() as session:
        found = await mail_tasks.job_for_event(session, event_id)
        if found is None:
            return None
        job, _ = found
        cred = (
            await session.get(QrCredential, job.qr_credential_id) if job.qr_credential_id else None
        )
        if cred is None or cred.status != CredentialStatus.ACTIVE:
            await mail_service.record_result(
                session,
                job,
                EmailJobStatus.CANCELLED,
                EmailEvent.CANCELLED,
                detail="QR code was revoked before sending.",
            )
            await session.commit()
            return None
        reg = await session.get(VisitorRegistration, cred.registration_id)
        assert reg is not None  # noqa: S101 - FK
        lead = await session.get(VisitorLead, reg.visitor_lead_id)
        assert job.edition_id is not None and job.template_id is not None  # noqa: S101
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
        job.subject = rendered.subject[:300]
        account = await mail_service.begin_attempt(session, job)
        await session.commit()
        job_id = job.id
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
    return await mail_tasks.deliver(job_id, email, account, final_attempt=final_attempt)


@celery_app.task(bind=True, name="registrations.send_qr_email", max_retries=MAX_RETRIES)
def send_qr_email(self: Any, event_id: str) -> str | None:
    final = self.request.retries >= MAX_RETRIES
    try:
        return run_async(send_qr_email_event(uuid.UUID(event_id), final_attempt=final))
    except TransientEmailError as e:
        raise self.retry(exc=e, countdown=mail_tasks.retry_countdown(self.request.retries)) from e
