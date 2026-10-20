import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Scope
from app.modules.registrations.models import (
    EmailJob,
    EmailLog,
    EmailTemplate,
    QrCredential,
    VisitorRegistration,
)
from app.modules.registrations.schemas import RegistrationListParams
from app.modules.visitors import service as visitors_service
from app.modules.visitors.models import VisitorLead


def _latest_email_status() -> Any:
    return (
        select(EmailJob.status)
        .where(EmailJob.registration_id == VisitorRegistration.id)
        .order_by(EmailJob.queued_at.desc(), EmailJob.id.desc())
        .limit(1)
        .correlate(VisitorRegistration)
        .scalar_subquery()
    )


def _base(scope: Scope) -> Select[Any]:
    """Registrations whose lead is visible in the scope, with the lead's label columns."""
    email_status = _latest_email_status()
    return (
        select(
            VisitorRegistration,
            VisitorLead.registration_code,
            VisitorLead.first_name,
            VisitorLead.qr_status,
            email_status.label("email_status"),
        )
        .join(VisitorLead, VisitorLead.id == VisitorRegistration.visitor_lead_id)
        .where(
            VisitorRegistration.edition_id == scope.edition_id,
            VisitorRegistration.visitor_lead_id.in_(visitors_service.visible_lead_ids(scope)),
        )
    )


async def list_registrations(
    session: AsyncSession, scope: Scope, params: RegistrationListParams
) -> tuple[Sequence[Any], int]:
    stmt = _base(scope)
    if params.visitor_lead_id:
        stmt = stmt.where(VisitorRegistration.visitor_lead_id == params.visitor_lead_id)
    if params.channel:
        stmt = stmt.where(VisitorRegistration.channel == params.channel)
    if params.qr_status:
        stmt = stmt.where(VisitorLead.qr_status == params.qr_status)
    if params.email_status:
        stmt = stmt.where(_latest_email_status() == params.email_status)
    if params.q and (q := params.q.strip()):
        like = f"%{q}%"
        stmt = stmt.where(
            or_(VisitorLead.registration_code.ilike(like), VisitorLead.first_name.ilike(like))
        )
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.execute(
        stmt.order_by(VisitorRegistration.registered_at.desc(), VisitorRegistration.id.desc())
        .offset(params.offset)
        .limit(params.page_size)
    )
    return rows.all(), int(total or 0)


async def get_row(session: AsyncSession, scope: Scope, registration_id: uuid.UUID) -> Any | None:
    row = await session.execute(_base(scope).where(VisitorRegistration.id == registration_id))
    return row.first()


async def edition_of(session: AsyncSession, registration_id: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(
        select(VisitorRegistration.edition_id).where(VisitorRegistration.id == registration_id)
    )


async def active_registration(
    session: AsyncSession, lead_id: uuid.UUID, *, for_update: bool = False
) -> VisitorRegistration | None:
    stmt = select(VisitorRegistration).where(
        VisitorRegistration.visitor_lead_id == lead_id,
        VisitorRegistration.status == "REGISTERED",
    )
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def active_credential(
    session: AsyncSession, registration_id: uuid.UUID, *, for_update: bool = False
) -> QrCredential | None:
    stmt = select(QrCredential).where(
        QrCredential.registration_id == registration_id, QrCredential.status == "ACTIVE"
    )
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def credentials(session: AsyncSession, registration_id: uuid.UUID) -> list[QrCredential]:
    rows = await session.scalars(
        select(QrCredential)
        .where(QrCredential.registration_id == registration_id)
        .order_by(QrCredential.issued_at.desc())
    )
    return list(rows)


async def email_jobs(
    session: AsyncSession, registration_id: uuid.UUID
) -> list[tuple[EmailJob, list[EmailLog]]]:
    jobs = list(
        await session.scalars(
            select(EmailJob)
            .where(EmailJob.registration_id == registration_id)
            .order_by(EmailJob.queued_at.desc(), EmailJob.id.desc())
        )
    )
    if not jobs:
        return []
    logs = await session.scalars(
        select(EmailLog)
        .where(EmailLog.email_job_id.in_([j.id for j in jobs]))
        .order_by(EmailLog.occurred_at, EmailLog.id)
    )
    by_job: dict[uuid.UUID, list[EmailLog]] = {j.id: [] for j in jobs}
    for log in logs:
        by_job[log.email_job_id].append(log)
    return [(j, by_job[j.id]) for j in jobs]


async def latest_template(
    session: AsyncSession, edition_id: uuid.UUID | None, template_key: str
) -> EmailTemplate | None:
    return await session.scalar(
        select(EmailTemplate)
        .where(
            EmailTemplate.template_key == template_key,
            EmailTemplate.edition_id.is_(None)
            if edition_id is None
            else EmailTemplate.edition_id == edition_id,
        )
        .order_by(EmailTemplate.version.desc())
        .limit(1)
    )


async def template_versions(
    session: AsyncSession, edition_id: uuid.UUID | None, template_key: str
) -> list[EmailTemplate]:
    rows = await session.scalars(
        select(EmailTemplate)
        .where(
            EmailTemplate.template_key == template_key,
            EmailTemplate.edition_id.is_(None)
            if edition_id is None
            else EmailTemplate.edition_id == edition_id,
        )
        .order_by(EmailTemplate.version.desc())
    )
    return list(rows)


# --- lookups for the gate module -------------------------------------------------------------


async def match_credential(session: AsyncSession, token_hash: str) -> Any | None:
    """(credential, registration, Registration ID, first name) for a scanned token hash."""
    row = await session.execute(
        select(
            QrCredential, VisitorRegistration, VisitorLead.registration_code, VisitorLead.first_name
        )
        .join(VisitorRegistration, VisitorRegistration.id == QrCredential.registration_id)
        .join(VisitorLead, VisitorLead.id == VisitorRegistration.visitor_lead_id)
        .where(QrCredential.token_hash == token_hash)
    )
    return row.first()


async def cache_rows(session: AsyncSession, edition_id: uuid.UUID) -> Sequence[Any]:
    """Every credential of the edition with what the gate screen shows."""
    rows = await session.execute(
        select(
            QrCredential.token_hash,
            QrCredential.status,
            VisitorRegistration.status,
            VisitorLead.registration_code,
            VisitorLead.first_name,
        )
        .join(VisitorRegistration, VisitorRegistration.id == QrCredential.registration_id)
        .join(VisitorLead, VisitorLead.id == VisitorRegistration.visitor_lead_id)
        .where(QrCredential.edition_id == edition_id)
        .order_by(QrCredential.issued_at)
    )
    return rows.all()


async def labels(
    session: AsyncSession, registration_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, str]]:
    rows = await session.execute(
        select(VisitorRegistration.id, VisitorLead.registration_code, VisitorLead.first_name)
        .join(VisitorLead, VisitorLead.id == VisitorRegistration.visitor_lead_id)
        .where(VisitorRegistration.id.in_(registration_ids))
    )
    return {r[0]: (r[1], r[2]) for r in rows}


async def token_hashes(session: AsyncSession, registration_ids: list[uuid.UUID]) -> list[str]:
    rows = await session.scalars(
        select(QrCredential.token_hash).where(
            QrCredential.registration_id.in_(registration_ids), QrCredential.status == "ACTIVE"
        )
    )
    return list(rows)
