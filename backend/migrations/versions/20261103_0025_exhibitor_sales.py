"""exhibitor sales pipeline: booths, exhibitor leads, contracts, payments

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-03

Owner request 2026-10-30 (docs/EXHIBITOR_LEADS_SALES_PIPELINE.md): exhibitor lead to opportunity
(a stage on the lead, not a table), booth, contract, and payment tagging without a gateway.
Portal accounts come with the portal login (phase 4).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    ]  # fmt: skip


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
    op.create_table(
        "booths",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("hall", sa.String(100), nullable=True),
        sa.Column("area_sqm", sa.Numeric(8, 2), nullable=False),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("area_sqm > 0", name=op.f("ck_booths_area_positive")),
        sa.CheckConstraint("price >= 0", name=op.f("ck_booths_price_not_negative")),
        _edition_fk("booths"),
        *_user_fks("booths"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booths")),
        sa.UniqueConstraint("edition_id", "code", name=op.f("uq_booths_edition_id_code")),
        sa.UniqueConstraint("id", "edition_id", name="uq_booths_id_edition"),
    )  # fmt: skip

    op.create_table(
        "exhibitor_leads",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("company_name", sa.String(300), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("email_normalized", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("phone_normalized", sa.String(32), nullable=True),
        sa.Column("product_categories", sa.Text(), nullable=True),
        sa.Column("booth_preference", sa.Text(), nullable=True),
        sa.Column("budget_estimate", sa.Numeric(14, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("lost_reason", sa.Text(), nullable=True),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("booth_id", sa.Uuid(), nullable=True),
        sa.Column("booth_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lead_owner_id", sa.Uuid(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("stage IN ('EXHIBITOR', 'LEAD', 'LOST', 'OPPORTUNITY')", name=op.f("ck_exhibitor_leads_stage_valid")),
        sa.CheckConstraint("booth_id IS NULL OR stage IN ('EXHIBITOR', 'OPPORTUNITY')", name=op.f("ck_exhibitor_leads_booth_only_when_selling")),
        sa.CheckConstraint("stage <> 'EXHIBITOR' OR booth_id IS NOT NULL", name=op.f("ck_exhibitor_leads_exhibitor_has_booth")),
        sa.CheckConstraint("budget_estimate IS NULL OR budget_estimate >= 0", name=op.f("ck_exhibitor_leads_budget_not_negative")),
        _edition_fk("exhibitor_leads"),
        sa.ForeignKeyConstraint(["booth_id", "edition_id"], ["booths.id", "booths.edition_id"], name="fk_exhibitor_leads_booth_id_booths"),
        sa.ForeignKeyConstraint(["lead_owner_id"], ["users.id"], name=op.f("fk_exhibitor_leads_lead_owner_id_users")),
        *_user_fks("exhibitor_leads"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitor_leads")),
    )  # fmt: skip
    op.create_index(
        "uq_exhibitor_leads_edition_email",
        "exhibitor_leads",
        ["edition_id", "email_normalized"],
        unique=True,
    )
    op.create_index(
        "uq_exhibitor_leads_booth",
        "exhibitor_leads",
        ["booth_id"],
        unique=True,
        postgresql_where=sa.text("booth_id IS NOT NULL"),
    )
    op.create_index("ix_exhibitor_leads_edition_stage", "exhibitor_leads", ["edition_id", "stage"])
    op.create_index(
        "ix_exhibitor_leads_edition_owner", "exhibitor_leads", ["edition_id", "lead_owner_id"]
    )
    op.create_index(
        "ix_exhibitor_leads_edition_updated",
        "exhibitor_leads",
        ["edition_id", sa.text("updated_at DESC")],
    )

    op.create_table(
        "exhibitor_contracts",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("exhibitor_lead_id", sa.Uuid(), nullable=False),
        sa.Column("contract_number", sa.String(50), nullable=True),
        sa.Column("pic_name", sa.String(200), nullable=True),
        sa.Column("company_address", sa.Text(), nullable=True),
        sa.Column("tax_id", sa.String(30), nullable=True),
        sa.Column("booth_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_file_key", sa.String(500), nullable=True),
        sa.Column("signed_file_name", sa.String(255), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('DRAFT', 'SIGNED')", name=op.f("ck_exhibitor_contracts_status_valid")),
        sa.CheckConstraint("booth_price >= 0", name=op.f("ck_exhibitor_contracts_booth_price_not_negative")),
        sa.CheckConstraint("discount_amount >= 0 AND discount_amount <= booth_price", name=op.f("ck_exhibitor_contracts_discount_valid")),
        sa.CheckConstraint("total_amount IS NULL OR total_amount >= 0", name=op.f("ck_exhibitor_contracts_total_not_negative")),
        sa.CheckConstraint(
            "status <> 'SIGNED' OR (contract_number IS NOT NULL AND pic_name IS NOT NULL"
            " AND company_address IS NOT NULL AND total_amount IS NOT NULL"
            " AND signed_at IS NOT NULL AND signed_file_key IS NOT NULL)",
            name=op.f("ck_exhibitor_contracts_signed_complete"),
        ),
        _edition_fk("exhibitor_contracts"),
        sa.ForeignKeyConstraint(["exhibitor_lead_id"], ["exhibitor_leads.id"], name=op.f("fk_exhibitor_contracts_exhibitor_lead_id_exhibitor_leads")),
        *_user_fks("exhibitor_contracts"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitor_contracts")),
        sa.UniqueConstraint("exhibitor_lead_id", name=op.f("uq_exhibitor_contracts_exhibitor_lead_id")),
    )  # fmt: skip
    op.create_index(
        "uq_exhibitor_contracts_edition_number",
        "exhibitor_contracts",
        ["edition_id", "contract_number"],
        unique=True,
        postgresql_where=sa.text("contract_number IS NOT NULL"),
    )
    op.create_index(
        "ix_exhibitor_contracts_edition_status", "exhibitor_contracts", ["edition_id", "status"]
    )

    op.create_table(
        "exhibitor_payments",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("proof_file_key", sa.String(500), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("status IN ('PENDING', 'REJECTED', 'VERIFIED')", name=op.f("ck_exhibitor_payments_status_valid")),
        sa.CheckConstraint("method IN ('BANK_TRANSFER', 'CASH', 'OTHER')", name=op.f("ck_exhibitor_payments_method_valid")),
        sa.CheckConstraint("amount > 0", name=op.f("ck_exhibitor_payments_amount_positive")),
        sa.CheckConstraint("(status = 'PENDING') = (reviewed_at IS NULL)", name=op.f("ck_exhibitor_payments_reviewed_unless_pending")),
        _edition_fk("exhibitor_payments"),
        sa.ForeignKeyConstraint(["contract_id"], ["exhibitor_contracts.id"], name=op.f("fk_exhibitor_payments_contract_id_exhibitor_contracts")),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], name=op.f("fk_exhibitor_payments_reviewed_by_users")),
        *_user_fks("exhibitor_payments"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitor_payments")),
    )  # fmt: skip
    op.create_index(
        op.f("ix_exhibitor_payments_contract_id"), "exhibitor_payments", ["contract_id"]
    )
    op.create_index(
        "ix_exhibitor_payments_edition_status", "exhibitor_payments", ["edition_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("exhibitor_payments")
    op.drop_table("exhibitor_contracts")
    op.drop_table("exhibitor_leads")
    op.drop_table("booths")
