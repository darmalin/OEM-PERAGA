"""Registration, QR credentials, and QR emails (spec 7, FEATURES/08)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, idempotency, outbox, ratelimit
from app.core.authorization import AuthContext, Scope
from app.core.config import get_settings
from app.core.context import current_actor_id
from app.core.crypto import encrypt
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.core.logging import mask_email
from app.core.pagination import Page
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitions.rules import EditionStatus
from app.modules.registrations import repository as repo
from app.modules.registrations import templates
from app.modules.registrations.models import (
    EmailJob,
    EmailLog,
    EmailTemplate,
    QrCredential,
    VisitorRegistration,
)
from app.modules.registrations.rules import (
    CredentialStatus,
    EmailEvent,
    EmailJobStatus,
    EmailKind,
    RegistrationChannel,
    RegistrationState,
    new_qr_token,
)
from app.modules.registrations.schemas import (
    CredentialOut,
    EmailJobOut,
    EmailLogOut,
    EmailTemplateIn,
    EmailTemplateOut,
    PublicRegistrationAccepted,
    PublicRegistrationIn,
    RegistrationDetailOut,
    RegistrationIn,
    RegistrationListParams,
    RegistrationOut,
    RevokeQrIn,
)
from app.modules.visitors import service as visitors_service
from app.modules.visitors.models import VisitorLead
from app.modules.visitors.rules import LeadSource, QrStatus, RegistrationStatus
from app.modules.visitors.schemas import LeadCreateIn, LeadOut

logger = structlog.get_logger("registrations")

ENTITY = "visitor_registration"
CREDENTIAL_ENTITY = "qr_credential"
SEND_TASK = "registrations.send_qr_email"
CREDENTIAL_AUDIT_FIELDS = ("status", "issued_at", "revoked_at", "revoke_reason", "registration_id")


# --- outputs -------------------------------------------------------------------------------


def _out(row: Any) -> RegistrationOut:
    reg, code, first_name, qr_status, email_status = row
    return RegistrationOut(
        id=reg.id,
        edition_id=reg.edition_id,
        visitor_lead_id=reg.visitor_lead_id,
        registration_code=code,
        first_name=first_name,
        channel=reg.channel,
        status=reg.status,
        registered_at=reg.registered_at,
        registered_by=reg.registered_by,
        qr_status=qr_status,
        email_status=email_status,
        version=reg.version,
    )


def _job_out(job: EmailJob, logs: list[EmailLog]) -> EmailJobOut:
    out = EmailJobOut.model_validate(job)
    out.logs = [EmailLogOut.model_validate(log) for log in logs]
    return out


async def _registration_out(
    session: AsyncSession, scope: Scope, registration_id: uuid.UUID
) -> RegistrationOut:
    row = await repo.get_row(session, scope, registration_id)
    if row is None:
        raise NotFound("Registration not found.")
    return _out(row)


# --- scope ---------------------------------------------------------------------------------


async def _scope_for_registration(
    session: AsyncSession, ctx: AuthContext, registration_id: uuid.UUID
) -> Scope:
    edition_id = await repo.edition_of(session, registration_id)
    if edition_id is None:
        raise NotFound("Registration not found.")
    try:
        return ctx.scope_for(edition_id)
    except NotFound as e:
        raise NotFound("Registration not found.") from e


async def _load_for_change(
    session: AsyncSession, ctx: AuthContext, registration_id: uuid.UUID
) -> tuple[VisitorRegistration, VisitorLead]:
    """Registration (locked) and its lead, both inside the caller's scope."""
    scope = await _scope_for_registration(session, ctx, registration_id)
    if await repo.get_row(session, scope, registration_id) is None:
        raise NotFound("Registration not found.")
    reg = await session.get(VisitorRegistration, registration_id, with_for_update=True)
    assert reg is not None  # noqa: S101 - found above in the same transaction
    lead = await visitors_service.get_lead_entity(
        session, scope, reg.visitor_lead_id, for_update=True
    )
    await exhibitions_service.ensure_writable(session, reg.edition_id)
    return reg, lead


