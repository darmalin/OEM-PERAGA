import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk


class LeadAssignmentHistory(UUIDPk, Base):
    """Every owner change. Append-only (spec 6.1)."""

    __tablename__ = "lead_assignment_history"
    __table_args__ = (
        Index("ix_lead_assignment_history_lead", "visitor_lead_id", "assigned_at"),
        Index("ix_lead_assignment_history_edition", "edition_id", "assigned_at"),
        CheckConstraint("method IN ('MANUAL', 'BULK', 'ROUND_ROBIN')", name="method_valid"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    visitor_lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitor_leads.id"), nullable=False
    )
    from_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    batch_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RoundRobinCursor(UUIDPk, Base):
    """Last agent used per edition and pool (team, or the whole edition)."""

    __tablename__ = "round_robin_cursors"
    __table_args__ = (UniqueConstraint("edition_id", "pool_key"),)

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    # team ID as text, or "edition" when no team is given.
    pool_key: Mapped[str] = mapped_column(String(64), nullable=False)
    last_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AssignmentJob(UUIDPk, Timestamps, Base):
    """Large assignment batches run in the worker."""

    __tablename__ = "assignment_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')", name="status_valid"
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    request: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_summary: Mapped[str | None] = mapped_column(Text)
    lead_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
