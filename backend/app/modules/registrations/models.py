import uuid
from datetime import datetime

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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk, Versioned


class VisitorRegistration(UUIDPk, Timestamps, Versioned, Base):
    """spec 7.1. One active registration per lead and edition."""

    __tablename__ = "visitor_registrations"
    __table_args__ = (
        Index(
            "uq_visitor_registrations_active_lead",
            "edition_id",
            "visitor_lead_id",
            unique=True,
            postgresql_where=text("status = 'REGISTERED'"),
        ),
        Index("ix_visitor_registrations_edition_registered", "edition_id", "registered_at"),
        CheckConstraint(
            "channel IN ('WEBSITE', 'ADMIN', 'TELEMARKETING', 'API', 'IMPORT')",
            name="channel_valid",
        ),
        CheckConstraint("status IN ('REGISTERED', 'CANCELLED')", name="status_valid"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    visitor_lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitor_leads.id"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="REGISTERED")
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    registered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class QrCredential(UUIDPk, Base):
    """spec 7.2. Lookups use token_hash; token_enc lets a resend reuse the same code."""

    __tablename__ = "qr_credentials"
    __table_args__ = (
        Index(
            "uq_qr_credentials_active_registration",
            "registration_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        CheckConstraint("status IN ('ACTIVE', 'REVOKED')", name="status_valid"),
        CheckConstraint(
            "(status = 'REVOKED') = (revoked_at IS NOT NULL)", name="revoked_at_matches"
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False, index=True
    )
    registration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitor_registrations.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="ACTIVE")
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    issued_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    revoke_reason: Mapped[str | None] = mapped_column(String(500))


class EmailTemplate(UUIDPk, Base):
    """Versioned and append-only: an edit is a new version. edition_id NULL = system default."""

    __tablename__ = "email_templates"
    __table_args__ = (
        UniqueConstraint(
            "edition_id", "template_key", "version", postgresql_nulls_not_distinct=True
        ),
        CheckConstraint("template_key IN ('QR_CONFIRMATION')", name="template_key_valid"),
    )

    edition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("exhibition_editions.id"))
    template_key: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class EmailJob(UUIDPk, Timestamps, Base):
    """spec 7.3: one outgoing email and its delivery state."""

    __tablename__ = "email_jobs"
    __table_args__ = (
        Index("ix_email_jobs_edition_status", "edition_id", "status"),
        Index("ix_email_jobs_registration", "registration_id", "queued_at"),
        CheckConstraint(
            "status IN ('QUEUED', 'SENDING', 'SENT', 'FAILED', 'CANCELLED')", name="status_valid"
        ),
        CheckConstraint("kind IN ('QR_CONFIRMATION')", name="kind_valid"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    registration_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visitor_registrations.id")
    )
    qr_credential_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("qr_credentials.id"))
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("email_templates.id"), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(300))
    # Safe summary only (exception type, SMTP code); never the message body or credentials.
    error_summary: Mapped[str | None] = mapped_column(String(500))
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class EmailLog(UUIDPk, Base):
    """Append-only event trail per email job."""

    __tablename__ = "email_logs"

    email_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_jobs.id"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
