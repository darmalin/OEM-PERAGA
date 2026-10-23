"""Read-only report queries.

Reporting is the one module that reads other modules' tables directly
(BACKEND_RULES/architecture.md). It never writes. Lead data always goes through
visitors.filtered_lead_ids(scope, filters) and gate data through the gate scope.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    case,
    distinct,
    extract,
    func,
    or_,
    select,
    true,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Scope
from app.modules.checkin.models import Gate, ScanAttempt, VisitorCheckin
from app.modules.checkin.repository import gate_scope_clause
from app.modules.exhibitions.models import Edition
from app.modules.identity.models import (
    Permission,
    RolePermission,
    Team,
    User,
    UserRoleAssignment,
    UserTeamMembership,
)
from app.modules.importexport.models import ImportJob
from app.modules.mail.models import EmailJob
from app.modules.registrations.models import VisitorRegistration
from app.modules.telemarketing.models import (
    VisitorCallActivity,
    VisitorFollowup,
    VisitorVerification,
)
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


# --- dashboard -------------------------------------------------------------------------------
# Per call, like the old system: a call and the verification sent with it (call_id link).


@dataclass(frozen=True)
class DashFilters:
    """Already-validated dashboard filters, split by what they narrow."""

    edition_id: uuid.UUID | None = None
    country: str | None = None
    user_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    lead_source_id: uuid.UUID | None = None
    telemarketing_status: str | None = None
    lead_quality: str | None = None
    buyer_type: str | None = None
    attend: str | None = None
    b2b_matching: bool | None = None


def local_day(column: Any, timezone: str) -> Any:
    """Event-local calendar date of a timestamptz column."""
    return func.date(func.timezone(timezone, column))


def _lead_conds(f: DashFilters) -> list[ColumnElement[bool]]:
    lead = VisitorLead
    conds: list[ColumnElement[bool]] = []
    if f.edition_id:
        conds.append(lead.edition_id == f.edition_id)
    if f.country:
        conds.append(lead.country == f.country)
    if f.lead_source_id:
        conds.append(lead.lead_source_id == f.lead_source_id)
    if f.telemarketing_status:
        conds.append(lead.telemarketing_status == f.telemarketing_status)
    return conds


def _people(column: Any, f: DashFilters) -> list[ColumnElement[bool]]:
    """User and team filters on the agent of a call or the owner of a lead."""
    conds: list[ColumnElement[bool]] = []
    if f.user_id:
        conds.append(column == f.user_id)
    if f.team_id:
        conds.append(
            column.in_(
                select(UserTeamMembership.user_id).where(UserTeamMembership.team_id == f.team_id)
            )
        )
    return conds


def _verification(
    valid: Any, invalid: Any, attend: Any, b2b: Any, buyer: Any, f: DashFilters
) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = []
    if f.lead_quality == "VALID":
        conds.append(valid.is_(True))
    elif f.lead_quality == "INVALID":
        conds.append(invalid.is_(True))
    elif f.lead_quality == "UNDECIDED":
        conds.append(
            and_(func.coalesce(valid, False).is_(False), func.coalesce(invalid, False).is_(False))
        )
    if f.attend:
        conds.append(attend == f.attend)
    if f.b2b_matching is not None:
        conds.append(func.coalesce(b2b, False).is_(f.b2b_matching))
    if f.buyer_type:
        conds.append(buyer == f.buyer_type)
    return conds


_CALL_KEYS = {
    "edition": VisitorCallActivity.edition_id,
    "source": VisitorLead.lead_source_id,
    "user": VisitorCallActivity.agent_id,
}
_LEAD_KEYS = {
    "edition": VisitorLead.edition_id,
    "source": VisitorLead.lead_source_id,
    "user": VisitorLead.lead_owner_id,
}


def _group(day: Any | None, key: Any | None) -> list[Any]:
    return [c for c in (day, key) if c is not None]


async def dashboard_calls(
    session: AsyncSession,
    visible: ColumnElement[bool],
    f: DashFilters,
    window: Window,
    timezone: str,
    by_day: bool,
    key: str | None,
) -> list[dict[str, Any]]:
    call, v = VisitorCallActivity, VisitorVerification
    answered = call.call_result == "ANSWER"
    first = call.attempt_number == 1
    day = local_day(call.called_at, timezone).label("day") if by_day else None
    key_col = _CALL_KEYS[key].label("key") if key else None
    metrics = [
        func.count().label("total"),
        _count_if(first & answered).label("answer"),
        _count_if(first & ~answered).label("non_answer"),
        _count_if(~first & answered).label("recontacted"),
        _count_if(~first & ~answered).label("retry_no_answer"),
        _count_if(v.is_valid_lead.is_(True)).label("valid"),
        _count_if(v.is_invalid.is_(True)).label("no_valid"),
        _count_if(v.attend == "ATTEND").label("attend"),
        _count_if(v.attend == "ATTEND_SOURCING").label("attend_sourcing"),
        _count_if(v.attend == "UNDER_CONSIDERATION").label("under_consideration"),
        _count_if(v.attend == "NOT_ATTEND").label("not_attend"),
        _count_if(v.attend == "HANG_UP_IMMEDIATELY").label("hang_up_immediately"),
        _count_if(v.b2b_matching.is_(True)).label("b2b_matching"),
        _count_if(v.buyer_type == "B_SIDE").label("b_side"),
        _count_if(v.buyer_type == "C_SIDE").label("c_side"),
    ]
    groups = _group(day, key_col)
    stmt = (
        select(*groups, *metrics)
        .select_from(call)
        .join(VisitorLead, VisitorLead.id == call.visitor_lead_id)
        .outerjoin(v, v.call_id == call.id)
        .where(
            visible,
            _in_window(call.called_at, window),
            *_lead_conds(f),
            *_people(call.agent_id, f),
            *_verification(
                v.is_valid_lead, v.is_invalid, v.attend, v.b2b_matching, v.buyer_type, f
            ),
        )
    )
    if groups:
        stmt = stmt.group_by(*groups)
    return [dict(r._mapping) for r in await session.execute(stmt)]


def _lead_where(visible: ColumnElement[bool], f: DashFilters) -> list[ColumnElement[bool]]:
    lead = VisitorLead
    return [
        visible,
        *_lead_conds(f),
        *_people(lead.lead_owner_id, f),
        *_verification(
            lead.is_valid_lead, lead.is_invalid, lead.attend, lead.b2b_matching, lead.buyer_type, f
        ),
    ]


async def dashboard_leads(
    session: AsyncSession,
    visible: ColumnElement[bool],
    f: DashFilters,
    window: Window,
    timezone: str,
    by_day: bool,
    key: str | None,
) -> dict[str, list[dict[str, Any]]]:
    """Leads added, and the parts of Pending: created and first called, before and in range.

    Pending at the end of a day = created by then - first called by then.
    """
    start, _ = window
    lead = VisitorLead
    key_col = _LEAD_KEYS[key].label("key") if key else None
    where = _lead_where(visible, f)
    first_call = (
        select(
            VisitorCallActivity.visitor_lead_id.label("lead_id"),
            func.min(VisitorCallActivity.called_at).label("first_at"),
        )
        .group_by(VisitorCallActivity.visitor_lead_id)
        .subquery()
    )

    async def counts(
        time_col: Any, cond: ColumnElement[bool], with_day: bool, join_first: bool
    ) -> list[dict[str, Any]]:
        day = local_day(time_col, timezone).label("day") if with_day else None
        groups = _group(day, key_col)
        stmt = select(*groups, func.count().label("n")).select_from(lead)
        if join_first:
            stmt = stmt.join(first_call, first_call.c.lead_id == lead.id)
        stmt = stmt.where(*where, cond)
        if groups:
            stmt = stmt.group_by(*groups)
        return [dict(r._mapping) for r in await session.execute(stmt)]

    in_range_created = _in_window(lead.created_at, window)
    in_range_first = _in_window(first_call.c.first_at, window)
    return {
        "added": await counts(lead.created_at, in_range_created, by_day, False),
        "created_before": await counts(lead.created_at, lead.created_at < start, False, False)
        if start
        else [],
        "called_before": await counts(
            first_call.c.first_at, first_call.c.first_at < start, False, True
        )
        if start
        else [],
        "called": await counts(first_call.c.first_at, in_range_first, by_day, True),
    }


async def dashboard_countries(session: AsyncSession, visible: ColumnElement[bool]) -> list[str]:
    rows = await session.scalars(
        select(VisitorLead.country)
        .distinct()
        .where(visible, VisitorLead.country.is_not(None))
        .order_by(VisitorLead.country)
    )
    return [r for r in rows if r]


async def dashboard_agents(
    session: AsyncSession, edition_ids: set[uuid.UUID] | None, extra_ids: set[uuid.UUID]
) -> list[tuple[uuid.UUID, str, str | None, str | None]]:
    """(user id, name, team names, edition codes) for users who log calls in these editions,
    plus `extra_ids` (users found in the data). Editions "All" for a global grant."""
    grants = (
        select(UserRoleAssignment.user_id, UserRoleAssignment.edition_id)
        .join(RolePermission, RolePermission.role_id == UserRoleAssignment.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(Permission.code == "telemarketing.call")
    )
    if edition_ids is not None:
        grants = grants.where(
            or_(
                UserRoleAssignment.edition_id.in_(edition_ids),
                UserRoleAssignment.edition_id.is_(None),
            )
        )
    grant_rows = (await session.execute(grants)).all()
    editions_of: dict[uuid.UUID, set[uuid.UUID | None]] = {}
    for user_id, edition_id in grant_rows:
        editions_of.setdefault(user_id, set()).add(edition_id)
    ids = set(editions_of) | extra_ids
    if not ids:
        return []
    users = (
        await session.execute(
            select(User.id, User.full_name).where(User.id.in_(ids)).order_by(User.full_name)
        )
    ).all()
    teams: dict[uuid.UUID, list[str]] = {}
    for user_id, name in await session.execute(
        select(UserTeamMembership.user_id, Team.name)
        .join(Team, Team.id == UserTeamMembership.team_id)
        .where(UserTeamMembership.user_id.in_(ids))
        .order_by(Team.name)
    ):
        teams.setdefault(user_id, []).append(name)
    codes = dict((await session.execute(select(Edition.id, Edition.code))).all())
    out = []
    for user_id, name in users:
        eds = editions_of.get(user_id, set())
        label = "All" if None in eds else ", ".join(sorted(codes.get(e, "") for e in eds if e))
        out.append((user_id, name, ", ".join(teams.get(user_id, [])) or None, label or None))
    return out


async def dashboard_teams(session: AsyncSession) -> list[tuple[uuid.UUID, str]]:
    return [
        (i, n) for i, n in await session.execute(select(Team.id, Team.name).order_by(Team.name))
    ]
