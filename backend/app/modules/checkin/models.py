import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk, Versioned


class Gate(UUIDPk, Timestamps, Versioned, Base):
    """spec 8.1: each gate belongs to one edition."""

    __tablename__ = "gates"
    __table_args__ = (UniqueConstraint("edition_id", "code"),)

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ScannerDevice(UUIDPk, Timestamps, Versioned, Base):
    """A registered scanner bound to one gate (and so one edition). Revocable (spec 8.3)."""

    __tablename__ = "scanner_devices"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'ACTIVE', 'REVOKED')", name="status_valid"),
        CheckConstraint("status <> 'ACTIVE' OR secret_hash IS NOT NULL", name="active_has_secret"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False, index=True
    )
    gate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gates.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING")
    # One-time activation code (hash), cleared once used.
    activation_code_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    activation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    secret_hash: Mapped[str | None] = mapped_column(String(64))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ScanAttempt(UUIDPk, Base):
    """Every scan, valid or not. Append-only; scan_event_id makes retries idempotent."""

    __tablename__ = "scan_attempts"
    __table_args__ = (
        Index("ix_scan_attempts_edition_date", "edition_id", "local_date"),
        Index("ix_scan_attempts_gate_scanned", "gate_id", "scanned_at"),
        Index("ix_scan_attempts_registration_date", "registration_id", "local_date"),
        CheckConstraint("mode IN ('ONLINE', 'OFFLINE', 'OVERRIDE')", name="mode_valid"),
        CheckConstraint(
            "outcome IN ('ACCEPTED', 'REJECTED_UNKNOWN', 'REJECTED_REVOKED', "
            "'REJECTED_WRONG_EDITION', 'REJECTED_CANCELLED')",
            name="outcome_valid",
        ),
        CheckConstraint(
            "mode <> 'OVERRIDE' OR (recorded_by IS NOT NULL AND reason IS NOT NULL)",
            name="override_attributed",
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    gate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gates.id"), nullable=False)
    device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scanner_devices.id"))
    scan_event_id: Mapped[uuid.UUID] = mapped_column(unique=True, nullable=False)
    # Hash of the scanned token; the raw token never reaches the server log or database.
    token_hash: Mapped[str | None] = mapped_column(String(64))
    credential_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("qr_credentials.id"))
    registration_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visitor_registrations.id")
    )
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    provisional_result: Mapped[str | None] = mapped_column(String(30))
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String(500))


class VisitorCheckin(UUIDPk, Timestamps, Base):
    """First valid entry per registration and event-local day.

    Repeat entries are the other ACCEPTED attempts. first_scan_attempt_id moves when an
    offline scan with an earlier time syncs later; the server is the final decision.
    """

    __tablename__ = "visitor_checkins"
    __table_args__ = (
        UniqueConstraint("registration_id", "local_date"),
        Index("ix_visitor_checkins_edition_date", "edition_id", "local_date"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    registration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitor_registrations.id"), nullable=False
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    first_scan_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scan_attempts.id"), nullable=False, unique=True
    )
    first_scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gates.id"), nullable=False)
