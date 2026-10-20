import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Scope
from app.modules.telemarketing.models import (
    AssignmentJob,
    FollowupReminder,
    LeadAssignmentHistory,
    RoundRobinCursor,
    VisitorCallActivity,
    VisitorFollowup,
    VisitorFollowupChange,
    VisitorVerification,
)


async def lock_cursor(
    session: AsyncSession, edition_id: uuid.UUID, pool_key: str
) -> RoundRobinCursor:
    """Create-if-missing, then row-lock, so concurrent round robins run one after another."""
    await session.execute(
        insert(RoundRobinCursor)
        .values(id=uuid.uuid4(), edition_id=edition_id, pool_key=pool_key)
        .on_conflict_do_nothing(index_elements=["edition_id", "pool_key"])
    )
    cursor = await session.scalar(
        select(RoundRobinCursor)
        .where(RoundRobinCursor.edition_id == edition_id, RoundRobinCursor.pool_key == pool_key)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert cursor is not None  # noqa: S101 - inserted above
    return cursor


async def lead_history(
    session: AsyncSession, scope: Scope, lead_id: uuid.UUID
) -> Sequence[LeadAssignmentHistory]:
    stmt = (
        select(LeadAssignmentHistory)
        .where(
            LeadAssignmentHistory.edition_id == scope.edition_id,
            LeadAssignmentHistory.visitor_lead_id == lead_id,
        )
        .order_by(LeadAssignmentHistory.assigned_at.desc(), LeadAssignmentHistory.id.desc())
    )
    return (await session.scalars(stmt)).all()


async def get_job(
    session: AsyncSession, job_id: uuid.UUID, edition_id: uuid.UUID | None = None
) -> AssignmentJob | None:
    stmt = select(AssignmentJob).where(AssignmentJob.id == job_id)
    if edition_id is not None:
        stmt = stmt.where(AssignmentJob.edition_id == edition_id)
    return await session.scalar(stmt)


async def edition_of_job(session: AsyncSession, job_id: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(select(AssignmentJob.edition_id).where(AssignmentJob.id == job_id))


# --- calls, verification, follow-ups ------------------------------------------------------


async def calls_for_lead(
    session: AsyncSession, scope: Scope, lead_id: uuid.UUID
) -> Sequence[VisitorCallActivity]:
    stmt = (
        select(VisitorCallActivity)
        .where(
            VisitorCallActivity.edition_id == scope.edition_id,
            VisitorCallActivity.visitor_lead_id == lead_id,
        )
        .order_by(VisitorCallActivity.attempt_number)
    )
    return (await session.scalars(stmt)).all()


async def call_results(session: AsyncSession, lead_id: uuid.UUID) -> list[str]:
    rows = await session.scalars(
        select(VisitorCallActivity.call_result)
        .where(VisitorCallActivity.visitor_lead_id == lead_id)
        .order_by(VisitorCallActivity.attempt_number)
    )
    return list(rows.all())


async def verifications_for_lead(
    session: AsyncSession, scope: Scope, lead_id: uuid.UUID
) -> Sequence[VisitorVerification]:
    stmt = (
        select(VisitorVerification)
        .where(
            VisitorVerification.edition_id == scope.edition_id,
            VisitorVerification.visitor_lead_id == lead_id,
        )
        .order_by(VisitorVerification.created_at.desc(), VisitorVerification.id.desc())
    )
    return (await session.scalars(stmt)).all()


async def earliest_open_followup(session: AsyncSession, lead_id: uuid.UUID) -> datetime | None:
    return await session.scalar(
        select(func.min(VisitorFollowup.due_at)).where(
            VisitorFollowup.visitor_lead_id == lead_id, VisitorFollowup.status == "OPEN"
        )
    )


async def get_followup(session: AsyncSession, followup_id: uuid.UUID) -> VisitorFollowup | None:
    return await session.get(VisitorFollowup, followup_id)


async def followup_changes(
    session: AsyncSession, followup_id: uuid.UUID
) -> Sequence[VisitorFollowupChange]:
    stmt = (
        select(VisitorFollowupChange)
        .where(VisitorFollowupChange.followup_id == followup_id)
        .order_by(VisitorFollowupChange.created_at, VisitorFollowupChange.id)
    )
    return (await session.scalars(stmt)).all()


async def list_followups(
    session: AsyncSession,
    visible_leads: Select[tuple[uuid.UUID]],
    scope: Scope,
    status: str,
    due_from: datetime | None,
    due_to: datetime | None,
    assigned_to: uuid.UUID | None,
    offset: int,
    limit: int,
) -> tuple[Sequence[VisitorFollowup], int]:
    """Follow-ups whose lead is visible in the scope, or that are assigned to the caller."""
    stmt = select(VisitorFollowup).where(
        VisitorFollowup.edition_id == scope.edition_id,
        VisitorFollowup.status == status,
        or_(
            VisitorFollowup.visitor_lead_id.in_(visible_leads),
            VisitorFollowup.assigned_to == scope.user_id,
        ),
    )
    if due_from is not None:
        stmt = stmt.where(VisitorFollowup.due_at >= due_from)
    if due_to is not None:
        stmt = stmt.where(VisitorFollowup.due_at < due_to)
    if assigned_to is not None:
        stmt = stmt.where(VisitorFollowup.assigned_to == assigned_to)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(
        stmt.order_by(VisitorFollowup.due_at, VisitorFollowup.id).offset(offset).limit(limit)
    )
    return rows.all(), total


async def due_for_reminder(session: AsyncSession, until: datetime) -> Sequence[VisitorFollowup]:
    stmt = (
        select(VisitorFollowup)
        .where(VisitorFollowup.status == "OPEN", VisitorFollowup.due_at <= until)
        .order_by(VisitorFollowup.due_at)
        .limit(1000)
    )
    return (await session.scalars(stmt)).all()


async def claim_reminder(
    session: AsyncSession, key: str, followup_id: uuid.UUID
) -> uuid.UUID | None:
    """Insert the reminder key; None when it already exists (never send twice)."""
    return await session.scalar(
        insert(FollowupReminder)
        .values(id=uuid.uuid4(), dedup_key=key, followup_id=followup_id)
        .on_conflict_do_nothing(index_elements=["dedup_key"])
        .returning(FollowupReminder.id)
    )