# --- building blocks -----------------------------------------------------------------------


async def _issue_credential(
    session: AsyncSession, reg: VisitorRegistration, action: str = "issue"
) -> QrCredential:
    token, token_hash = new_qr_token()
    cred = QrCredential(
        edition_id=reg.edition_id,
        registration_id=reg.id,
        token_hash=token_hash,
        token_enc=encrypt(token),
        status=CredentialStatus.ACTIVE,
        issued_by=current_actor_id(),
    )
    session.add(cred)
    await session.flush()
    await session.refresh(cred)
    await audit.record(
        session,
        entity_type=CREDENTIAL_ENTITY,
        entity_id=cred.id,
        action=action,
        after=audit.snapshot(cred, CREDENTIAL_AUDIT_FIELDS),
        edition_id=reg.edition_id,
    )
    return cred


async def _template_for(session: AsyncSession, edition_id: uuid.UUID) -> EmailTemplate:
    """Latest edition template, else the latest system default (seeded by migration)."""
    key = EmailKind.QR_CONFIRMATION
    template = await repo.latest_template(session, edition_id, key)
    if template is None:
        template = await repo.latest_template(session, None, key)
    if template is None:
        raise RuntimeError("No QR_CONFIRMATION email template; run migrations")
    return template


def add_log(
    session: AsyncSession, job: EmailJob, event: EmailEvent, detail: str | None = None
) -> None:
    session.add(EmailLog(email_job_id=job.id, event=event, detail=detail))


async def _queue_email(
    session: AsyncSession, reg: VisitorRegistration, cred: QrCredential, recipient: str
) -> EmailJob:
    """Email job + outbox event in the caller's transaction; the worker sends it after commit."""
    template = await _template_for(session, reg.edition_id)
    job = EmailJob(
        edition_id=reg.edition_id,
        kind=EmailKind.QR_CONFIRMATION,
        registration_id=reg.id,
        qr_credential_id=cred.id,
        recipient=recipient,
        template_id=template.id,
        template_version=template.version,
        status=EmailJobStatus.QUEUED,
        triggered_by=current_actor_id(),
    )
    session.add(job)
    await session.flush()
    add_log(session, job, EmailEvent.QUEUED)
    await outbox.enqueue(
        session, "registration.qr_email", SEND_TASK, {"email_job_id": str(job.id)}, queue="email"
    )
    return job


async def register_lead(
    session: AsyncSession,
    lead: VisitorLead,
    channel: RegistrationChannel,
    *,
    send_email: bool = True,
) -> VisitorRegistration:
    """Register a locked lead, issue its QR, and queue the QR email. Shared by every channel.

    spec 7.1: the QR is issued right away, without waiting for telemarketing.
    """
    if await repo.active_registration(session, lead.id) is not None:
        raise Conflict(
            f"{lead.registration_code} is already registered.", code="ALREADY_REGISTERED"
        )
    reg = VisitorRegistration(
        edition_id=lead.edition_id,
        visitor_lead_id=lead.id,
        channel=channel,
        status=RegistrationState.REGISTERED,
        registered_by=current_actor_id(),
    )
    try:
        async with session.begin_nested():
            session.add(reg)
            await session.flush()
    except IntegrityError as e:
        # Two requests passed the check at once; the partial unique index decides.
        if "uq_visitor_registrations_active_lead" in str(e.orig):
            raise Conflict(
                f"{lead.registration_code} is already registered.", code="ALREADY_REGISTERED"
            ) from e
        raise
    await session.refresh(reg)
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=reg.id,
        action="create",
        after=audit.snapshot(reg, ("visitor_lead_id", "channel", "status", "registered_at")),
        edition_id=reg.edition_id,
    )
    cred = await _issue_credential(session, reg)
    await visitors_service.apply_changes(
        session,
        lead,
        {"registration_status": RegistrationStatus.REGISTERED, "qr_status": QrStatus.ACTIVE},
        action="register",
    )
    if send_email and lead.email:
        await _queue_email(session, reg, cred, lead.email)
    return reg


