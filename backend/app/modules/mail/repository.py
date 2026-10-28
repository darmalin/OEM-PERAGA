"""Email accounts and the email log. Edition visibility is applied by the caller's filter."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Row, Select, and_, false, func, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.modules.mail.models import EmailAccount, EmailJob, EmailLog
from app.modules.mail.schemas import EmailJobListParams


async def list_accounts(session: AsyncSession, only_active: bool) -> list[EmailAccount]:
    stmt = select(EmailAccount).order_by(EmailAccount.is_default.desc(), EmailAccount.name)
    if only_active:
        stmt = stmt.where(EmailAccount.is_active)
    return list((await session.scalars(stmt)).all())


async def get_account(
    session: AsyncSession, account_id: uuid.UUID, *, for_update: bool = False
) -> EmailAccount | None:
    return await session.get(EmailAccount, account_id, with_for_update=for_update)


async def default_account(session: AsyncSession) -> EmailAccount | None:
    return await session.scalar(
        select(EmailAccount).where(EmailAccount.is_default, EmailAccount.is_active)
    )


async def clear_default(session: AsyncSession) -> None:
    await session.execute(
        update(EmailAccount).where(EmailAccount.is_default).values(is_default=False)
    )


def visibility(edition_ids: set[uuid.UUID] | None, system: bool) -> ColumnElement[bool]:
    """Editions the caller may read (None = all) and, for super admins, emails without one."""
    if system:
        return EmailJob.edition_id.is_(None)
    if edition_ids is None:
        return EmailJob.edition_id.is_not(None)
    return EmailJob.edition_id.in_(edition_ids) if edition_ids else false()


def _filters(params: EmailJobListParams) -> ColumnElement[bool]:
    conds: list[ColumnElement[bool]] = []
    if params.edition_id:
        conds.append(EmailJob.edition_id == params.edition_id)
    if params.kind:
        conds.append(EmailJob.kind == params.kind)
    if params.status:
        conds.append(EmailJob.status == params.status)
    if params.account_id:
        conds.append(EmailJob.account_id == params.account_id)
    if params.q:
        like = f"%{params.q.strip().lower()}%"
        conds.append(func.lower(EmailJob.recipient).like(like))
    if params.queued_from:
        conds.append(EmailJob.queued_at >= params.queued_from)
    if params.queued_to:
        conds.append(EmailJob.queued_at < params.queued_to)
    return and_(true(), *conds)


def _with_account[*Ts](stmt: Select[*Ts]) -> Select[*Ts]:
    return stmt.outerjoin(EmailAccount, EmailAccount.id == EmailJob.account_id)


async def list_jobs(
    session: AsyncSession, visible: ColumnElement[bool], params: EmailJobListParams
) -> tuple[Sequence[Any], int]:
    where = visible & _filters(params)
    total = await session.scalar(select(func.count()).select_from(EmailJob).where(where)) or 0
    stmt = (
        _with_account(select(EmailJob, EmailAccount.name))
        .where(where)
        .order_by(EmailJob.queued_at.desc(), EmailJob.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    )
    return (await session.execute(stmt)).all(), total


async def get_job_row(
    session: AsyncSession, visible: ColumnElement[bool], job_id: uuid.UUID
) -> Any | None:
    stmt = _with_account(select(EmailJob, EmailAccount.name)).where(visible, EmailJob.id == job_id)
    return (await session.execute(stmt)).first()


async def logs_for(
    session: AsyncSession, job_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[EmailLog]]:
    out: dict[uuid.UUID, list[EmailLog]] = {j: [] for j in job_ids}
    if not job_ids:
        return out
    rows = await session.scalars(
        select(EmailLog)
        .where(EmailLog.email_job_id.in_(job_ids))
        .order_by(EmailLog.occurred_at, EmailLog.id)
    )
    for log in rows:
        out[log.email_job_id].append(log)
    return out


async def jobs_for_registration(
    session: AsyncSession, registration_id: uuid.UUID
) -> Sequence[Row[EmailJob, str]]:
    stmt = (
        _with_account(select(EmailJob, EmailAccount.name))
        .where(EmailJob.registration_id == registration_id)
        .order_by(EmailJob.queued_at.desc(), EmailJob.id.desc())
    )
    return (await session.execute(stmt)).all()


def latest_status_for(registration_id: Any) -> Any:
    """Correlated scalar subquery: status of the newest email of a registration."""
    return (
        select(EmailJob.status)
        .where(EmailJob.registration_id == registration_id)
        .order_by(EmailJob.queued_at.desc(), EmailJob.id.desc())
        .limit(1)
        .scalar_subquery()
    )


async def list_lead_emails(
    session: AsyncSession, edition_id: uuid.UUID, lead_id: uuid.UUID, params: PageParams
) -> tuple[Sequence[EmailJob], dict[str, int]]:
    """Exact lead identity and edition; counts cover all pages, not just the visible rows."""
    where = (EmailJob.edition_id == edition_id) & (EmailJob.visitor_lead_id == lead_id)
    counts = dict(
        (
            await session.execute(
                select(EmailJob.status, func.count()).where(where).group_by(EmailJob.status)
            )
        ).all()
    )
    rows = await session.scalars(
        select(EmailJob)
        .where(where)
        .order_by(EmailJob.queued_at.desc(), EmailJob.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    )
    return rows.all(), counts
