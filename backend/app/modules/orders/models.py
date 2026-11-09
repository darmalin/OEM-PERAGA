"""Exhibitor order forms (docs/EXHIBITOR_ORDER_FORMS.md, migration 0030)."""

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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk, Versioned
from app.modules.exhibitors.models import MONEY
from app.modules.orders.rules import (
    OPEN_STATUSES,
    AttachmentPurpose,
    DetailsType,
    OptionKind,
    OrderStatus,
    PricePeriod,
)


def _in(col: str, values: list[str] | frozenset[str]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in sorted(values))})"


def _array_of(col: str, values: list[str]) -> str:
    return f"{col} <@ ARRAY[{', '.join(repr(v) for v in sorted(values))}]::varchar[]"


class OrderForm(UUIDPk, Timestamps, Versioned, Base):
    """One order form of an edition (form 04 Electrical, ...), set up by staff."""

    __tablename__ = "order_forms"
    __table_args__ = (
        UniqueConstraint("edition_id", "code"),
        # Target of the (form_id, edition_id) FKs: no order or item crosses editions.
        UniqueConstraint("id", "edition_id", name="uq_order_forms_id_edition"),
        CheckConstraint("code ~ '^[0-9]{2}[a-z]?$'", name="code_format"),
        CheckConstraint(
            f"details_type IS NULL OR {_in('details_type', list(DetailsType))}",
            name="details_type_valid",
        ),
        CheckConstraint(
            _array_of("attachment_purposes", list(AttachmentPurpose)),
            name="attachment_purposes_valid",
        ),
        CheckConstraint("NOT allow_custom_items OR has_catalog", name="custom_items_need_catalog"),
        CheckConstraint(
            "closes_on IS NULL OR deadline_on IS NULL OR closes_on >= deadline_on",
            name="closes_after_deadline",
        ),
        CheckConstraint(
            "(secondary_deadline_label IS NULL) = (secondary_deadline_on IS NULL)",
            name="secondary_deadline_complete",
        ),
        Index("ix_order_forms_edition_sort", "edition_id", "sort_order"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    details_type: Mapped[str | None] = mapped_column(String(30))
    has_catalog: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_custom_items: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attachment_purposes: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), nullable=False, default=list
    )
    # Shown with a countdown; submitting stays possible until closes_on (decision O8).
    deadline_on: Mapped[date | None] = mapped_column(Date)
    # Last day to submit; NULL means the edition's order_expired_on.
    closes_on: Mapped[date | None] = mapped_column(Date)
    # Form 02 has a Booking and a Material deadline.
    secondary_deadline_label: Mapped[str | None] = mapped_column(String(100))
    secondary_deadline_on: Mapped[date | None] = mapped_column(Date)
    instructions: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class OrderFormItem(UUIDPk, Timestamps, Versioned, Base):
    """Catalog item of a form. Never deleted (order lines point at it); deactivate instead."""

    __tablename__ = "order_form_items"
    __table_args__ = (
        UniqueConstraint("form_id", "code"),
        UniqueConstraint("id", "edition_id", name="uq_order_form_items_id_edition"),
        ForeignKeyConstraint(
            ["form_id", "edition_id"],
            ["order_forms.id", "order_forms.edition_id"],
            name="fk_order_form_items_form_id_order_forms",
        ),
        CheckConstraint("price_regular >= 0", name="price_regular_not_negative"),
        CheckConstraint(
            "price_surcharge IS NULL OR price_surcharge >= 0", name="price_surcharge_not_negative"
        ),
        CheckConstraint(
            "price_onsite IS NULL OR price_onsite >= 0", name="price_onsite_not_negative"
        ),
        CheckConstraint("max_quantity IS NULL OR max_quantity > 0", name="max_quantity_positive"),
        Index("ix_order_form_items_form_sort", "form_id", "sort_order"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    form_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    section: Mapped[str | None] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    size: Mapped[str | None] = mapped_column(String(100))
    unit: Mapped[str | None] = mapped_column(String(50))
    image_key: Mapped[str | None] = mapped_column(String(500))
    # Missing surcharge or onsite price means the regular price (decision O4).
    price_regular: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price_surcharge: Mapped[Decimal | None] = mapped_column(MONEY)
    price_onsite: Mapped[Decimal | None] = mapped_column(MONEY)
    max_quantity: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ExhibitorOrderCounter(Base):
    """Per-edition order number counter, incremented with UPSERT ... RETURNING."""

    __tablename__ = "exhibitor_order_counters"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id", ondelete="CASCADE"), primary_key=True
    )
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ExhibitorOrder(UUIDPk, Timestamps, Versioned, Base):
    """One order of an exhibitor on one form. Written in the portal, reviewed by staff.

    `details` holds the form's answers, validated against the form's code-defined schema
    (decision O10); the documented JSONB exception in BACKEND_RULES/database.md.
    """

    __tablename__ = "exhibitor_orders"
    __table_args__ = (
        UniqueConstraint("id", "edition_id", name="uq_exhibitor_orders_id_edition"),
        ForeignKeyConstraint(
            ["exhibitor_lead_id", "edition_id"],
            ["exhibitor_leads.id", "exhibitor_leads.edition_id"],
            name="fk_exhibitor_orders_exhibitor_lead_id_exhibitor_leads",
        ),
        ForeignKeyConstraint(
            ["form_id", "edition_id"],
            ["order_forms.id", "order_forms.edition_id"],
            name="fk_exhibitor_orders_form_id_order_forms",
        ),
        # One order the exhibitor can still edit per form (decision O7).
        Index(
            "uq_exhibitor_orders_open_per_form",
            "exhibitor_lead_id",
            "form_id",
            unique=True,
            postgresql_where=text(_in("status", OPEN_STATUSES)),
        ),
        Index(
            "uq_exhibitor_orders_edition_number",
            "edition_id",
            "order_number",
            unique=True,
            postgresql_where=text("order_number IS NOT NULL"),
        ),
        Index("ix_exhibitor_orders_edition_status", "edition_id", "status"),
        Index("ix_exhibitor_orders_edition_form_status", "edition_id", "form_id", "status"),
        Index("ix_exhibitor_orders_exhibitor_lead_id", "exhibitor_lead_id"),
        CheckConstraint(_in("status", list(OrderStatus)), name="status_valid"),
        CheckConstraint(
            f"price_period IS NULL OR {_in('price_period', list(PricePeriod))}",
            name="price_period_valid",
        ),
        CheckConstraint("total >= 0", name="total_not_negative"),
        # Everything below is set on the first submit and kept afterwards.
        CheckConstraint(
            "(status = 'DRAFT') = (order_number IS NULL)"
            " AND (status = 'DRAFT') = (submitted_at IS NULL)"
            " AND (status = 'DRAFT') = (price_period IS NULL)"
            " AND (status = 'DRAFT') = (booth_id_at_submit IS NULL)"
            " AND (booth_id_at_submit IS NULL) = (area_sqm_at_submit IS NULL)",
            name="submitted_complete",
        ),
        CheckConstraint(
            "status NOT IN ('APPROVED', 'RETURNED') OR (reviewed_at IS NOT NULL"
            " AND reviewed_by IS NOT NULL)",
            name="reviewed_complete",
        ),
        CheckConstraint(
            "status <> 'RETURNED' OR review_notes IS NOT NULL", name="returned_has_reason"
        ),
        CheckConstraint(
            "(status = 'CANCELLED') = (cancel_reason IS NOT NULL)", name="cancelled_has_reason"
        ),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    exhibitor_lead_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    form_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    # <edition code>-O-0001, given on the first submit, so deleted drafts leave no gaps.
    order_number: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=OrderStatus.DRAFT)
    price_period: Mapped[str | None] = mapped_column(String(10))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    remarks: Mapped[str | None] = mapped_column(Text)
    # Sum of the priced lines, kept in step by the service; no tax or discount (decision O5).
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal(0))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exhibitor_accounts.id")
    )
    # The booth when last submitted: free quantities come from its area (decision O2).
    booth_id_at_submit: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("booths.id"))
    area_sqm_at_submit: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ExhibitorOrderLine(UUIDPk, Timestamps, Base):
    """A catalog item or an extra item (no item_id) on an order.

    Child rows of the order: written with it under the order's version, so who and when are
    on the order and in the audit log.
    """

    __tablename__ = "exhibitor_order_lines"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_id", "edition_id"],
            ["exhibitor_orders.id", "exhibitor_orders.edition_id"],
            name="fk_exhibitor_order_lines_order_id_exhibitor_orders",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["item_id", "edition_id"],
            ["order_form_items.id", "order_form_items.edition_id"],
            name="fk_exhibitor_order_lines_item_id_order_form_items",
        ),
        # One line per catalog item; quantity says how many.
        Index(
            "uq_exhibitor_order_lines_order_item",
            "order_id",
            "item_id",
            unique=True,
            postgresql_where=text("item_id IS NOT NULL"),
        ),
        Index("ix_exhibitor_order_lines_item_id", "item_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "free_quantity >= 0 AND free_quantity <= quantity", name="free_quantity_valid"
        ),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="unit_price_not_negative"),
        # Catalog lines always carry a price; extra items wait for staff (decision O6).
        CheckConstraint("item_id IS NULL OR unit_price IS NOT NULL", name="catalog_line_priced"),
        CheckConstraint("(unit_price IS NULL) = (amount IS NULL)", name="amount_with_price"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_not_negative"),
        CheckConstraint("item_id IS NULL OR image_key IS NULL", name="image_only_on_extra_items"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column()
    # Copied from the catalog item, so later catalog edits do not change sent orders.
    section: Mapped[str | None] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    size: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    free_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_price: Mapped[Decimal | None] = mapped_column(MONEY)
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    image_key: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ExhibitorOrderFile(UUIDPk, Timestamps, Base):
    """An attachment of an order (logo, fitting location, visa list). Replaced, never edited."""

    __tablename__ = "exhibitor_order_files"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_id", "edition_id"],
            ["exhibitor_orders.id", "exhibitor_orders.edition_id"],
            name="fk_exhibitor_order_files_order_id_exhibitor_orders",
            ondelete="CASCADE",
        ),
        UniqueConstraint("file_key"),
        CheckConstraint(_in("purpose", list(AttachmentPurpose)), name="purpose_valid"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exhibitor_accounts.id")
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ExhibitorFormWaiver(UUIDPk, Timestamps, Base):
    """The exhibitor ticked "I don't require this form"; not an order status (rule #9)."""

    __tablename__ = "exhibitor_form_waivers"
    __table_args__ = (
        UniqueConstraint("exhibitor_lead_id", "form_id"),
        ForeignKeyConstraint(
            ["exhibitor_lead_id", "edition_id"],
            ["exhibitor_leads.id", "exhibitor_leads.edition_id"],
            name="fk_exhibitor_form_waivers_exhibitor_lead_id_exhibitor_leads",
        ),
        ForeignKeyConstraint(
            ["form_id", "edition_id"],
            ["order_forms.id", "order_forms.edition_id"],
            name="fk_exhibitor_form_waivers_form_id_order_forms",
        ),
        Index("ix_exhibitor_form_waivers_form_id", "form_id"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    exhibitor_lead_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    form_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    waived_by_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exhibitor_accounts.id")
    )


class OrderFormOption(UUIDPk, Timestamps, Base):
    """One choice of a form's question (product category, official forwarder, seminar date).

    Replaced as a list per kind by staff; answers store the chosen text, so editing the list
    never changes sent orders.
    """

    __tablename__ = "order_form_options"
    __table_args__ = (
        UniqueConstraint("form_id", "kind", "value"),
        ForeignKeyConstraint(
            ["form_id", "edition_id"],
            ["order_forms.id", "order_forms.edition_id"],
            name="fk_order_form_options_form_id_order_forms",
            ondelete="CASCADE",
        ),
        CheckConstraint(_in("kind", list(OptionKind)), name="kind_valid"),
        Index("ix_order_form_options_form_kind_sort", "form_id", "kind", "sort_order"),
    )

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id"), nullable=False
    )
    form_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
