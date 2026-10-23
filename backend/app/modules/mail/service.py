"""Outgoing email: sending accounts, the queue every email goes through, and the email log."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, outbox, ratelimit
from app.core.authorization import AuthContext
from app.core.context import current_actor_id
from app.core.crypto import decrypt, encrypt
from app.core.email import SmtpAccount, env_account
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed, check_version
from app.core.logging import mask_email
from app.core.pagination import Page
from app.modules.exhibitions import service as exhibitions_service
from app.modules.mail import repository as repo
from app.modules.mail.models import EmailAccount, EmailJob, EmailLog
from app.modules.mail.rules import SYSTEM_KINDS, EmailEvent, EmailJobStatus, EmailKind
from app.modules.mail.schemas import (
    EmailAccountBrief,
    EmailAccountIn,
    EmailAccountOut,
    EmailAccountUpdateIn,
    EmailJobListParams,
    EmailJobOut,
    EmailLogOut,
    TestEmailAccepted,
)

MANAGE = "email_account.manage"
READ_LOG = "email_log.read"
TEST_TASK = "mail.send_test_email"
ACCOUNT_ENTITY = "email_account"
_ACCOUNT_FIELDS = (
    "name",
    "from_name",
    "from_address",
    "reply_to",
    "host",
    "port",
    "security",
    "username",
    "is_active",
    "is_default",
)


def _require_manage(ctx: AuthContext) -> None:
    """Email accounts are system-wide: a global grant (Super Admin)."""
    if not ctx.has_global(MANAGE):
        raise PermissionDenied()


# --- queue (used by every module that sends email) -------------------------------------------


def add_log(
    session: AsyncSession, job: EmailJob, event: EmailEvent, detail: str | None = None
) -> None:
    session.add(EmailLog(email_job_id=job.id, event=event, detail=detail))


async def queue_email(
    session: AsyncSession,
    *,
    kind: EmailKind,
    recipient: str,
    task: str,
    payload: dict[str, Any] | None = None,
    edition_id: uuid.UUID | None = None,
    registration_id: uuid.UUID | None = None,
    qr_credential_id: uuid.UUID | None = None,
    visitor_lead_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
    template_version: int | None = None,
    subject: str | None = None,
    account_id: uuid.UUID | None = None,
) -> EmailJob:
    """Email job + outbox event in the caller's transaction; the worker sends it after commit.

    `payload` carries what the task needs besides the job (e.g. an encrypted reset token).
    """
    job = EmailJob(
        edition_id=edition_id,
        kind=kind,
        registration_id=registration_id,
        qr_credential_id=qr_credential_id,
        visitor_lead_id=visitor_lead_id,
        user_id=user_id,
        recipient=recipient,
        subject=subject,
        template_id=template_id,
        template_version=template_version,
        account_id=account_id,
        status=EmailJobStatus.QUEUED,
        triggered_by=current_actor_id(),
    )
    session.add(job)
    await session.flush()
    add_log(session, job, EmailEvent.QUEUED)
    await outbox.enqueue(
        session,
        f"mail.{kind.lower()}",
        task,
        {"email_job_id": str(job.id), **(payload or {})},
        queue="email",
    )
    return job


def _smtp(account: EmailAccount) -> SmtpAccount:
    return SmtpAccount(
        host=account.host,
        port=account.port,
        security=account.security,
        username=account.username,
        password=decrypt(account.password_enc) if account.password_enc else "",
        from_address=account.from_address,
        from_name=account.from_name,
        reply_to=account.reply_to,
    )


async def resolve_account(
    session: AsyncSession, job: EmailJob
) -> tuple[EmailAccount | None, SmtpAccount]:
    """Account for one attempt, decided at send time so a fixed account helps queued email.

    TEST: the account under test. Edition email: the edition's account when active. Else the
    default account, else the .env settings (no account configured yet).
    """
    account: EmailAccount | None = None
    if job.kind == EmailKind.TEST:
        account = await repo.get_account(session, job.account_id) if job.account_id else None
    elif job.edition_id is not None and job.kind not in SYSTEM_KINDS:
        edition = await exhibitions_service.get_edition_by_id(session, job.edition_id)
        if edition is not None and edition.email_account_id is not None:
            account = await repo.get_account(session, edition.email_account_id)
            if account is not None and not account.is_active:
                account = None
    if account is None and job.kind != EmailKind.TEST:
        account = await repo.default_account(session)
    if account is None:
        return None, env_account()
    return account, _smtp(account)


async def begin_attempt(session: AsyncSession, job: EmailJob) -> SmtpAccount:
    """Mark SENDING, count the attempt, record the account. The caller commits."""
    account, smtp = await resolve_account(session, job)
    job.account_id = account.id if account else None
    job.from_address = smtp.from_address
    job.status = EmailJobStatus.SENDING
    job.attempts += 1
    add_log(session, job, EmailEvent.ATTEMPT, f"Attempt {job.attempts}")
    return smtp


async def record_result(
    session: AsyncSession,
    job: EmailJob,
    status: EmailJobStatus,
    event: EmailEvent,
    *,
    detail: str | None = None,
    message_id: str | None = None,
) -> None:
    job.status = status
    if status == EmailJobStatus.SENT:
        job.sent_at = datetime.now(UTC)
        job.provider_message_id = message_id
        job.error_summary = None
    elif detail:
        job.error_summary = detail[:500]
    add_log(session, job, event, detail)
    if (
        job.kind == EmailKind.TEST
        and job.account_id
        and status
        in (
            EmailJobStatus.SENT,
            EmailJobStatus.FAILED,
        )
    ):
        account = await repo.get_account(session, job.account_id, for_update=True)
        if account is not None:
            account.last_test_at = datetime.now(UTC)
            account.last_test_ok = status == EmailJobStatus.SENT
            account.last_test_detail = (
                f"Sent to {mask_email(job.recipient)}"
                if account.last_test_ok
                else job.error_summary
            )


# --- accounts ------------------------------------------------------------------------------


def _account_out(account: EmailAccount) -> EmailAccountOut:
    out = EmailAccountOut.model_validate(account)
    out.has_password = bool(account.password_enc)
    return out


async def list_accounts(session: AsyncSession, ctx: AuthContext) -> list[EmailAccountOut]:
    _require_manage(ctx)
    return [_account_out(a) for a in await repo.list_accounts(session, only_active=False)]


async def account_choices(session: AsyncSession) -> list[EmailAccountBrief]:
    """Active accounts for the edition's Email Account select (edition admins)."""
    rows = await repo.list_accounts(session, only_active=True)
    return [EmailAccountBrief.model_validate(a) for a in rows]


