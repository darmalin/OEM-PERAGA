"""Visitor lead queries. Every function on lead data takes a Scope and applies it in SQL."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, Row, Select, case, false, func, or_, select, true, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Scope
from app.modules.identity.models import User, UserTeamMembership
from app.modules.visitors.models import (
    EditionFieldOption,
    VisitorCustomFieldDefinition,
    VisitorLead,
)
from app.modules.visitors.schemas import LeadFilters


def scope_clause(scope: Scope) -> ColumnElement[bool]:
    """Edition + ownership filter for a scope (BACKEND_RULES/database.md)."""
    clause: ColumnElement[bool] = VisitorLead.edition_id == scope.edition_id
    if scope.full_access:
        return clause
    visible: list[ColumnElement[bool]] = []
    if scope.owned:
        visible.append(VisitorLead.lead_owner_id == scope.user_id)
    if scope.team_ids:
        visible.append(
            VisitorLead.lead_owner_id.in_(
                select(UserTeamMembership.user_id).where(
                    UserTeamMembership.team_id.in_(scope.team_ids)
                )
            )
        )
    return clause & (or_(*visible) if visible else false())


def apply_scope[*Ts](stmt: Select[*Ts], scope: Scope) -> Select[*Ts]:
    return stmt.where(scope_clause(scope))


def filter_clause(f: LeadFilters) -> ColumnElement[bool]:
    conds: list[ColumnElement[bool]] = []
    if f.q:
        like = f"%{f.q.strip().lower()}%"
        digits = "".join(ch for ch in f.q if ch.isdigit())
        options = [
            func.lower(VisitorLead.first_name).like(like),
            VisitorLead.email_normalized.like(like),
            func.lower(VisitorLead.company_name).like(like),
            func.lower(VisitorLead.registration_code).like(like),
        ]
        if len(digits) >= 4:
            options.append(VisitorLead.phone_normalized.like(f"%{digits}%"))
        conds.append(or_(*options))
    if f.telemarketing_status:
        conds.append(
            VisitorLead.telemarketing_status.in_([s.value for s in f.telemarketing_status])
        )
    if f.registration_status:
        conds.append(VisitorLead.registration_status == f.registration_status)
    if f.qr_status:
        conds.append(VisitorLead.qr_status == f.qr_status)
    if f.lead_owner_id:
        conds.append(VisitorLead.lead_owner_id == f.lead_owner_id)
    if f.team_id:
        conds.append(
            VisitorLead.lead_owner_id.in_(
                select(UserTeamMembership.user_id).where(UserTeamMembership.team_id == f.team_id)
            )
        )
    if f.unassigned is True:
        conds.append(VisitorLead.lead_owner_id.is_(None))
    elif f.unassigned is False:
        conds.append(VisitorLead.lead_owner_id.is_not(None))
    if f.source:
        conds.append(VisitorLead.source == f.source)
    if f.country:
        conds.append(VisitorLead.country == f.country.upper())
    if f.is_valid_lead is not None:
        conds.append(VisitorLead.is_valid_lead.is_(f.is_valid_lead))
    if f.is_invalid is not None:
        conds.append(VisitorLead.is_invalid.is_(f.is_invalid))
    if f.attend:
        conds.append(VisitorLead.attend == f.attend)
    if f.buyer_type:
        conds.append(VisitorLead.buyer_type == f.buyer_type)
    if f.lead_date_from:
        conds.append(VisitorLead.lead_date >= f.lead_date_from)
    if f.lead_date_to:
        conds.append(VisitorLead.lead_date < f.lead_date_to)
    return _and(conds) if conds else true()


def _and(conds: list[ColumnElement[bool]]) -> ColumnElement[bool]:
    result = conds[0]
    for c in conds[1:]:
        result = result & c
    return result


async def list_leads(
    session: AsyncSession, scope: Scope, f: LeadFilters, sort: str, offset: int, limit: int
) -> tuple[Sequence[Row[VisitorLead, str | None]], int]:
    base = apply_scope(select(VisitorLead.id), scope).where(filter_clause(f))
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    column = getattr(VisitorLead, sort.lstrip("-"))
    order = column.desc().nulls_last() if sort.startswith("-") else column.asc().nulls_last()
    stmt = (
        apply_scope(select(VisitorLead, User.full_name), scope)
        .outerjoin(User, User.id == VisitorLead.lead_owner_id)
        .where(filter_clause(f))
        .order_by(order, VisitorLead.id)
        .offset(offset)
        .limit(limit)
    )
    return (await session.execute(stmt)).all(), total


async def scoped_lead_ids(
    session: AsyncSession,
    scope: Scope,
    lead_ids: list[uuid.UUID] | None,
    f: LeadFilters | None,
    limit: int,
) -> list[uuid.UUID]:
    """IDs inside the scope, in creation order (deterministic for round robin)."""
    stmt = apply_scope(select(VisitorLead.id), scope)
    if lead_ids is not None:
        stmt = stmt.where(VisitorLead.id.in_(lead_ids))
    if f is not None:
        stmt = stmt.where(filter_clause(f))
    stmt = stmt.order_by(VisitorLead.created_at, VisitorLead.id).limit(limit)
    return list((await session.scalars(stmt)).all())


async def lock_leads(
    session: AsyncSession, scope: Scope, lead_ids: list[uuid.UUID]
) -> list[VisitorLead]:
    """Row-lock leads in ID order (a fixed order avoids deadlocks between batches)."""
    stmt = (
        apply_scope(select(VisitorLead), scope)
        .where(VisitorLead.id.in_(lead_ids))
        .order_by(VisitorLead.id)
        .with_for_update()
    )
    return list((await session.scalars(stmt)).all())


def visible_ids(scope: Scope) -> Select[tuple[uuid.UUID]]:
    """Subquery of lead IDs in the scope, for other modules' filters."""
    return apply_scope(select(VisitorLead.id), scope)