# Registration channel of a lead registered automatically on creation.
CHANNEL_FOR_SOURCE = {
    LeadSource.MANUAL: RegistrationChannel.ADMIN,
    LeadSource.EXCEL: RegistrationChannel.IMPORT,
    LeadSource.API: RegistrationChannel.API,
    LeadSource.WEBSITE: RegistrationChannel.WEBSITE,
    LeadSource.TELEMARKETING: RegistrationChannel.TELEMARKETING,
}


async def register_new_lead(session: AsyncSession, lead: VisitorLead) -> VisitorRegistration:
    """Owner decision 2026-10-22: every lead that comes in is registered and can enter the gate,
    whether or not telemarketing worked it. The QR email is sent later (Resend QR Email)."""
    return await register_lead(
        session, lead, CHANNEL_FOR_SOURCE[LeadSource(lead.source)], send_email=False
    )


async def register_backlog(session: AsyncSession, limit: int) -> int:
    """Register leads created before auto-registration (CLI register-backlog). Archived
    editions are skipped: their data is read-only."""
    editions = await exhibitions_service.edition_summaries(session, None)
    writable = [e.id for e in editions if e.status != EditionStatus.ARCHIVED]
    leads = await visitors_service.unregistered_leads(session, writable, limit)
    for lead in leads:
        await register_new_lead(session, lead)
    return len(leads)


# --- staff endpoints -----------------------------------------------------------------------


async def create_lead(session: AsyncSession, ctx: AuthContext, data: LeadCreateIn) -> LeadOut:
    """POST /visitor-leads: create and register in one transaction."""
    lead = await visitors_service.create_lead(session, ctx, data)
    await register_new_lead(session, lead)
    return await visitors_service.lead_out(session, lead)


async def create_registration(
    session: AsyncSession, ctx: AuthContext, data: RegistrationIn, key: str
) -> RegistrationOut:
    """POST /visitor-registrations. Idempotent per Idempotency-Key (spec 7, M4)."""
    claim_id, stored = await idempotency.claim(
        session, f"registrations:{ctx.user.id}", key, data.model_dump(mode="json")
    )
    if stored is not None:
        return RegistrationOut.model_validate(stored.response)
    scope = await visitors_service.scope_for_lead(session, ctx, data.visitor_lead_id)
    lead = await visitors_service.get_lead_entity(
        session, scope, data.visitor_lead_id, for_update=True
    )
    await exhibitions_service.ensure_writable(session, lead.edition_id)
    reg = await register_lead(
        session, lead, RegistrationChannel(data.channel), send_email=data.send_email
    )
    out = await _registration_out(session, scope, reg.id)
    assert claim_id is not None  # noqa: S101 - claim() returns one of the two
    await idempotency.store(session, claim_id, 201, out.model_dump(mode="json"))
    return out


async def list_registrations(
    session: AsyncSession, ctx: AuthContext, params: RegistrationListParams
) -> Page[RegistrationOut]:
    scope = ctx.scope_for(params.edition_id)
    rows, total = await repo.list_registrations(session, scope, params)
    return Page(
        items=[_out(r) for r in rows], total=total, page=params.page, page_size=params.page_size
    )


async def get_registration(
    session: AsyncSession, ctx: AuthContext, registration_id: uuid.UUID
) -> RegistrationDetailOut:
    scope = await _scope_for_registration(session, ctx, registration_id)
    base = await _registration_out(session, scope, registration_id)
    return RegistrationDetailOut(
        **base.model_dump(),
        credentials=[
            CredentialOut.model_validate(c)
            for c in await repo.credentials(session, registration_id)
        ],
        email_jobs=[
            _job_out(j, logs) for j, logs in await repo.email_jobs(session, registration_id)
        ],
    )


