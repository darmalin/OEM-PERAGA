import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk, Versioned


class EmailAccount(UUIDPk, Timestamps, Versioned, Base):
    """An SMTP account email is sent through (System > Email Accounts, Super Admin only)."""

    __tablename__ = "email_accounts"
    __table_args__ = (
        CheckConstraint("security IN ('NONE', 'STARTTLS', 'SSL')", name="security_valid"),
        # At most one default: the account for system emails (password reset, OTP later).
        Index(
            "uq_email_accounts_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(200))
    from_address: Mapped[str] = mapped_column(String(320), nullable=False)
    reply_to: Mapped[str | None] = mapped_column(String(320))
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    security: Mapped[str] = mapped_column(String(10), nullable=False)
    username: Mapped[str | None] = mapped_column(String(320))
    # Fernet-encrypted with EMS_APP_ENCRYPTION_KEY; never returned by the API.
    password_enc: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_test_detail: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class EmailJob(UUIDPk, Timestamps, Base):
    """spec 7.3: one outgoing email and its delivery state. Every email the system sends."""

    __tablename__ = "email_jobs"
    __table_args__ = (
        Index("ix_email_jobs_edition_status", "edition_id", "status"),
        Index("ix_email_jobs_registration", "registration_id", "queued_at"),
        Index("ix_email_jobs_queued", "queued_at"),
        CheckConstraint(
            "status IN ('QUEUED', 'SENDING', 'SENT', 'FAILED', 'CANCELLED')", name="status_valid"
        ),
        CheckConstraint(
            "kind IN ('QR_CONFIRMATION', 'PASSWORD_RESET', 'FOLLOWUP_REMINDER', 'TEST')",
            name="kind_valid",
        ),
    )

    # NULL for system emails (password reset, test, staff reminders without an edition).
    edition_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("exhibition_editions.id"))
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    registration_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("visitor_registrations.id")
    )
    qr_credential_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("qr_credentials.id"))
    visitor_lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visitor_leads.id"))
    # The staff user an email is about (password reset, reminder).
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(300))
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_templates.id"))
    template_version: Mapped[int | None] = mapped_column(Integer)
    # Fixed for TEST; otherwise set on each attempt from the edition or the default account.
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_accounts.id"))
    from_address: Mapped[str | None] = mapped_column(String(320))
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
