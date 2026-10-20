import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.identity.models import User


async def list_logs(
    session: AsyncSession,
    *,
    edition_ids: set[uuid.UUID] | None,
    edition_id: uuid.UUID | None,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    action: str | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    offset: int,
    limit: int,
) -> tuple[Sequence[Row[AuditLog, str | None]], int]:
    """edition_ids None = every row (global reader); otherwise only those editions."""
    stmt = select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.actor_user_id)
    if edition_ids is not None:
        stmt = stmt.where(AuditLog.edition_id.in_(edition_ids))
    if edition_id is not None:
        stmt = stmt.where(AuditLog.edition_id == edition_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if occurred_from:
        stmt = stmt.where(AuditLog.occurred_at >= occurred_from)
    if occurred_to:
        stmt = stmt.where(AuditLog.occurred_at < occurred_to)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.execute(
        stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)
    )
    return rows.all(), total


async def entity_timeline(
    session: AsyncSession,
    edition_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    limit: int = 200,
) -> Sequence[Row[AuditLog, str | None]]:
    stmt = (
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(
            AuditLog.edition_id == edition_id,
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        )
        .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    return (await session.execute(stmt)).all()
