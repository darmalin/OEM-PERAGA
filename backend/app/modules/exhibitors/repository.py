"""Exhibitor lead queries. Every function on lead data takes a Scope and applies it in SQL."""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Row, and_, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Scope
from app.modules.exhibitors.models import ExhibitorLead
from app.modules.exhibitors.schemas import ExhibitorLeadListParams
from app.modules.identity.models import User, UserTeamMembership


def scope_clause(scope: Scope) -> ColumnElement[bool]:
    clause: ColumnElement[bool] = ExhibitorLead.edition_id == scope.edition_id
    if scope.full_access:
        return clause
    visible: list[ColumnElement[bool]] = []
    if scope.owned:
        visible.append(ExhibitorLead.lead_owner_id == scope.user_id)
    if scope.team_ids:
        visible.append(
            ExhibitorLead.lead_owner_id.in_(
                select(UserTeamMembership.user_id).where(
                    UserTeamMembership.team_id.in_(scope.team_ids)
                )
            )
        )
    return clause & (or_(*visible) if visible else false())


def _filters(p: ExhibitorLeadListParams) -> ColumnElement[bool]:
    conds: list[ColumnElement[bool]] = []
    if p.q and p.q.strip():
        like = f"%{p.q.strip().lower()}%"
        conds.append(
            or_(
                func.lower(ExhibitorLead.company_name).like(like),
                func.lower(ExhibitorLead.contact_name).like(like),
                ExhibitorLead.email_normalized.like(like),
            )
        )
    if p.stage:
        conds.append(ExhibitorLead.stage.in_([s.value for s in p.stage]))
    if p.lead_owner_id:
        conds.append(ExhibitorLead.lead_owner_id == p.lead_owner_id)
    return and_(*conds) if conds else true()


async def list_leads(
    session: AsyncSession, scope: Scope, p: ExhibitorLeadListParams
) -> tuple[Sequence[Row[ExhibitorLead, str | None]], int]:
    where = (scope_clause(scope), _filters(p))
    total = await session.scalar(select(func.count(ExhibitorLead.id)).where(*where)) or 0
    column = getattr(ExhibitorLead, p.sort.lstrip("-"))
    order = column.desc() if p.sort.startswith("-") else column.asc()
    stmt = (
        select(ExhibitorLead, User.full_name)
        .outerjoin(User, User.id == ExhibitorLead.lead_owner_id)
        .where(*where)
        .order_by(order, ExhibitorLead.id)
        .offset(p.offset)
        .limit(p.page_size)
    )
    return (await session.execute(stmt)).all(), total


async def edition_of(session: AsyncSession, lead_id: uuid.UUID) -> uuid.UUID | None:
    """Edition of a lead, used only to resolve the caller's scope before the real query."""
    return await session.scalar(select(ExhibitorLead.edition_id).where(ExhibitorLead.id == lead_id))


async def get_lead(
    session: AsyncSession, scope: Scope, lead_id: uuid.UUID, *, for_update: bool = False
) -> ExhibitorLead | None:
    stmt = select(ExhibitorLead).where(scope_clause(scope), ExhibitorLead.id == lead_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def email_taken(
    session: AsyncSession,
    edition_id: uuid.UUID,
    email_normalized: str,
    exclude_id: uuid.UUID | None,
) -> bool:
    # Duplicate check across the whole edition, not the caller's scope: the rule is per edition.
    stmt = select(ExhibitorLead.id).where(
        ExhibitorLead.edition_id == edition_id,
        ExhibitorLead.email_normalized == email_normalized,
    )
    if exclude_id is not None:
        stmt = stmt.where(ExhibitorLead.id != exclude_id)
    return await session.scalar(stmt.limit(1)) is not None


async def owner_name(session: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    if user_id is None:
        return None
    return await session.scalar(select(User.full_name).where(User.id == user_id))
