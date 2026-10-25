import uuid
from datetime import datetime
from typing import Any

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk


class ImportJob(UUIDPk, Timestamps, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("ix_import_jobs_edition_created", "edition_id", "created_at"),
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'COMPLETED_WITH_ERRORS', 'FAILED')",
            name="status_valid",
        ),
        CheckConstraint(
            "import_type IN ('LEADS_ONLY', 'LEADS_AND_REGISTER')", name="import_type_valid"
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="QUEUED")
    import_type: Mapped[str] = mapped_column(String(30), nullable=False, default="LEADS_ONLY")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(100), nullable=False)
    column_mapping: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    total_rows: Mapped[int | None] = mapped_column(Integer)
    # Rows (by spreadsheet row number) already handled; a restarted job resumes after it.
    checkpoint_row: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Share new leads round robin among the edition teams' callers when rows are done.
    auto_assign: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assigned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # {user_id: {"name": ..., "count": n}}
    assign_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text)
    errors_object_key: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ImportRowError(UUIDPk, Base):
    """One rejected row. Append-only."""

    __tablename__ = "import_errors"
    __table_args__ = (Index("ix_import_errors_job_row", "import_job_id", "row_number"),)

    import_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False
    )
    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    # Safe subset only: first name, company, masked email/phone (never the full row).
    row_preview: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ImportMappingPreset(UUIDPk, Timestamps, Base):
    """Last confirmed column mapping, saved per edition."""

    __tablename__ = "import_mapping_presets"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False, unique=True
    )
    mapping: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ExportJob(UUIDPk, Timestamps, Base):
    """spec 11: Excel exports run in the worker; the file expires (EMS_EXPORT_TTL_SECONDS)."""

    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("ix_export_jobs_edition_created", "edition_id", "created_at"),
        Index("ix_export_jobs_status_expires", "status", "expires_at"),
        CheckConstraint("kind IN ('VISITORS', 'REPORT')", name="kind_valid"),
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'EXPIRED')",
            name="status_valid",
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # Filters / report params as sent; re-validated by the worker.
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    row_count: Mapped[int | None] = mapped_column(Integer)
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(Integer)
    object_key: Mapped[str | None] = mapped_column(String(100))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
