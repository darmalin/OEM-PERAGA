"""Transactional outbox (BACKEND_RULES/jobs-integrations.md).

Services insert an event in the same transaction as the business change. The dispatcher
(Celery Beat) picks undispatched rows with FOR UPDATE SKIP LOCKED and enqueues the real task.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.context import current_request_id
from app.core.db import Base, UUIDPk


class OutboxEvent(UUIDPk, Base):
    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Celery task that handles this event; receives the event id only.
    task_name: Mapped[str] = mapped_column(String(200), nullable=False)
    queue: Mapped[str] = mapped_column(String(50), nullable=False, default="default")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    dispatch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


async def enqueue(
    session: AsyncSession,
    event_type: str,
    task_name: str,
    payload: dict[str, Any],
    queue: str = "default",
) -> OutboxEvent:
    """Add an outbox event inside the caller's transaction."""
    event = OutboxEvent(
        event_type=event_type,
        task_name=task_name,
        queue=queue,
        payload=payload,
        request_id=current_request_id(),
    )
    session.add(event)
    await session.flush()
    return event


async def claim_pending(session: AsyncSession, limit: int = 100) -> list[OutboxEvent]:
    """Lock a batch of undispatched events; concurrent dispatchers skip locked rows."""
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.dispatched_at.is_(None))
        .order_by(OutboxEvent.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list((await session.scalars(stmt)).all())


async def get_event(session: AsyncSession, event_id: uuid.UUID) -> OutboxEvent | None:
    return await session.get(OutboxEvent, event_id)
