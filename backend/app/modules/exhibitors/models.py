import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
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
from app.modules.exhibitors.rules import (
    BOOTH_STAGES,
    ContractStatus,
    PaymentMethod,
    PaymentStatus,
    SalesStage,
)

MONEY = Numeric(14, 2)


def _in(col: str, values: list[str] | frozenset[str]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in sorted(values))})"


class Booth(UUIDPk, Timestamps, Versioned, Base):
    """Booth inventory of an edition."""

    __tablename__ = "booths"
    __table_args__ = (
        UniqueConstraint("edition_id", "code"),
        # Target of the (booth_id, edition_id) FK on exhibitor_leads: no cross-edition booking.
        UniqueConstraint("id", "edition_id", name="uq_booths_id_edition"),
        CheckConstraint("area_sqm > 0", name="area_positive"),
        CheckConstraint("price >= 0", name="price_not_negative"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    hall: Mapped[str | None] = mapped_column(String(100))
    area_sqm: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ExhibitorAccount(UUIDPk, Timestamps, Versioned, Base):
    """Portal login of an exhibitor company, kept apart from staff users.

    Not edition data: one account can exhibit in several editions (one lead per edition).
    """

    __tablename__ = "exhibitor_accounts"
    __table_args__ = (
        UniqueConstraint("email_normalized"),
        Index(
            "uq_exhibitor_accounts_invite_token_hash",
            "invite_token_hash",
            unique=True,
            postgresql_where=text("invite_token_hash IS NOT NULL"),
        ),
        CheckConstraint(
            "(invite_token_hash IS NULL) = (invite_expires_at IS NULL)", name="invite_complete"
        ),
        CheckConstraint(
            "activated_at IS NULL OR password_hash IS NOT NULL", name="activated_has_password"
        ),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    # NULL until the invitation is accepted.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # SHA-256 of the single-use invitation token; the raw token is shown once, never stored.
    invite_token_hash: Mapped[str | None] = mapped_column(String(64))
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ExhibitorContractCounter(Base):
    """Per-edition contract number counter, incremented with UPSERT ... RETURNING."""

    __tablename__ = "exhibitor_contract_counters"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id", ondelete="CASCADE"), primary_key=True
    )
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ExhibitorLead(UUIDPk, Timestamps, Versioned, Base):
    """A company that may rent a booth. Not a visitor lead: separate table, separate pipeline."""

    __tablename__ = "exhibitor_leads"
    __table_args__ = (
        # Target of the (exhibitor_lead_id, edition_id) FKs of the order forms (migration 0030).
        UniqueConstraint("id", "edition_id", name="uq_exhibitor_leads_id_edition"),
        Index(
            "uq_exhibitor_leads_edition_email",
            "edition_id",
            "email_normalized",
            unique=True,
        ),
        # A booth is sold once per edition.
        Index(
            "uq_exhibitor_leads_booth",
            "booth_id",
            unique=True,
            postgresql_where=text("booth_id IS NOT NULL"),
        ),
        ForeignKeyConstraint(
            ["booth_id", "edition_id"],
            ["booths.id", "booths.edition_id"],
            name="fk_exhibitor_leads_booth_id_booths",
        ),
        Index("ix_exhibitor_leads_edition_stage", "edition_id", "stage"),
        Index("ix_exhibitor_leads_edition_owner", "edition_id", "lead_owner_id"),
        Index("ix_exhibitor_leads_edition_updated", "edition_id", text("updated_at DESC")),
        CheckConstraint(_in("stage", list(SalesStage)), name="stage_valid"),
        CheckConstraint(
            f"booth_id IS NULL OR {_in('stage', BOOTH_STAGES)}", name="booth_only_when_selling"
        ),
        CheckConstraint("stage <> 'EXHIBITOR' OR booth_id IS NOT NULL", name="exhibitor_has_booth"),
        CheckConstraint(
            "stage <> 'EXHIBITOR' OR exhibitor_account_id IS NOT NULL", name="exhibitor_has_account"
        ),
        # One portal account exhibits once per edition.
        Index(
            "uq_exhibitor_leads_edition_account",
            "edition_id",
            "exhibitor_account_id",
            unique=True,
            postgresql_where=text("exhibitor_account_id IS NOT NULL"),
        ),
        CheckConstraint(
            "budget_estimate IS NULL OR budget_estimate >= 0", name="budget_not_negative"
        ),
        CheckConstraint("booth_price IS NULL OR booth_price >= 0", name="booth_price_not_negative"),
        # A price belongs to a held booth; without one the booth's list price applies (0035).
        CheckConstraint(
            "booth_price IS NULL OR booth_id IS NOT NULL", name="booth_price_with_booth"
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    phone_normalized: Mapped[str | None] = mapped_column(String(32))
    product_categories: Mapped[str | None] = mapped_column(Text)
    booth_preference: Mapped[str | None] = mapped_column(Text)
    budget_estimate: Mapped[Decimal | None] = mapped_column(MONEY)
    notes: Mapped[str | None] = mapped_column(Text)

    stage: Mapped[str] = mapped_column(String(20), nullable=False, default=SalesStage.LEAD)
    lost_reason: Mapped[str | None] = mapped_column(Text)
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    booth_id: Mapped[uuid.UUID | None] = mapped_column()
    booth_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The price agreed for the held booth, in the booth's currency. Starts at the booth's list
    # price; staff may change it. Copied into the contract at Convert.
    booth_price: Mapped[Decimal | None] = mapped_column(MONEY)
    exhibitor_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exhibitor_accounts.id"), index=True
    )

    lead_owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ExhibitorContract(UUIDPk, Timestamps, Versioned, Base):
    """One contract per exhibitor; filled in the portal while DRAFT, read-only once SIGNED."""

    __tablename__ = "exhibitor_contracts"
    __table_args__ = (
        UniqueConstraint("exhibitor_lead_id"),
        Index(
            "uq_exhibitor_contracts_edition_number",
            "edition_id",
            "contract_number",
            unique=True,
            postgresql_where=text("contract_number IS NOT NULL"),
        ),
        Index("ix_exhibitor_contracts_edition_status", "edition_id", "status"),
        CheckConstraint(_in("status", list(ContractStatus)), name="status_valid"),
        CheckConstraint("booth_price >= 0", name="booth_price_not_negative"),
        CheckConstraint(
            "discount_amount >= 0 AND discount_amount <= booth_price", name="discount_valid"
        ),
        CheckConstraint("total_amount IS NULL OR total_amount >= 0", name="total_not_negative"),
        CheckConstraint(
            "status <> 'SIGNED' OR (contract_number IS NOT NULL AND pic_name IS NOT NULL"
            " AND company_address IS NOT NULL AND total_amount IS NOT NULL"
            " AND signed_at IS NOT NULL AND signed_file_key IS NOT NULL)",
            name="signed_complete",
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    exhibitor_lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibitor_leads.id"), nullable=False
    )
    contract_number: Mapped[str | None] = mapped_column(String(50))
    pic_name: Mapped[str | None] = mapped_column(String(200))
    company_address: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[str | None] = mapped_column(String(30))  # NPWP
    # Copied from the booth when the contract is created; later booth price edits do not apply.
    booth_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal(0))
    # VAT from an accepted quotation (migration 0037): vat_rate % of (price - discount) x num/den.
    # 0 means no VAT, as for contracts made before quotations.
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal(0), server_default="0"
    )
    vat_base_num: Mapped[int] = mapped_column(
        Integer, nullable=False, default=11, server_default="11"
    )
    vat_base_den: Mapped[int] = mapped_column(
        Integer, nullable=False, default=12, server_default="12"
    )
    vat_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal(0), server_default="0"
    )
    # booth_price - discount_amount + vat_amount
    total_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # [{"label", "percent", "due_on", "amount"}] from the accepted quotation; shown, not enforced.
    payment_terms: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("exhibitor_quotations.id"))
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=ContractStatus.DRAFT)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Storage object key of the signed PDF (BACKEND_RULES/security-permissions.md "Uploads").
    signed_file_key: Mapped[str | None] = mapped_column(String(500))
    signed_file_name: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ExhibitorPayment(UUIDPk, Timestamps, Versioned, Base):
    """One recorded installment against a contract. Tagging only, no payment gateway."""

    __tablename__ = "exhibitor_payments"
    __table_args__ = (
        Index("ix_exhibitor_payments_edition_status", "edition_id", "status"),
        CheckConstraint(_in("status", list(PaymentStatus)), name="status_valid"),
        CheckConstraint(_in("method", list(PaymentMethod)), name="method_valid"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "(status = 'PENDING') = (reviewed_at IS NULL)", name="reviewed_unless_pending"
        ),
        # A payment is for the booth contract or for one service order, never both (migration
        # 0034, docs/EXHIBITOR_ORDER_FORMS.md Phase 7).
        CheckConstraint("num_nonnulls(contract_id, order_id) = 1", name="one_target"),
        ForeignKeyConstraint(
            ["order_id", "edition_id"],
            ["exhibitor_orders.id", "exhibitor_orders.edition_id"],
            name="fk_exhibitor_payments_order_id_exhibitor_orders",
        ),
        Index("ix_exhibitor_payments_order_id", "order_id"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exhibitor_contracts.id"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    proof_file_key: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=PaymentStatus.PENDING)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