async def labels(
    session: AsyncSession, scope: Scope, lead_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, str]]:
    rows = await session.execute(
        select(VisitorLead.id, VisitorLead.first_name, VisitorLead.registration_code).where(
            VisitorLead.edition_id == scope.edition_id, VisitorLead.id.in_(lead_ids)
        )
    )
    return {i: (name, code) for i, name, code in rows.all()}


async def owner_queue(
    session: AsyncSession, scope: Scope, owner_id: uuid.UUID, offset: int, limit: int
) -> tuple[Sequence[Row[VisitorLead, str | None]], int]:
    """Call queue: follow-ups due first (soonest first), then NEW leads, then the rest."""
    base = apply_scope(select(VisitorLead), scope).where(VisitorLead.lead_owner_id == owner_id)
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    is_new = case((VisitorLead.telemarketing_status == "NEW", 0), else_=1)
    stmt = (
        apply_scope(select(VisitorLead, User.full_name), scope)
        .outerjoin(User, User.id == VisitorLead.lead_owner_id)
        .where(VisitorLead.lead_owner_id == owner_id)
        .order_by(
            VisitorLead.next_followup_at.asc().nulls_last(),
            is_new,
            VisitorLead.last_call_at.asc().nulls_first(),
            VisitorLead.created_at,
        )
        .offset(offset)
        .limit(limit)
    )
    return (await session.execute(stmt)).all(), total


async def edition_of(session: AsyncSession, lead_id: uuid.UUID) -> uuid.UUID | None:
    """Edition of a lead, used only to resolve the caller's scope before the real query."""
    return await session.scalar(select(VisitorLead.edition_id).where(VisitorLead.id == lead_id))