async def get_account(
    session: AsyncSession, ctx: AuthContext, account_id: uuid.UUID
) -> EmailAccountOut:
    _require_manage(ctx)
    account = await repo.get_account(session, account_id)
    if account is None:
        raise NotFound("Email account not found.")
    return _account_out(account)


async def _flush_account(session: AsyncSession) -> None:
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError as e:
        raise Conflict(
            "An email account with this name already exists.",
            code="DUPLICATE_EMAIL_ACCOUNT",
            fields={"name": "Already exists."},
        ) from e


async def create_account(
    session: AsyncSession, ctx: AuthContext, data: EmailAccountIn
) -> EmailAccountOut:
    _require_manage(ctx)
    values = data.model_dump(exclude={"password"})
    account = EmailAccount(
        **values,
        password_enc=encrypt(data.password) if data.password else None,
        # The first account becomes the default, so system email has one at once.
        is_default=await repo.default_account(session) is None and data.is_active,
        created_by=ctx.user.id,
        updated_by=ctx.user.id,
    )
    session.add(account)
    await _flush_account(session)
    await session.refresh(account)
    await audit.record(
        session,
        entity_type=ACCOUNT_ENTITY,
        entity_id=account.id,
        action="create",
        after=audit.snapshot(account, _ACCOUNT_FIELDS),
    )
    return _account_out(account)


