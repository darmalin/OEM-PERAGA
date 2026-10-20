import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Scope
from app.modules.telemarketing.models import (
    AssignmentJob,
    LeadAssignmentHistory,
    RoundRobinCursor,
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
