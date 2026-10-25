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

from app.core.db import Base, Timestamps, UUIDPk, Versioned


class LeadAssignmentHistory(UUIDPk, Base):
    """Every owner change. Append-only (spec 6.1)."""

    __tablename__ = "lead_assignment_history"
    __table_args__ = (
        Index("ix_lead_assignment_history_lead", "visitor_lead_id", "assigned_at"),
        Index("ix_lead_assignment_history_edition", "edition_id", "assigned_at"),
        CheckConstraint(
            "method IN ('MANUAL', 'BULK', 'ROUND_ROBIN', 'IMPORT')", name="method_valid"
        ),
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


class VisitorCallActivity(UUIDPk, Base):
    """One call attempt. Append-only: never edited or deleted (spec 6.3)."""

    __tablename__ = "visitor_call_activities"
    __table_args__ = (
        UniqueConstraint("visitor_lead_id", "attempt_number"),
        Index("ix_visitor_call_activities_edition_called", "edition_id", "called_at"),
        Index("ix_visitor_call_activities_agent_called", "agent_id", "called_at"),
        CheckConstraint("attempt_number >= 1", name="attempt_positive"),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="duration_ok"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    visitor_lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitor_leads.id"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    call_result: Mapped[str] = mapped_column(String(30), nullable=False)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VisitorVerification(UUIDPk, Base):
    """Verification history; each row is the full state after a change. Append-only."""

    __tablename__ = "visitor_verifications"
    __table_args__ = (
        Index("ix_visitor_verifications_lead", "visitor_lead_id", "created_at"),
        CheckConstraint("NOT (is_valid_lead AND is_invalid)", name="valid_xor_invalid"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False, index=True
    )
    visitor_lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitor_leads.id"), nullable=False
    )
    is_valid_lead: Mapped[bool] = mapped_column(nullable=False)
    is_invalid: Mapped[bool] = mapped_column(nullable=False)
    attend: Mapped[str | None] = mapped_column(String(30))
    b2b_matching: Mapped[bool] = mapped_column(nullable=False)
    buyer_type: Mapped[str | None] = mapped_column(String(10))
    # The call this verification came with (dashboard counts per call); NULL for a save on the
    # Verification tab between calls.
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visitor_call_activities.id"), index=True
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VisitorFollowup(UUIDPk, Timestamps, Versioned, Base):
    __tablename__ = "visitor_followups"
    __table_args__ = (
        Index("ix_visitor_followups_edition_status_due", "edition_id", "status", "due_at"),
        Index("ix_visitor_followups_assignee_due", "assigned_to", "status", "due_at"),
        CheckConstraint("status IN ('OPEN', 'DONE', 'CANCELLED')", name="status_valid"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    visitor_lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitor_leads.id"), nullable=False, index=True
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    note: Mapped[str | None] = mapped_column(Text)
    created_from_call_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visitor_call_activities.id")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class VisitorFollowupChange(UUIDPk, Base):
    """Follow-up history: create, reschedule, done, cancel. Append-only."""

    __tablename__ = "visitor_followup_changes"

    followup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitor_followups.id"), nullable=False, index=True
    )
    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    old_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FollowupReminder(UUIDPk, Base):
    """One row per reminder; the unique key makes a reminder impossible to send twice."""

    __tablename__ = "followup_reminders"

    # followup:{id}:{due_at}
    dedup_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    followup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitor_followups.id"), nullable=False, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