async def resend_qr(
    session: AsyncSession, ctx: AuthContext, registration_id: uuid.UUID, key: str
) -> EmailJobOut:
    """POST /visitor-registrations/{id}/resend-qr. Reuses the active credential (spec 7.2)."""
    claim_id, stored = await idempotency.claim(
        session, f"resend_qr:{ctx.user.id}", key, {"registration_id": str(registration_id)}
    )
    if stored is not None:
        return EmailJobOut.model_validate(stored.response)
    reg, lead = await _load_for_change(session, ctx, registration_id)
    if reg.status != RegistrationState.REGISTERED:
        raise Conflict("This registration is cancelled.", code="REGISTRATION_CANCELLED")
    cred = await repo.active_credential(session, reg.id)
    if cred is None:
        raise Conflict(
            "There is no active QR code. Revoke with reissue to create a new one.",
            code="QR_NOT_ACTIVE",
        )
    if not lead.email:
        raise ValidationFailed(
            "This visitor has no email address.", fields={"email": "Add an email first."}
        )
    job = await _queue_email(session, reg, cred, lead.email)
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=reg.id,
        action="resend_qr",
        after={"email_job_id": job.id, "recipient": mask_email(lead.email)},
        edition_id=reg.edition_id,
    )
    await session.refresh(job)
    out = _job_out(job, [])
    assert claim_id is not None  # noqa: S101 - claim() returns one of the two
    await idempotency.store(session, claim_id, 202, out.model_dump(mode="json"))
    return out


async def revoke_qr(
    session: AsyncSession, ctx: AuthContext, registration_id: uuid.UUID, data: RevokeQrIn
) -> RegistrationDetailOut:
    """POST /visitor-registrations/{id}/revoke-qr, optionally issuing a replacement."""
    reg, lead = await _load_for_change(session, ctx, registration_id)
    if reg.status != RegistrationState.REGISTERED:
        raise Conflict("This registration is cancelled.", code="REGISTRATION_CANCELLED")
    cred = await repo.active_credential(session, reg.id, for_update=True)
    if cred is None and not data.reissue:
        raise Conflict("The QR code is already revoked.", code="QR_NOT_ACTIVE")
    if cred is not None:
        before = audit.snapshot(cred, CREDENTIAL_AUDIT_FIELDS)
        cred.status = CredentialStatus.REVOKED
        cred.revoked_at = datetime.now(UTC)
        cred.revoked_by = ctx.user.id
        cred.revoke_reason = data.reason
        await session.flush()
        await audit.record(
            session,
            entity_type=CREDENTIAL_ENTITY,
            entity_id=cred.id,
            action="revoke",
            before=before,
            after=audit.snapshot(cred, CREDENTIAL_AUDIT_FIELDS),
            edition_id=reg.edition_id,
        )
    qr_status = QrStatus.REVOKED
    if data.reissue:
        new_cred = await _issue_credential(session, reg, action="reissue")
        qr_status = QrStatus.ACTIVE
        if data.send_email and lead.email:
            await _queue_email(session, reg, new_cred, lead.email)
    await visitors_service.apply_changes(
        session, lead, {"qr_status": qr_status}, action="qr_change"
    )
    return await get_registration(session, ctx, registration_id)


# --- email templates -----------------------------------------------------------------------


def _check_template_access(ctx: AuthContext, edition_id: uuid.UUID | None) -> None:
    if edition_id is None:
        if not ctx.has_global("edition.manage"):
            raise PermissionDenied("Only a global admin can change the system template.")
        return
    if not ctx.scope_for(edition_id, "edition.manage").full_access:
        raise PermissionDenied()


async def list_templates(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID | None, key: EmailKind
) -> list[EmailTemplateOut]:
    _check_template_access(ctx, edition_id)
    return [
        EmailTemplateOut.model_validate(t)
        for t in await repo.template_versions(session, edition_id, key)
    ]


