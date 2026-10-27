import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk, Versioned


class CampaignLink(UUIDPk, Timestamps, Versioned, Base):
    """A shareable public form for one edition (owner request 2026-10-26)."""

    __tablename__ = "campaign_links"
    __table_args__ = (
        UniqueConstraint("edition_id", "name"),
        CheckConstraint(
            "max_submissions IS NULL OR max_submissions > 0", name="max_submissions_positive"
        ),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR starts_at < ends_at", name="period_valid"
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Public part of the URL (/r/{token}). Replaced on "new link"; the old one stops working.
    token: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    lead_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lead_sources.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_submissions: Mapped[int | None] = mapped_column(Integer)
    submission_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gtm_container_id: Mapped[str | None] = mapped_column(String(20))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class CampaignSubmission(UUIDPk, Base):
    """Every form post, for abuse review. The IP is a keyed hash, never the address."""

    __tablename__ = "campaign_submissions"
    __table_args__ = (
        Index("ix_campaign_submissions_link_created", "campaign_link_id", "created_at"),
        CheckConstraint("outcome IN ('CREATED', 'DUPLICATE', 'BOT')", name="outcome_valid"),
    )

    campaign_link_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_links.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    consent_version: Mapped[str | None] = mapped_column(String(20))
    visitor_lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visitor_leads.id"))


class CampaignView(Base):
    """Form opens per link and edition-local day; one per visitor (keyed IP hash) per day."""

    __tablename__ = "campaign_views"

    campaign_link_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_links.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
