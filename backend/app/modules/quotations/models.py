"""Exhibitor quotations (docs/EXHIBITOR_QUOTATIONS.md, migration 0036)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk, Versioned
from app.modules.exhibitors.models import MONEY
from app.modules.quotations.rules import QuotationStatus, StandType

SQM = Numeric(10, 2)


def _in(col: str, values: list[str]) -> str:
    return f"{col} IN ({', '.join(repr(str(v)) for v in sorted(values))})"


class QuotationSettings(UUIDPk, Timestamps, Versioned, Base):
    """What every quotation of an edition starts from: number, letter text, rates, terms, signer.
    A quotation copies what it uses, so editing these never changes one already made."""

    __tablename__ = "quotation_settings"
    __table_args__ = (
        CheckConstraint("start_number >= 1", name="start_number_positive"),
        CheckConstraint("vat_rate >= 0 AND vat_rate <= 100", name="vat_rate_valid"),
        CheckConstraint(
            "vat_base_num > 0 AND vat_base_den > 0 AND vat_base_num <= vat_base_den",
            name="vat_base_valid",
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), unique=True, nullable=False
    )
    # Number: <running number>/<company_code>/<code>/<month>/<year>, e.g. 112/PNJS/IIT/VII/2026.
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    company_code: Mapped[str] = mapped_column(String(20), nullable=False, default="PNJS")
    # First running number for a code in a year: the numbers already used in Excel come before it.
    start_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    place: Mapped[str] = mapped_column(String(100), nullable=False, default="Jakarta")
    # "INATEX 2027 (The 23rd Indonesia International ... Expo)" and "14-17 April 2027 at JIEXPO".
    letter_name: Mapped[str | None] = mapped_column(Text)
    event_text: Mapped[str | None] = mapped_column(Text)
    # [{"currency": "IDR", "stand_type": "RAW", "rate": "4850000.00"}, ...]: price per sqm.
    rates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    shell_includes: Mapped[str | None] = mapped_column(Text)
    discount_label: Mapped[str] = mapped_column(
        String(60), nullable=False, default="Special Discount"
    )
    # VAT for IDR: 12% of an 11/12 tax base. USD quotations start without VAT.
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal(12))
    vat_base_num: Mapped[int] = mapped_column(Integer, nullable=False, default=11)
    vat_base_den: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    # [{"label": "Booking Fee", "percent": "30", "due_on": "2026-07-31"}, ...]
    terms: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    signer_name: Mapped[str | None] = mapped_column(String(200))
    signer_title: Mapped[str | None] = mapped_column(String(200))
    signature_key: Mapped[str | None] = mapped_column(String(200))  # PNG/JPEG in storage
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class QuotationCounter(Base):
    """Running number per quotation code and year, shared by editions with the same code."""

    __tablename__ = "quotation_counters"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False)


class ExhibitorQuotation(UUIDPk, Timestamps, Versioned, Base):
    """One issued quotation. Never edited: a revision is a new quotation that supersedes it."""

    __tablename__ = "exhibitor_quotations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["exhibitor_lead_id", "edition_id"],
            ["exhibitor_leads.id", "exhibitor_leads.edition_id"],
            name="fk_exhibitor_quotations_lead",
        ),
        ForeignKeyConstraint(
            ["booth_id", "edition_id"],
            ["booths.id", "booths.edition_id"],
            name="fk_exhibitor_quotations_booth",
        ),
        UniqueConstraint("number"),
        Index("ix_exhibitor_quotations_lead", "exhibitor_lead_id", text("created_at DESC")),
        # One accepted quotation per lead (Phase 4).
        Index(
            "uq_exhibitor_quotations_accepted",
            "exhibitor_lead_id",
            unique=True,
            postgresql_where=text("status = 'ACCEPTED'"),
        ),
        CheckConstraint(_in("status", list(QuotationStatus)), name="status_valid"),
        CheckConstraint(_in("stand_type", list(StandType)), name="stand_type_valid"),
        CheckConstraint("charged_sqm > 0", name="charged_positive"),
        CheckConstraint(
            "complimentary_sqm >= 0 AND complimentary_sqm < area_sqm", name="complimentary_valid"
        ),
        CheckConstraint("discount_percent >= 0 AND discount_percent <= 100", name="discount_valid"),
        CheckConstraint("stand_rate >= 0 AND raw_rate >= 0", name="rates_not_negative"),
        CheckConstraint("total_amount >= 0", name="total_not_negative"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    exhibitor_lead_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    number: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default=QuotationStatus.ISSUED)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False)
    # The quotation it revises; that one is SUPERSEDED.
    replaces_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("exhibitor_quotations.id"))

    recipient_company: Mapped[str] = mapped_column(String(300), nullable=False)
    recipient_address: Mapped[str | None] = mapped_column(Text)
    attention: Mapped[str | None] = mapped_column(String(200))  # "Ms. Novy"

    stand_type: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    booth_id: Mapped[uuid.UUID | None] = mapped_column()
    booth_code: Mapped[str | None] = mapped_column(String(30))
    width_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    length_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    area_sqm: Mapped[Decimal] = mapped_column(SQM, nullable=False)
    complimentary_sqm: Mapped[Decimal] = mapped_column(SQM, nullable=False, default=Decimal(0))
    charged_sqm: Mapped[Decimal] = mapped_column(SQM, nullable=False)
    stand_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    raw_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_label: Mapped[str | None] = mapped_column(String(60))
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal(0)
    )
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # 0: no VAT
    vat_base_num: Mapped[int] = mapped_column(Integer, nullable=False)
    vat_base_den: Mapped[int] = mapped_column(Integer, nullable=False)

    gross_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cost_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # [{"label", "percent", "due_on", "amount"}], amounts summing to the total.
    terms: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    includes: Mapped[str | None] = mapped_column(Text)  # "(Include : Partition, ...)"
    notes: Mapped[str | None] = mapped_column(Text)
    # Letter text as printed: letter_name, event_text, place, signer_name, signer_title,
    # signature_key, company_code.
    letter: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