async def update_account(
    session: AsyncSession, ctx: AuthContext, account_id: uuid.UUID, data: EmailAccountUpdateIn
) -> EmailAccountOut:
    _require_manage(ctx)
    account = await repo.get_account(session, account_id, for_update=True)
    if account is None:
        raise NotFound("Email account not found.")
    check_version(account.version, data.version)
    changes = data.model_dump(exclude_unset=True, exclude={"version", "password"})
    if changes.get("is_active") is False and account.is_default:
        raise ValidationFailed(
            "Make another account the default before turning this one off.",
            fields={"is_active": "This is the default account."},
        )
    before = audit.snapshot(account, _ACCOUNT_FIELDS)
    for key, value in changes.items():
        # Required columns ignore an explicit null; optional ones are cleared by it.
        if value is not None or key in ("from_name", "reply_to", "username"):
            setattr(account, key, value)
    if data.password:
        account.password_enc = encrypt(data.password)
    account.updated_by = ctx.user.id
    await _flush_account(session)
    await session.refresh(account)
    after = audit.snapshot(account, _ACCOUNT_FIELDS)
    if data.password:
        after["password"] = "changed"  # noqa: S105 - audit marker, never the value
    await audit.record(
        session,
        entity_type=ACCOUNT_ENTITY,
        entity_id=account.id,
        action="update",
        before=before,
        after=after,
    )
    return _account_out(account)


async def set_default(
    session: AsyncSession, ctx: AuthContext, account_id: uuid.UUID
) -> EmailAccountOut:
    _require_manage(ctx)
    account = await repo.get_account(session, account_id, for_update=True)
    if account is None:
        raise NotFound("Email account not found.")
    if not account.is_active:
        raise ValidationFailed("Turn the account on before making it the default.")
    if not account.is_default:
        await repo.clear_default(session)
        await session.flush()
        account.is_default = True
        account.updated_by = ctx.user.id
        await session.flush()
        await session.refresh(account)
        await audit.record(
            session,
            entity_type=ACCOUNT_ENTITY,
            entity_id=account.id,
            action="set_default",
            after={"is_default": True},
        )
    return _account_out(account)


async def send_test(
    session: AsyncSession, ctx: AuthContext, account_id: uuid.UUID
) -> TestEmailAccepted:
    """Queue a test email to the account's own address; the result lands on the account."""
    _require_manage(ctx)
    await ratelimit.hit(f"mail_test:{ctx.user.id}", 10, 3600)
    account = await repo.get_account(session, account_id)
    if account is None:
        raise NotFound("Email account not found.")
    job = await queue_email(
        session,
        kind=EmailKind.TEST,
        recipient=account.from_address,
        task=TEST_TASK,
        subject="EMS test email",
        account_id=account.id,
        user_id=ctx.user.id,
    )
    return TestEmailAccepted(email_job_id=job.id, recipient=account.from_address)


# --- log -----------------------------------------------------------------------------------


def _visible(ctx: AuthContext, params_scope: str) -> Any:
    if params_scope == "system":
        _require_manage(ctx)
        return repo.visibility(None, system=True)
    return repo.visibility(ctx.edition_ids(READ_LOG), system=False)


async def _job_outs(session: AsyncSession, rows: Any, with_logs: bool) -> list[EmailJobOut]:
    jobs = [r[0] for r in rows]
    logs = await repo.logs_for(session, [j.id for j in jobs]) if with_logs else {}
    out = []
    for job, account_name in rows:
        item = EmailJobOut.model_validate(job)
        item.account_name = account_name
        item.logs = [EmailLogOut.model_validate(x) for x in logs.get(job.id, [])]
        out.append(item)
    return out


async def list_jobs(
    session: AsyncSession, ctx: AuthContext, params: EmailJobListParams
) -> Page[EmailJobOut]:
    if params.edition_id is not None and params.scope == "editions":
        ctx.scope_for(params.edition_id, READ_LOG)  # 404 for an edition out of reach
    rows, total = await repo.list_jobs(session, _visible(ctx, params.scope), params)
    return Page(
        items=await _job_outs(session, rows, with_logs=False),
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def get_job(session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID) -> EmailJobOut:
    row = await repo.get_job_row(session, _visible(ctx, "editions"), job_id)
    if row is None and ctx.has_global(MANAGE):
        row = await repo.get_job_row(session, _visible(ctx, "system"), job_id)
    if row is None:
        raise NotFound("Email not found.")
    return (await _job_outs(session, [row], with_logs=True))[0]


async def jobs_for_registration(
    session: AsyncSession, registration_id: uuid.UUID
) -> list[EmailJobOut]:
    """For the registration page; the caller already checked access to the registration."""
    return await _job_outs(
        session, await repo.jobs_for_registration(session, registration_id), with_logs=True
    )


def latest_status_for(registration_id: Any) -> Any:
    return repo.latest_status_for(registration_id)
