"""Exhibitor lead queries. Every function on lead data takes a Scope and applies it in SQL."""

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import ColumnElement, Row, and_, false, func, or_, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Scope
from app.modules.exhibitors.models import (
    Booth,
    ExhibitorAccount,
    ExhibitorContract,
    ExhibitorContractCounter,
    ExhibitorLead,
    ExhibitorPayment,
)
from app.modules.exhibitors.schemas import BoothListParams, ExhibitorLeadListParams
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
) -> tuple[Sequence[Row[ExhibitorLead, str | None, str | None]], int]:
    where = (scope_clause(scope), _filters(p))
    total = await session.scalar(select(func.count(ExhibitorLead.id)).where(*where)) or 0
    column = getattr(ExhibitorLead, p.sort.lstrip("-"))
    order = column.desc() if p.sort.startswith("-") else column.asc()
    stmt = (
        select(ExhibitorLead, User.full_name, Booth.code)
        .outerjoin(User, User.id == ExhibitorLead.lead_owner_id)
        .outerjoin(Booth, Booth.id == ExhibitorLead.booth_id)
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


async def booth_code(session: AsyncSession, booth_id: uuid.UUID | None) -> str | None:
    if booth_id is None:
        return None
    return await session.scalar(select(Booth.code).where(Booth.id == booth_id))


# --- booths ------------------------------------------------------------------------------
# Booths are edition master data: callers resolve the edition scope before these run.


async def list_booths(
    session: AsyncSession, edition_id: uuid.UUID, p: BoothListParams
) -> tuple[Sequence[Row[Booth, uuid.UUID | None, str | None]], int]:
    conds: list[ColumnElement[bool]] = [Booth.edition_id == edition_id]
    if not p.include_inactive:
        conds.append(Booth.is_active.is_(True))
    if p.q and p.q.strip():
        like = f"%{p.q.strip().lower()}%"
        conds.append(or_(func.lower(Booth.code).like(like), func.lower(Booth.hall).like(like)))
    if p.available is True:
        conds.append(ExhibitorLead.id.is_(None))
    elif p.available is False:
        conds.append(ExhibitorLead.id.is_not(None))
    joined = select(Booth.id).outerjoin(ExhibitorLead, ExhibitorLead.booth_id == Booth.id)
    total = (
        await session.scalar(select(func.count()).select_from(joined.where(*conds).subquery())) or 0
    )
    stmt = (
        select(Booth, ExhibitorLead.id, ExhibitorLead.company_name)
        .outerjoin(ExhibitorLead, ExhibitorLead.booth_id == Booth.id)
        .where(*conds)
        .order_by(Booth.code, Booth.id)
        .offset(p.offset)
        .limit(p.page_size)
    )
    return (await session.execute(stmt)).all(), total


async def get_booth(
    session: AsyncSession, booth_id: uuid.UUID, *, for_update: bool = False
) -> Booth | None:
    stmt = select(Booth).where(Booth.id == booth_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def booth_holder(session: AsyncSession, booth_id: uuid.UUID) -> tuple[uuid.UUID, str] | None:
    row = (
        await session.execute(
            select(ExhibitorLead.id, ExhibitorLead.company_name).where(
                ExhibitorLead.booth_id == booth_id
            )
        )
    ).first()
    return (row[0], row[1]) if row else None


# --- contracts ---------------------------------------------------------------------------


async def get_contract(
    session: AsyncSession, lead_id: uuid.UUID, *, for_update: bool = False
) -> ExhibitorContract | None:
    stmt = select(ExhibitorContract).where(ExhibitorContract.exhibitor_lead_id == lead_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def next_contract_number(session: AsyncSession, edition_id: uuid.UUID) -> int:
    """Next per-edition number; the row lock is held until the transaction ends."""
    stmt = (
        insert(ExhibitorContractCounter)
        .values(edition_id=edition_id, last_value=1)
        .on_conflict_do_update(
            index_elements=[ExhibitorContractCounter.edition_id],
            set_={"last_value": ExhibitorContractCounter.last_value + 1},
        )
        .returning(ExhibitorContractCounter.last_value)
    )
    return int((await session.execute(stmt)).scalar_one())


# --- portal accounts (not edition data: an account spans editions) ---------------------


async def account_by_email(
    session: AsyncSession, email_normalized: str, *, for_update: bool = False
) -> ExhibitorAccount | None:
    stmt = select(ExhibitorAccount).where(ExhibitorAccount.email_normalized == email_normalized)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def account_by_invite(
    session: AsyncSession, token_hash: str, *, for_update: bool = False
) -> ExhibitorAccount | None:
    stmt = select(ExhibitorAccount).where(ExhibitorAccount.invite_token_hash == token_hash)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def get_account(
    session: AsyncSession, account_id: uuid.UUID, *, for_update: bool = False
) -> ExhibitorAccount | None:
    stmt = select(ExhibitorAccount).where(ExhibitorAccount.id == account_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def account_exhibitors(
    session: AsyncSession, account_id: uuid.UUID
) -> Sequence[Row[ExhibitorLead, str | None, ExhibitorContract | None]]:
    """The account's own exhibitor records: the portal's only view of exhibitor data."""
    stmt = (
        select(ExhibitorLead, Booth.code, ExhibitorContract)
        .outerjoin(Booth, Booth.id == ExhibitorLead.booth_id)
        .outerjoin(ExhibitorContract, ExhibitorContract.exhibitor_lead_id == ExhibitorLead.id)
        .where(
            ExhibitorLead.exhibitor_account_id == account_id,
            ExhibitorLead.stage == "EXHIBITOR",
        )
        .order_by(ExhibitorLead.converted_at.desc())
    )
    return (await session.execute(stmt)).all()


async def portal_lead(
    session: AsyncSession, account_id: uuid.UUID, lead_id: uuid.UUID
) -> ExhibitorLead | None:
    """An exhibitor record of the account; any other lead is invisible to the portal."""
    return await session.scalar(
        select(ExhibitorLead).where(
            ExhibitorLead.id == lead_id,
            ExhibitorLead.exhibitor_account_id == account_id,
            ExhibitorLead.stage == "EXHIBITOR",
        )
    )


# --- payments ------------------------------------------------------------------------------


async def list_payments(
    session: AsyncSession, contract_id: uuid.UUID
) -> Sequence[ExhibitorPayment]:
    stmt = (
        select(ExhibitorPayment)
        .where(ExhibitorPayment.contract_id == contract_id)
        .order_by(ExhibitorPayment.paid_on, ExhibitorPayment.created_at)
    )
    return (await session.scalars(stmt)).all()


async def get_payment(
    session: AsyncSession,
    contract_id: uuid.UUID,
    payment_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> ExhibitorPayment | None:
    stmt = select(ExhibitorPayment).where(
        ExhibitorPayment.id == payment_id, ExhibitorPayment.contract_id == contract_id
    )
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def payment_sums(session: AsyncSession, contract_id: uuid.UUID) -> dict[str, Decimal]:
    """Sum of amounts per payment status of a contract."""
    stmt = (
        select(ExhibitorPayment.status, func.sum(ExhibitorPayment.amount))
        .where(ExhibitorPayment.contract_id == contract_id)
        .group_by(ExhibitorPayment.status)
    )
    return {status: total for status, total in (await session.execute(stmt)).all()}


# --- pipeline summary ----------------------------------------------------------------------


async def stage_counts(session: AsyncSession, scope: Scope) -> dict[str, int]:
    stmt = (
        select(ExhibitorLead.stage, func.count())
        .where(scope_clause(scope))
        .group_by(ExhibitorLead.stage)
    )
    return {stage: n for stage, n in (await session.execute(stmt)).all()}


async def booth_counts(session: AsyncSession, edition_id: uuid.UUID) -> tuple[int, int]:
    """(active booths, active booths held by a lead) of the edition."""
    held = func.count(ExhibitorLead.id)
    stmt = (
        select(func.count(Booth.id), held)
        .outerjoin(ExhibitorLead, ExhibitorLead.booth_id == Booth.id)
        .where(Booth.edition_id == edition_id, Booth.is_active.is_(True))
    )
    total, taken = (await session.execute(stmt)).one()
    return int(total), int(taken)


async def contract_rows(
    session: AsyncSession, scope: Scope
) -> Sequence[Row[ExhibitorContract, Decimal]]:
    """Contracts in scope with the verified sum of each."""
    verified = (
        select(func.coalesce(func.sum(ExhibitorPayment.amount), 0))
        .where(
            ExhibitorPayment.contract_id == ExhibitorContract.id,
            ExhibitorPayment.status == "VERIFIED",
        )
        .scalar_subquery()
    )
    stmt = (
        select(ExhibitorContract, verified)
        .join(ExhibitorLead, ExhibitorLead.id == ExhibitorContract.exhibitor_lead_id)
        .where(scope_clause(scope))
    )
    return (await session.execute(stmt)).all()


async def pending_by_contract(session: AsyncSession, scope: Scope) -> dict[uuid.UUID, Decimal]:
    stmt = (
        select(ExhibitorPayment.contract_id, func.sum(ExhibitorPayment.amount))
        .join(ExhibitorContract, ExhibitorContract.id == ExhibitorPayment.contract_id)
        .join(ExhibitorLead, ExhibitorLead.id == ExhibitorContract.exhibitor_lead_id)
        .where(scope_clause(scope), ExhibitorPayment.status == "PENDING")
        .group_by(ExhibitorPayment.contract_id)
    )
    # The join to contracts leaves out order payments (contract_id NULL, migration 0034).
    return {cid: total for cid, total in (await session.execute(stmt)).all() if cid is not None}
