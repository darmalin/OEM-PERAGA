"""exhibitor order forms: forms, catalog items, orders, lines, files, waivers

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-09

Owner request 2026-11-09 (docs/EXHIBITOR_ORDER_FORMS.md, Phase 1): one generic set of tables for
the fourteen order forms of the old portal. Prices live in the catalog and are copied to the order
lines by the server on submit. Allowances (free quantities per booth area) come in Phase 6.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DETAILS_TYPES = (
    "advertising",
    "badges_visa",
    "directory_listing",
    "exhibit_details",
    "freight",
    "parking",
    "seminar",
    "social_media",
    "stand_service",
)
PURPOSES = ("FITTING_LOCATION", "LOGO", "OTHER", "PRODUCT_IMAGE", "VISA_LIST")


def _quoted(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]  # fmt: skip


def _audit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    ]


def _user_fks(table: str) -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f(f"fk_{table}_created_by_users")),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name=op.f(f"fk_{table}_updated_by_users")),
    ]  # fmt: skip


def _edition_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["edition_id"],
        ["exhibition_editions.id"],
        name=op.f(f"fk_{table}_edition_id_exhibition_editions"),
    )


def upgrade() -> None:
    # Target of the (exhibitor_lead_id, edition_id) FKs below.
    op.create_unique_constraint(
        "uq_exhibitor_leads_id_edition", "exhibitor_leads", ["id", "edition_id"]
    )

    op.create_table(
        "order_forms",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(5), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("details_type", sa.String(30), nullable=True),
        sa.Column("has_catalog", sa.Boolean(), nullable=False),
        sa.Column("allow_custom_items", sa.Boolean(), nullable=False),
        sa.Column("attachment_purposes", postgresql.ARRAY(sa.String(20)), nullable=False),
        sa.Column("deadline_on", sa.Date(), nullable=True),
        sa.Column("closes_on", sa.Date(), nullable=True),
        sa.Column("secondary_deadline_label", sa.String(100), nullable=True),
        sa.Column("secondary_deadline_on", sa.Date(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint("code ~ '^[0-9]{2}[a-z]?$'", name=op.f("ck_order_forms_code_format")),
        sa.CheckConstraint(f"details_type IS NULL OR details_type IN ({_quoted(DETAILS_TYPES)})", name=op.f("ck_order_forms_details_type_valid")),
        sa.CheckConstraint(f"attachment_purposes <@ ARRAY[{_quoted(PURPOSES)}]::varchar[]", name=op.f("ck_order_forms_attachment_purposes_valid")),
        sa.CheckConstraint("NOT allow_custom_items OR has_catalog", name=op.f("ck_order_forms_custom_items_need_catalog")),
        sa.CheckConstraint("closes_on IS NULL OR deadline_on IS NULL OR closes_on >= deadline_on", name=op.f("ck_order_forms_closes_after_deadline")),
        sa.CheckConstraint("(secondary_deadline_label IS NULL) = (secondary_deadline_on IS NULL)", name=op.f("ck_order_forms_secondary_deadline_complete")),
        _edition_fk("order_forms"),
        *_user_fks("order_forms"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_forms")),
        sa.UniqueConstraint("edition_id", "code", name=op.f("uq_order_forms_edition_id_code")),
        sa.UniqueConstraint("id", "edition_id", name="uq_order_forms_id_edition"),
    )  # fmt: skip
    op.create_index("ix_order_forms_edition_sort", "order_forms", ["edition_id", "sort_order"])

    op.create_table(
        "order_form_items",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("form_id", sa.Uuid(), nullable=False),
        sa.Column("section", sa.String(200), nullable=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("size", sa.String(100), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("image_key", sa.String(500), nullable=True),
        sa.Column("price_regular", sa.Numeric(14, 2), nullable=False),
        sa.Column("price_surcharge", sa.Numeric(14, 2), nullable=True),
        sa.Column("price_onsite", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_quantity", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint("price_regular >= 0", name=op.f("ck_order_form_items_price_regular_not_negative")),
        sa.CheckConstraint("price_surcharge IS NULL OR price_surcharge >= 0", name=op.f("ck_order_form_items_price_surcharge_not_negative")),
        sa.CheckConstraint("price_onsite IS NULL OR price_onsite >= 0", name=op.f("ck_order_form_items_price_onsite_not_negative")),
        sa.CheckConstraint("max_quantity IS NULL OR max_quantity > 0", name=op.f("ck_order_form_items_max_quantity_positive")),
        _edition_fk("order_form_items"),
        sa.ForeignKeyConstraint(["form_id", "edition_id"], ["order_forms.id", "order_forms.edition_id"], name="fk_order_form_items_form_id_order_forms"),
        *_user_fks("order_form_items"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_form_items")),
        sa.UniqueConstraint("form_id", "code", name=op.f("uq_order_form_items_form_id_code")),
        sa.UniqueConstraint("id", "edition_id", name="uq_order_form_items_id_edition"),
    )  # fmt: skip
    op.create_index("ix_order_form_items_form_sort", "order_form_items", ["form_id", "sort_order"])

    op.create_table(
        "exhibitor_order_counters",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["edition_id"], ["exhibition_editions.id"], name=op.f("fk_exhibitor_order_counters_edition_id_exhibition_editions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("edition_id", name=op.f("pk_exhibitor_order_counters")),
    )  # fmt: skip

    op.create_table(
        "exhibitor_orders",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("exhibitor_lead_id", sa.Uuid(), nullable=False),
        sa.Column("form_id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("price_period", sa.String(10), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("booth_id_at_submit", sa.Uuid(), nullable=True),
        sa.Column("area_sqm_at_submit", sa.Numeric(8, 2), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('APPROVED', 'CANCELLED', 'DRAFT', 'RETURNED', 'SUBMITTED')", name=op.f("ck_exhibitor_orders_status_valid")),
        sa.CheckConstraint("price_period IS NULL OR price_period IN ('ONSITE', 'REGULAR', 'SURCHARGE')", name=op.f("ck_exhibitor_orders_price_period_valid")),
        sa.CheckConstraint("total >= 0", name=op.f("ck_exhibitor_orders_total_not_negative")),
        sa.CheckConstraint(
            "(status = 'DRAFT') = (order_number IS NULL)"
            " AND (status = 'DRAFT') = (submitted_at IS NULL)"
            " AND (status = 'DRAFT') = (price_period IS NULL)"
            " AND (status = 'DRAFT') = (booth_id_at_submit IS NULL)"
            " AND (booth_id_at_submit IS NULL) = (area_sqm_at_submit IS NULL)",
            name=op.f("ck_exhibitor_orders_submitted_complete"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('APPROVED', 'RETURNED') OR (reviewed_at IS NOT NULL"
            " AND reviewed_by IS NOT NULL)",
            name=op.f("ck_exhibitor_orders_reviewed_complete"),
        ),
        sa.CheckConstraint("status <> 'RETURNED' OR review_notes IS NOT NULL", name=op.f("ck_exhibitor_orders_returned_has_reason")),
        sa.CheckConstraint("(status = 'CANCELLED') = (cancel_reason IS NOT NULL)", name=op.f("ck_exhibitor_orders_cancelled_has_reason")),
        _edition_fk("exhibitor_orders"),
        sa.ForeignKeyConstraint(["exhibitor_lead_id", "edition_id"], ["exhibitor_leads.id", "exhibitor_leads.edition_id"], name="fk_exhibitor_orders_exhibitor_lead_id_exhibitor_leads"),
        sa.ForeignKeyConstraint(["form_id", "edition_id"], ["order_forms.id", "order_forms.edition_id"], name="fk_exhibitor_orders_form_id_order_forms"),
        sa.ForeignKeyConstraint(["submitted_by_account_id"], ["exhibitor_accounts.id"], name=op.f("fk_exhibitor_orders_submitted_by_account_id_exhibitor_accounts")),
        sa.ForeignKeyConstraint(["booth_id_at_submit"], ["booths.id"], name=op.f("fk_exhibitor_orders_booth_id_at_submit_booths")),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], name=op.f("fk_exhibitor_orders_reviewed_by_users")),
        *_user_fks("exhibitor_orders"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitor_orders")),
        sa.UniqueConstraint("id", "edition_id", name="uq_exhibitor_orders_id_edition"),
    )  # fmt: skip
    op.create_index(
        "uq_exhibitor_orders_open_per_form",
        "exhibitor_orders",
        ["exhibitor_lead_id", "form_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('DRAFT', 'RETURNED')"),
    )
    op.create_index(
        "uq_exhibitor_orders_edition_number",
        "exhibitor_orders",
        ["edition_id", "order_number"],
        unique=True,
        postgresql_where=sa.text("order_number IS NOT NULL"),
    )
    op.create_index(
        "ix_exhibitor_orders_edition_status", "exhibitor_orders", ["edition_id", "status"]
    )
    op.create_index(
        "ix_exhibitor_orders_edition_form_status",
        "exhibitor_orders",
        ["edition_id", "form_id", "status"],
    )
    op.create_index(
        "ix_exhibitor_orders_exhibitor_lead_id", "exhibitor_orders", ["exhibitor_lead_id"]
    )

    op.create_table(
        "exhibitor_order_lines",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=True),
        sa.Column("section", sa.String(200), nullable=True),
        sa.Column("code", sa.String(30), nullable=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("size", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("free_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("image_key", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_exhibitor_order_lines_quantity_positive")),
        sa.CheckConstraint("free_quantity >= 0 AND free_quantity <= quantity", name=op.f("ck_exhibitor_order_lines_free_quantity_valid")),
        sa.CheckConstraint("unit_price IS NULL OR unit_price >= 0", name=op.f("ck_exhibitor_order_lines_unit_price_not_negative")),
        sa.CheckConstraint("item_id IS NULL OR unit_price IS NOT NULL", name=op.f("ck_exhibitor_order_lines_catalog_line_priced")),
        sa.CheckConstraint("(unit_price IS NULL) = (amount IS NULL)", name=op.f("ck_exhibitor_order_lines_amount_with_price")),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name=op.f("ck_exhibitor_order_lines_amount_not_negative")),
        sa.CheckConstraint("item_id IS NULL OR image_key IS NULL", name=op.f("ck_exhibitor_order_lines_image_only_on_extra_items")),
        _edition_fk("exhibitor_order_lines"),
        sa.ForeignKeyConstraint(["order_id", "edition_id"], ["exhibitor_orders.id", "exhibitor_orders.edition_id"], name="fk_exhibitor_order_lines_order_id_exhibitor_orders", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id", "edition_id"], ["order_form_items.id", "order_form_items.edition_id"], name="fk_exhibitor_order_lines_item_id_order_form_items"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitor_order_lines")),
    )  # fmt: skip
    op.create_index(
        op.f("ix_exhibitor_order_lines_order_id"), "exhibitor_order_lines", ["order_id"]
    )
    op.create_index("ix_exhibitor_order_lines_item_id", "exhibitor_order_lines", ["item_id"])
    op.create_index(
        "uq_exhibitor_order_lines_order_item",
        "exhibitor_order_lines",
        ["order_id", "item_id"],
        unique=True,
        postgresql_where=sa.text("item_id IS NOT NULL"),
    )

    op.create_table(
        "exhibitor_order_files",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(f"purpose IN ({_quoted(PURPOSES)})", name=op.f("ck_exhibitor_order_files_purpose_valid")),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_exhibitor_order_files_size_positive")),
        _edition_fk("exhibitor_order_files"),
        sa.ForeignKeyConstraint(["order_id", "edition_id"], ["exhibitor_orders.id", "exhibitor_orders.edition_id"], name="fk_exhibitor_order_files_order_id_exhibitor_orders", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_account_id"], ["exhibitor_accounts.id"], name=op.f("fk_exhibitor_order_files_uploaded_by_account_id_exhibitor_accounts")),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], name=op.f("fk_exhibitor_order_files_uploaded_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitor_order_files")),
        sa.UniqueConstraint("file_key", name=op.f("uq_exhibitor_order_files_file_key")),
    )  # fmt: skip
    op.create_index(
        op.f("ix_exhibitor_order_files_order_id"), "exhibitor_order_files", ["order_id"]
    )

    op.create_table(
        "exhibitor_form_waivers",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("exhibitor_lead_id", sa.Uuid(), nullable=False),
        sa.Column("form_id", sa.Uuid(), nullable=False),
        sa.Column("waived_by_account_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        _edition_fk("exhibitor_form_waivers"),
        sa.ForeignKeyConstraint(["exhibitor_lead_id", "edition_id"], ["exhibitor_leads.id", "exhibitor_leads.edition_id"], name="fk_exhibitor_form_waivers_exhibitor_lead_id_exhibitor_leads"),
        sa.ForeignKeyConstraint(["form_id", "edition_id"], ["order_forms.id", "order_forms.edition_id"], name="fk_exhibitor_form_waivers_form_id_order_forms"),
        sa.ForeignKeyConstraint(["waived_by_account_id"], ["exhibitor_accounts.id"], name=op.f("fk_exhibitor_form_waivers_waived_by_account_id_exhibitor_accounts")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitor_form_waivers")),
        sa.UniqueConstraint("exhibitor_lead_id", "form_id", name=op.f("uq_exhibitor_form_waivers_exhibitor_lead_id_form_id")),
    )  # fmt: skip
    op.create_index("ix_exhibitor_form_waivers_form_id", "exhibitor_form_waivers", ["form_id"])


def downgrade() -> None:
    op.drop_table("exhibitor_form_waivers")
    op.drop_table("exhibitor_order_files")
    op.drop_table("exhibitor_order_lines")
    op.drop_table("exhibitor_orders")
    op.drop_table("exhibitor_order_counters")
    op.drop_table("order_form_items")
    op.drop_table("order_forms")
    op.drop_constraint("uq_exhibitor_leads_id_edition", "exhibitor_leads", type_="unique")