async def get_lead(
    session: AsyncSession, scope: Scope, lead_id: uuid.UUID, *, for_update: bool = False
) -> VisitorLead | None:
    stmt = apply_scope(select(VisitorLead), scope).where(VisitorLead.id == lead_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def owner_name(session: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    if user_id is None:
        return None
    return await session.scalar(select(User.full_name).where(User.id == user_id))


async def find_conflicts(
    session: AsyncSession,
    edition_id: uuid.UUID,
    email_normalized: str | None,
    phone_normalized: str | None,
    exclude_id: uuid.UUID | None = None,
) -> Sequence[Row[str, str | None, str | None, uuid.UUID | None]]:
    """Duplicate check across the whole edition, independent of the caller's scope (spec 5.2)."""
    conds: list[ColumnElement[bool]] = []
    if email_normalized:
        conds.append(VisitorLead.email_normalized == email_normalized)
    if phone_normalized:
        conds.append(VisitorLead.phone_normalized == phone_normalized)
    if not conds:
        return []
    stmt = select(
        VisitorLead.registration_code,
        VisitorLead.email_normalized,
        VisitorLead.phone_normalized,
        VisitorLead.import_job_id,
    ).where(VisitorLead.edition_id == edition_id, or_(*conds))
    if exclude_id is not None:
        stmt = stmt.where(VisitorLead.id != exclude_id)
    return (await session.execute(stmt)).all()


async def active_custom_fields(
    session: AsyncSession, edition_id: uuid.UUID, include_inactive: bool = False
) -> Sequence[VisitorCustomFieldDefinition]:
    stmt = select(VisitorCustomFieldDefinition).where(
        VisitorCustomFieldDefinition.edition_id == edition_id
    )
    if not include_inactive:
        stmt = stmt.where(VisitorCustomFieldDefinition.is_active.is_(True))
    stmt = stmt.order_by(
        VisitorCustomFieldDefinition.sort_order, VisitorCustomFieldDefinition.label
    )
    return (await session.scalars(stmt)).all()


async def get_custom_field(
    session: AsyncSession, field_id: uuid.UUID
) -> VisitorCustomFieldDefinition | None:
    return await session.get(VisitorCustomFieldDefinition, field_id)


async def field_options(
    session: AsyncSession, edition_id: uuid.UUID, field: str | None, include_inactive: bool
) -> Sequence[EditionFieldOption]:
    stmt = select(EditionFieldOption).where(EditionFieldOption.edition_id == edition_id)
    if field:
        stmt = stmt.where(EditionFieldOption.field == field)
    if not include_inactive:
        stmt = stmt.where(EditionFieldOption.is_active.is_(True))
    stmt = stmt.order_by(
        EditionFieldOption.field, EditionFieldOption.sort_order, EditionFieldOption.label
    )
    return (await session.scalars(stmt)).all()


async def active_option_values(session: AsyncSession, edition_id: uuid.UUID) -> dict[str, set[str]]:
    rows = await session.execute(
        select(EditionFieldOption.field, EditionFieldOption.value).where(
            EditionFieldOption.edition_id == edition_id, EditionFieldOption.is_active.is_(True)
        )
    )
    values: dict[str, set[str]] = {}
    for field, value in rows.all():
        values.setdefault(field, set()).add(value)
    return values


async def get_field_option(
    session: AsyncSession, option_id: uuid.UUID
) -> EditionFieldOption | None:
    return await session.get(EditionFieldOption, option_id)


def filtered_ids(scope: Scope, f: LeadFilters) -> Select[uuid.UUID]:
    """Lead IDs in scope that match the filters (subquery for reports and exports)."""
    return apply_scope(select(VisitorLead.id), scope).where(filter_clause(f))


async def export_batch(
    session: AsyncSession,
    scope: Scope,
    f: LeadFilters,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> Sequence[Row[VisitorLead, str | None]]:
    """Keyset page in creation order, so a long export never skips or repeats a lead."""
    stmt = (
        apply_scope(select(VisitorLead, User.full_name), scope)
        .outerjoin(User, User.id == VisitorLead.lead_owner_id)
        .where(filter_clause(f))
    )
    if after is not None:
        stmt = stmt.where(tuple_(VisitorLead.created_at, VisitorLead.id) > tuple_(*after))
    stmt = stmt.order_by(VisitorLead.created_at, VisitorLead.id).limit(limit)
    return (await session.execute(stmt)).all()
