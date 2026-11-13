"""exhibitor quotations: per-edition settings, numbering, issued quotations

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-13

Phase 2 of docs/EXHIBITOR_QUOTATIONS.md (owner request 2026-11-13): quotations made from the lead
page before an exhibitor exists, laid out like the sales team's Excel sheet.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quotation_counters",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code", "year", name=op.f("pk_quotation_counters")),
    )
    op.create_table(
        "quotation_settings",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("company_code", sa.String(length=20), nullable=False),
        sa.Column("start_number", sa.Integer(), nullable=False),
        sa.Column("place", sa.String(length=100), nullable=False),
        sa.Column("letter_name", sa.Text(), nullable=True),
        sa.Column("event_text", sa.Text(), nullable=True),
        sa.Column(
            "rates",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("shell_includes", sa.Text(), nullable=True),
        sa.Column("discount_label", sa.String(length=60), nullable=False),
        sa.Column("vat_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("vat_base_num", sa.Integer(), nullable=False),
        sa.Column("vat_base_den", sa.Integer(), nullable=False),
        sa.Column(
            "terms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("signer_name", sa.String(length=200), nullable=True),
        sa.Column("signer_title", sa.String(length=200), nullable=True),
        sa.Column("signature_key", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "start_number >= 1", name=op.f("ck_quotation_settings_start_number_positive")
        ),
        sa.CheckConstraint(
            "vat_base_num > 0 AND vat_base_den > 0 AND vat_base_num <= vat_base_den",
            name=op.f("ck_quotation_settings_vat_base_valid"),
        ),
        sa.CheckConstraint(
            "vat_rate >= 0 AND vat_rate <= 100", name=op.f("ck_quotation_settings_vat_rate_valid")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_quotation_settings_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_quotation_settings_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_quotation_settings_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_settings")),
        sa.UniqueConstraint("edition_id", name=op.f("uq_quotation_settings_edition_id")),
    )
    op.create_table(
        "exhibitor_quotations",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("exhibitor_lead_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("replaces_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_company", sa.String(length=300), nullable=False),
        sa.Column("recipient_address", sa.Text(), nullable=True),
        sa.Column("attention", sa.String(length=200), nullable=True),
        sa.Column("stand_type", sa.String(length=10), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("booth_id", sa.Uuid(), nullable=True),
        sa.Column("booth_code", sa.String(length=30), nullable=True),
        sa.Column("width_m", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("length_m", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("area_sqm", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("complimentary_sqm", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("charged_sqm", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("stand_rate", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("raw_rate", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("discount_label", sa.String(length=60), nullable=True),
        sa.Column("discount_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("vat_base_num", sa.Integer(), nullable=False),
        sa.Column("vat_base_den", sa.Integer(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("cost_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("includes", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("letter", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "stand_type IN ('RAW', 'SHELL')", name=op.f("ck_exhibitor_quotations_stand_type_valid")
        ),
        sa.CheckConstraint(
            "status IN ('ACCEPTED', 'CANCELLED', 'ISSUED', 'SUPERSEDED')",
            name=op.f("ck_exhibitor_quotations_status_valid"),
        ),
        sa.CheckConstraint(
            "charged_sqm > 0", name=op.f("ck_exhibitor_quotations_charged_positive")
        ),
        sa.CheckConstraint(
            "complimentary_sqm >= 0 AND complimentary_sqm < area_sqm",
            name=op.f("ck_exhibitor_quotations_complimentary_valid"),
        ),
        sa.CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name=op.f("ck_exhibitor_quotations_discount_valid"),
        ),
        sa.CheckConstraint(
            "stand_rate >= 0 AND raw_rate >= 0",
            name=op.f("ck_exhibitor_quotations_rates_not_negative"),
        ),
        sa.CheckConstraint(
            "total_amount >= 0", name=op.f("ck_exhibitor_quotations_total_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["booth_id", "edition_id"],
            ["booths.id", "booths.edition_id"],
            name="fk_exhibitor_quotations_booth",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_exhibitor_quotations_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_exhibitor_quotations_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["exhibitor_lead_id", "edition_id"],
            ["exhibitor_leads.id", "exhibitor_leads.edition_id"],
            name="fk_exhibitor_quotations_lead",
        ),
        sa.ForeignKeyConstraint(
            ["replaces_id"],
            ["exhibitor_quotations.id"],
            name=op.f("fk_exhibitor_quotations_replaces_id_exhibitor_quotations"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_exhibitor_quotations_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitor_quotations")),
        sa.UniqueConstraint("number", name=op.f("uq_exhibitor_quotations_number")),
    )
    op.create_index(
        "ix_exhibitor_quotations_lead",
        "exhibitor_quotations",
        ["exhibitor_lead_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "uq_exhibitor_quotations_accepted",
        "exhibitor_quotations",
        ["exhibitor_lead_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACCEPTED'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_exhibitor_quotations_accepted",
        table_name="exhibitor_quotations",
        postgresql_where=sa.text("status = 'ACCEPTED'"),
    )
    op.drop_index("ix_exhibitor_quotations_lead", table_name="exhibitor_quotations")
    op.drop_table("exhibitor_quotations")
    op.drop_table("quotation_settings")
    op.drop_table("quotation_counters")
