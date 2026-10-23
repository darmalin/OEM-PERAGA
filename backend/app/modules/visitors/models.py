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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk, Versioned


def _in(col: str, values: list[str]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class VisitorLead(UUIDPk, Timestamps, Versioned, Base):
    __tablename__ = "visitor_leads"
    __table_args__ = (
        # spec 5.2: duplicates within an edition are rejected by the database.
        Index(
            "uq_visitor_leads_edition_email",
            "edition_id",
            "email_normalized",
            unique=True,
            postgresql_where=text("email_normalized IS NOT NULL"),
        ),
        Index(
            "uq_visitor_leads_edition_phone",
            "edition_id",
            "phone_normalized",
            unique=True,
            postgresql_where=text("phone_normalized IS NOT NULL"),
        ),
        Index(
            "uq_visitor_leads_edition_external",
            "edition_id",
            "external_source",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        UniqueConstraint("edition_id", "registration_code"),
        Index("ix_visitor_leads_edition_tm_status", "edition_id", "telemarketing_status"),
        Index("ix_visitor_leads_edition_owner", "edition_id", "lead_owner_id"),
        Index("ix_visitor_leads_edition_updated", "edition_id", text("updated_at DESC")),
        Index("ix_visitor_leads_edition_followup", "edition_id", "next_followup_at"),
        CheckConstraint(
            "email_normalized IS NOT NULL OR phone_normalized IS NOT NULL",
            name="email_or_phone",
        ),
        CheckConstraint("NOT (is_valid_lead AND is_invalid)", name="valid_xor_invalid"),
        CheckConstraint(
            _in("source", ["EXCEL", "API", "MANUAL", "WEBSITE", "TELEMARKETING"]),
            name="source_valid",
        ),
        CheckConstraint(
            "gender IS NULL OR " + _in("gender", ["MALE", "FEMALE", "OTHER"]), name="gender_valid"
        ),
        CheckConstraint(
            _in(
                "telemarketing_status",
                ["NEW", "ANSWER", "NO_ANSWER", "RECONTACTED", "RETRY_NO_ANSWER"],
            ),
            name="tm_status_valid",
        ),
        CheckConstraint(
            _in("registration_status", ["NOT_REGISTERED", "REGISTERED", "CANCELLED"]),
            name="registration_status_valid",
        ),
        CheckConstraint(_in("qr_status", ["NONE", "ACTIVE", "REVOKED"]), name="qr_status_valid"),
        CheckConstraint(
            "attend IS NULL OR "
            + _in(
                "attend",
                [
                    "ATTEND",
                    "ATTEND_SOURCING",
                    "UNDER_CONSIDERATION",
                    "NOT_ATTEND",
                    "HANG_UP_IMMEDIATELY",
                ],
            ),
            name="attend_valid",
        ),
        CheckConstraint(
            "buyer_type IS NULL OR " + _in("buyer_type", ["B_SIDE", "C_SIDE"]),
            name="buyer_type_valid",
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    # "Registration ID" in the UI: edition prefix + 6-digit counter. Not the primary key.
    registration_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    lead_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    first_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    email_normalized: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    phone_normalized: Mapped[str | None] = mapped_column(String(32))
    gender: Mapped[str | None] = mapped_column(String(10))
    company_name: Mapped[str | None] = mapped_column(String(300))
    job_title: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(String(500))
    business_type: Mapped[str | None] = mapped_column(String(100))
    branch: Mapped[str | None] = mapped_column(String(100))
    exhibition_type: Mapped[str | None] = mapped_column(String(100))
    # How the lead came in (MANUAL, EXCEL, ...; "Channel" in the UI). Set by the system.
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # "Source" in the UI: campaign or list the lead came from, from the global master data.
    lead_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lead_sources.id"), index=True
    )
    lead_owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # Free text (owner decision 2026-10-22, like the old system); was a multi-select until 0016.
    product_categories: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)

    # Verification (current values; history lives in visitor_verifications).
    is_valid_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_invalid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attend: Mapped[str | None] = mapped_column(String(30))
    b2b_matching: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    buyer_type: Mapped[str | None] = mapped_column(String(10))
    verification_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Separate statuses, never one generic status (spec 4.4, rule 9).
    telemarketing_status: Mapped[str] = mapped_column(String(20), nullable=False, default="NEW")
    registration_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="NOT_REGISTERED"
    )
    qr_status: Mapped[str] = mapped_column(String(10), nullable=False, default="NONE")
    call_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_call_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    external_source: Mapped[str | None] = mapped_column(String(50))
    external_id: Mapped[str | None] = mapped_column(String(100))
    # Import that created the lead, for traceability and in-file duplicate detection.
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_jobs.id"), index=True
    )
    custom_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}", default=dict
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class LeadSourceOption(UUIDPk, Timestamps, Versioned, Base):
    """Global master data for the lead "Source" select (owner decision 2026-10-22)."""

    __tablename__ = "lead_sources"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class EditionFieldOption(UUIDPk, Timestamps, Versioned, Base):
    """Options for configurable selects (Business Type, Branch, ...), per edition."""

    __tablename__ = "edition_field_options"
    __table_args__ = (
        UniqueConstraint("edition_id", "field", "value"),
        CheckConstraint(
            _in("field", ["BUSINESS_TYPE", "BRANCH", "EXHIBITION_TYPE", "PRODUCT_CATEGORY"]),
            name="field_valid",
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    field: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class VisitorCustomFieldDefinition(UUIDPk, Timestamps, Versioned, Base):
    """spec 4.5; scoped per edition (D5 default)."""

    __tablename__ = "visitor_custom_field_definitions"
    __table_args__ = (
        UniqueConstraint("edition_id", "field_key"),
        CheckConstraint(
            _in(
                "field_type",
                ["text", "textarea", "number", "date", "select", "multi_select", "checkbox"],
            ),
            name="field_type_valid",
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    field_key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    validation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    in_import: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    in_export: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