async def create_template_version(
    session: AsyncSession, ctx: AuthContext, data: EmailTemplateIn
) -> EmailTemplateOut:
    """Templates are never edited in place; each save is a new version."""
    _check_template_access(ctx, data.edition_id)
    templates.validate(data.subject, data.body_text, data.body_html)
    latest = await repo.latest_template(session, data.edition_id, data.template_key)
    template = EmailTemplate(
        edition_id=data.edition_id,
        template_key=data.template_key,
        version=(latest.version + 1) if latest else 1,
        subject=data.subject,
        body_text=data.body_text,
        body_html=data.body_html,
        created_by=ctx.user.id,
    )
    try:
        async with session.begin_nested():
            session.add(template)
            await session.flush()
    except IntegrityError as e:
        raise Conflict("Someone saved this template at the same time. Reload.") from e
    await session.refresh(template)
    await audit.record(
        session,
        entity_type="email_template",
        entity_id=template.id,
        action="create",
        after=audit.snapshot(template, ("template_key", "version", "subject")),
        edition_id=data.edition_id,
    )
    return EmailTemplateOut.model_validate(template)


# --- public website registration -----------------------------------------------------------


async def public_register(
    session: AsyncSession, edition_code: str, data: PublicRegistrationIn, client_ip: str
) -> PublicRegistrationAccepted:
    """POST /public/editions/{code}/registrations. Neutral answer for duplicates (FEATURES/08)."""
    s = get_settings()
    await ratelimit.hit(f"public_reg:ip:{client_ip}", s.public_registration_per_ip_per_hour, 3600)
    accepted = PublicRegistrationAccepted()
    if data.contact_fax:
        logger.info("public_registration_honeypot", ip=client_ip)
        return accepted
    edition = await exhibitions_service.get_edition_by_code(session, edition_code)
    if (
        edition is None
        or edition.status != EditionStatus.ACTIVE
        or not edition.public_registration_open
    ):
        raise NotFound("Registration is not open for this event.", code="REGISTRATION_CLOSED")
    values = data.model_dump(exclude_unset=True, exclude={"contact_fax"})
    try:
        lead = await visitors_service.insert_lead(
            session, edition.id, values, source=LeadSource.WEBSITE
        )
    except visitors_service.DuplicateVisitor:
        # Do not reveal that the email or phone is already known.
        logger.info("public_registration_duplicate", edition=edition.code)
        return accepted
    await register_lead(session, lead, RegistrationChannel.WEBSITE)
    return accepted


# --- lookups for the gate module (callers check device or user scope first) -----------------


@dataclass(frozen=True)
class CredentialMatch:
    credential_id: uuid.UUID
    credential_active: bool
    edition_id: uuid.UUID
    registration_id: uuid.UUID
    registered: bool
    registration_code: str
    first_name: str


async def match_credential(session: AsyncSession, token_hash: str) -> CredentialMatch | None:
    row = await repo.match_credential(session, token_hash)
    if row is None:
        return None
    cred, reg, code, first_name = row
    return CredentialMatch(
        credential_id=cred.id,
        credential_active=cred.status == CredentialStatus.ACTIVE,
        edition_id=cred.edition_id,
        registration_id=reg.id,
        registered=reg.status == RegistrationState.REGISTERED,
        registration_code=code,
        first_name=first_name,
    )


async def gate_cache_rows(
    session: AsyncSession, edition_id: uuid.UUID
) -> list[tuple[str, str, str, str]]:
    """(token hash, ACTIVE/REVOKED/CANCELLED, Registration ID, first name) per credential."""
    out = []
    for token_hash, cred_status, reg_status, code, first_name in await repo.cache_rows(
        session, edition_id
    ):
        status = cred_status if reg_status == RegistrationState.REGISTERED else "CANCELLED"
        out.append((token_hash, status, code, first_name))
    return out


async def registration_labels(
    session: AsyncSession, registration_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, str]]:
    """registration id -> (Registration ID, first name)."""
    return await repo.labels(session, registration_ids) if registration_ids else {}


async def active_token_hashes(
    session: AsyncSession, registration_ids: list[uuid.UUID]
) -> list[str]:
    return await repo.token_hashes(session, registration_ids) if registration_ids else []


async def registration_for_override(
    session: AsyncSession, registration_id: uuid.UUID
) -> tuple[VisitorRegistration, uuid.UUID | None] | None:
    """Registration and its active credential id, for a supervisor override."""
    reg = await session.get(VisitorRegistration, registration_id)
    if reg is None:
        return None
    cred = await repo.active_credential(session, reg.id)
    return reg, cred.id if cred else None
