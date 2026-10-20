import uuid
from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk, Versioned
from app.modules.exhibitions.rules import EditionStatus


class Venue(UUIDPk, Timestamps, Versioned, Base):
    __tablename__ = "venues"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(2))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Exhibition(UUIDPk, Timestamps, Versioned, Base):
    __tablename__ = "exhibitions"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Edition(UUIDPk, Timestamps, Versioned, Base):
    __tablename__ = "exhibition_editions"
    __table_args__ = (
        UniqueConstraint("exhibition_id", "year"),
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'CLOSED', 'ARCHIVED')", name="status_valid"),
        CheckConstraint("year BETWEEN 2000 AND 2100", name="year_range"),
    )

    exhibition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibitions.id"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("venues.id"), index=True)
    country: Mapped[str | None] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    registration_id_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[EditionStatus] = mapped_column(
        String(20), nullable=False, default=EditionStatus.DRAFT
    )
    # Email settings (spec 3): sender shown on QR and reminder emails.
    email_sender_name: Mapped[str | None] = mapped_column(String(200))
    email_reply_to: Mapped[str | None] = mapped_column(String(320))
    # Registration settings.
    public_registration_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Gate settings: offline cache lifetime override (D6), NULL = system default.
    scanner_cache_ttl_minutes: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class EditionCounter(Base):
    """Per-edition Registration ID counter, incremented with UPDATE ... RETURNING."""

    __tablename__ = "edition_counters"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id", ondelete="CASCADE"), primary_key=True
    )
    last_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
