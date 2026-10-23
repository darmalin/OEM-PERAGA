"""Read-only report queries.

Reporting is the one module that reads other modules' tables directly
(BACKEND_RULES/architecture.md). It never writes. Lead data always goes through
visitors.filtered_lead_ids(scope, filters) and gate data through the gate scope.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, case, distinct, extract, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Scope
from app.modules.checkin.models import Gate, ScanAttempt, VisitorCheckin
from app.modules.checkin.repository import gate_scope_clause
from app.modules.identity.models import User
from app.modules.importexport.models import ImportJob
from app.modules.mail.models import EmailJob
from app.modules.registrations.models import VisitorRegistration
from app.modules.telemarketing.models import VisitorCallActivity, VisitorFollowup
from app.modules.visitors.models import VisitorLead

Window = tuple[datetime | None, datetime | None]


def _in_window(column: Any, window: Window) -> ColumnElement[bool]:
    start, end = window
    conds: list[ColumnElement[bool]] = []
    if start is not None:
        conds.append(column >= start)
    if end is not None:
        conds.append(column < end)
    return and_(*conds) if conds else true()


def _count_if(cond: ColumnElement[bool]) -> Any:
    return func.count().filter(cond)


async def _breakdown(session: AsyncSession, stmt: Select[Any, int]) -> list[tuple[Any, int]]:
    return [(r[0], int(r[1])) for r in await session.execute(stmt)]


# --- lead based ------------------------------------------------------------------------------


async def lead_overview(session: AsyncSession, lead_ids: Any) -> Sequence[Any]:
    row = await session.execute(
        select(
            func.count(),
            _count_if(VisitorLead.telemarketing_status == "NEW"),
            _count_if(VisitorLead.lead_owner_id.is_not(None)),
        ).where(VisitorLead.id.in_(lead_ids))
    )
    return row.one()


_BREAKDOWN_COLUMNS = {
    "source": VisitorLead.source,
    "country": VisitorLead.country,
    "telemarketing_status": VisitorLead.telemarketing_status,
    "attend": VisitorLead.attend,
    "buyer_type": VisitorLead.buyer_type,
}


async def leads_by(
    session: AsyncSession, lead_ids: Any, field: str, limit: int = 50
) -> list[tuple[Any, int]]:
    column = _BREAKDOWN_COLUMNS[field]
    return await _breakdown(
        session,
        select(column, func.count())
        .where(VisitorLead.id.in_(lead_ids))
        .group_by(column)
        .order_by(func.count().desc(), column)
        .limit(limit),
    )


async def call_totals(session: AsyncSession, lead_ids: Any, window: Window) -> Sequence[Any]:
    row = await session.execute(
        select(func.count(), _count_if(VisitorCallActivity.call_result == "ANSWER")).where(
            VisitorCallActivity.visitor_lead_id.in_(lead_ids),
            _in_window(VisitorCallActivity.called_at, window),
        )
    )
    return row.one()


async def followup_totals(
    session: AsyncSession, lead_ids: Any, today: Window, now: datetime
) -> Sequence[Any]:
    open_ = VisitorFollowup.status == "OPEN"
    row = await session.execute(
        select(
            _count_if(open_),
            _count_if(open_ & _in_window(VisitorFollowup.due_at, today)),
            _count_if(open_ & (VisitorFollowup.due_at < now)),
        ).where(VisitorFollowup.visitor_lead_id.in_(lead_ids))
    )
    return row.one()


async def verification_totals(session: AsyncSession, lead_ids: Any) -> Sequence[Any]:
    row = await session.execute(
        select(
            _count_if(VisitorLead.is_valid_lead.is_(True)),
            _count_if(VisitorLead.is_invalid.is_(True)),
            _count_if(VisitorLead.is_valid_lead.is_(False) & VisitorLead.is_invalid.is_(False)),
            _count_if(VisitorLead.b2b_matching.is_(True)),
        ).where(VisitorLead.id.in_(lead_ids))
    )
    return row.one()


async def registration_totals(session: AsyncSession, lead_ids: Any) -> Sequence[Any]:
    row = await session.execute(
        select(
            _count_if(VisitorLead.registration_status == "REGISTERED"),
            _count_if(VisitorLead.registration_status != "REGISTERED"),
            _count_if(VisitorLead.qr_status == "ACTIVE"),
            _count_if(VisitorLead.qr_status == "REVOKED"),
        ).where(VisitorLead.id.in_(lead_ids))
    )
    return row.one()


async def registrations_by_channel(session: AsyncSession, lead_ids: Any) -> list[tuple[Any, int]]:
    return await _breakdown(
        session,
        select(VisitorRegistration.channel, func.count())
        .where(
            VisitorRegistration.visitor_lead_id.in_(lead_ids),
            VisitorRegistration.status == "REGISTERED",
        )
        .group_by(VisitorRegistration.channel)
        .order_by(VisitorRegistration.channel),
    )


async def emails_by_status_for_leads(
    session: AsyncSession, lead_ids: Any, window: Window
) -> list[tuple[Any, int]]:
    return await _breakdown(
        session,
        select(EmailJob.status, func.count())
        .join(VisitorRegistration, VisitorRegistration.id == EmailJob.registration_id)
        .where(
            VisitorRegistration.visitor_lead_id.in_(lead_ids),
            _in_window(EmailJob.queued_at, window),
        )
        .group_by(EmailJob.status)
        .order_by(EmailJob.status),
    )


async def agent_rows(
    session: AsyncSession, edition_id: uuid.UUID, lead_ids: Any, window: Window
) -> Sequence[Any]:
    """Per agent: leads owned, call attempts, answered, follow-ups total/done."""
    owned = (
        select(VisitorLead.lead_owner_id.label("agent_id"), func.count().label("leads_owned"))
        .where(VisitorLead.id.in_(lead_ids), VisitorLead.lead_owner_id.is_not(None))
        .group_by(VisitorLead.lead_owner_id)
        .subquery()
    )
    calls = (
        select(
            VisitorCallActivity.agent_id.label("agent_id"),
            func.count().label("attempts"),
            _count_if(VisitorCallActivity.call_result == "ANSWER").label("answered"),
        )
        .where(
            VisitorCallActivity.visitor_lead_id.in_(lead_ids),
            _in_window(VisitorCallActivity.called_at, window),
        )
        .group_by(VisitorCallActivity.agent_id)
        .subquery()
    )
    followups = (
        select(
            VisitorFollowup.assigned_to.label("agent_id"),
            func.count().label("total"),
            _count_if(VisitorFollowup.status == "DONE").label("done"),
        )
        .where(VisitorFollowup.visitor_lead_id.in_(lead_ids))
        .group_by(VisitorFollowup.assigned_to)
        .subquery()
    )
    agents = (
        select(owned.c.agent_id)
        .union(select(calls.c.agent_id), select(followups.c.agent_id))
        .subquery()
    )
    rows = await session.execute(
        select(
            User.id,
            User.full_name,
            func.coalesce(owned.c.leads_owned, 0),
            func.coalesce(calls.c.attempts, 0),
            func.coalesce(calls.c.answered, 0),
            func.coalesce(followups.c.total, 0),
            func.coalesce(followups.c.done, 0),
        )
        .join(agents, agents.c.agent_id == User.id)
        .outerjoin(owned, owned.c.agent_id == User.id)
        .outerjoin(calls, calls.c.agent_id == User.id)
        .outerjoin(followups, followups.c.agent_id == User.id)
        .order_by(User.full_name, User.id)
    )
    result: Sequence[Any] = rows.all()
    return result


# --- gates -----------------------------------------------------------------------------------


def _scans(scope: Scope, gate_id: uuid.UUID | None, window: Window) -> list[ColumnElement[bool]]:
    conds = [
        ScanAttempt.edition_id == scope.edition_id,
        gate_scope_clause(ScanAttempt.gate_id, scope),
        _in_window(ScanAttempt.scanned_at, window),
    ]
    if gate_id is not None:
        conds.append(ScanAttempt.gate_id == gate_id)
    return conds


_ACCEPTED = ScanAttempt.outcome == "ACCEPTED"
_FIRST = VisitorCheckin.id.is_not(None)


def _attempts_with_first() -> Any:
    return (
        select()
        .select_from(ScanAttempt)
        .outerjoin(VisitorCheckin, VisitorCheckin.first_scan_attempt_id == ScanAttempt.id)
    )


async def attendance_totals(
    session: AsyncSession, scope: Scope, gate_id: uuid.UUID | None, window: Window
) -> Sequence[Any]:
    row = await session.execute(
        _attempts_with_first()
        .add_columns(
            func.count(),
            _count_if(_ACCEPTED),
            _count_if(_FIRST),
            _count_if(~_ACCEPTED),
            func.count(distinct(case((_ACCEPTED, ScanAttempt.registration_id)))),
        )
        .where(*_scans(scope, gate_id, window))
    )
    return row.one()


async def attendance_by_day(
    session: AsyncSession, scope: Scope, gate_id: uuid.UUID | None, window: Window
) -> Sequence[Any]:
    rows = await session.execute(
        _attempts_with_first()
        .add_columns(
            ScanAttempt.local_date,
            func.count(distinct(case((_ACCEPTED, ScanAttempt.registration_id)))),
            _count_if(_FIRST),
            _count_if(_ACCEPTED),
            func.count(),
            _count_if(~_ACCEPTED),
        )
        .where(*_scans(scope, gate_id, window))
        .group_by(ScanAttempt.local_date)
        .order_by(ScanAttempt.local_date)
    )
    return rows.all()


async def by_gate(
    session: AsyncSession, scope: Scope, gate_id: uuid.UUID | None, window: Window
) -> Sequence[Any]:
    rows = await session.execute(
        select(
            Gate.id,
            Gate.code,
            Gate.name,
            func.count(ScanAttempt.id),
            func.count(ScanAttempt.id).filter(_ACCEPTED),
            func.count(ScanAttempt.id).filter(~_ACCEPTED),
        )
        .outerjoin(
            ScanAttempt,
            and_(ScanAttempt.gate_id == Gate.id, *_scans(scope, gate_id, window)),
        )
        .where(Gate.edition_id == scope.edition_id, gate_scope_clause(Gate.id, scope))
        .where(Gate.id == gate_id if gate_id is not None else true())
        .group_by(Gate.id, Gate.code, Gate.name)
        .order_by(Gate.code)
    )
    return rows.all()


async def by_hour(
    session: AsyncSession,
    scope: Scope,
    gate_id: uuid.UUID | None,
    window: Window,
    timezone: str,
) -> Sequence[Any]:
    local = func.timezone(timezone, ScanAttempt.scanned_at)
    hour = extract("hour", local)
    rows = await session.execute(
        select(ScanAttempt.local_date, hour, func.count(), _count_if(_ACCEPTED))
        .where(*_scans(scope, gate_id, window))
        .group_by(ScanAttempt.local_date, hour)
        .order_by(ScanAttempt.local_date, hour)
    )
    return rows.all()


# --- edition operations ----------------------------------------------------------------------


async def import_totals(
    session: AsyncSession, edition_id: uuid.UUID, window: Window
) -> tuple[Sequence[Any], list[tuple[Any, int]]]:
    where = [ImportJob.edition_id == edition_id, _in_window(ImportJob.created_at, window)]
    totals = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(ImportJob.processed_count), 0),
                func.coalesce(func.sum(ImportJob.created_count), 0),
                func.coalesce(func.sum(ImportJob.duplicate_count), 0),
                func.coalesce(func.sum(ImportJob.invalid_count), 0),
            ).where(*where)
        )
    ).one()
    statuses = await _breakdown(
        session,
        select(ImportJob.status, func.count())
        .where(*where)
        .group_by(ImportJob.status)
        .order_by(ImportJob.status),
    )
    return totals, statuses


async def email_status_totals(
    session: AsyncSession, edition_id: uuid.UUID, window: Window
) -> list[tuple[Any, int]]:
    return await _breakdown(
        session,
        select(EmailJob.status, func.count())
        .where(EmailJob.edition_id == edition_id, _in_window(EmailJob.queued_at, window))
        .group_by(EmailJob.status)
        .order_by(EmailJob.status),
    )
